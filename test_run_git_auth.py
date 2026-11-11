"""Offline Git authentication regressions. All credentials are synthetic sentinels."""

import base64
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote


# Import without reading the developer's dotenv file.
with patch('dotenv.load_dotenv'):
    spec = importlib.util.spec_from_file_location('fintech_runner', Path(__file__).with_name('run.py'))
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

TOKEN = 'SENTINEL-only-fake+/=credential'
BASIC = base64.b64encode(f'x-access-token:{TOKEN}'.encode()).decode()
REMOTE = 'https://github.com/example/sentinel.git'
RAW_RUN = subprocess.run


class GitAuthTests(unittest.TestCase):
    def setUp(self):
        # Keep platform essentials, but never borrow real credentials from the
        # test runner's environment or dotenv file.
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in ('PATH', 'SYSTEMROOT', 'TEMP', 'TMP', 'HOME', 'USERPROFILE')}
        environment.update({
            'GITHUB_TOKEN': TOKEN, 'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'sentinel.keep', 'GIT_CONFIG_VALUE_0': 'unchanged',
            'GIT_PUSH_RETRIES': '1',
        })
        self.env_patch = patch.dict(os.environ, environment, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        original_cwd = Path.cwd()
        self.addCleanup(os.chdir, original_cwd)
        self.calls = []

    def assert_no_secrets(self, value):
        value = str(value)
        for secret in (TOKEN, BASIC, quote(TOKEN, safe='')):
            self.assertNotIn(secret, value)

    def fake_git(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        self.assert_no_secrets(args)
        self.assertNotIn('set-url', args)
        self.assertNotIn('GITHUB_TOKEN', kwargs['env'])
        self.assertTrue(kwargs['capture_output'])
        stdout = ''
        if args[1:3] == ['remote', 'get-url']:
            stdout = self.remote + '\n'
        elif args[1:3] == ['status', '-sb']:
            stdout = '## main...origin/main [ahead 1, behind 1]'
        elif args[1:3] == ['rev-parse', '--abbrev-ref']:
            stdout = 'main\n'
        return subprocess.CompletedProcess(args, 0, stdout, '')

    def config(self, env):
        return [(env[f'GIT_CONFIG_KEY_{i}'], env[f'GIT_CONFIG_VALUE_{i}'])
                for i in range(int(env.get('GIT_CONFIG_COUNT', '0')))]

    def test_https_auth_is_child_only_and_scoped(self):
        self.remote = REMOTE
        os.environ['GIT_TRACE_CURL'] = 'sentinel-trace-file'
        os.environ['GIT_TRACE_REDACT'] = '0'
        os.environ['GIT_CURL_VERBOSE'] = '1'
        before = dict(os.environ)
        with patch.object(runner.subprocess, 'run', side_effect=self.fake_git):
            runner.run_git(['git', 'fetch', 'origin'], auth_remote='origin')
        self.assertEqual(dict(os.environ), before)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.config(self.calls[0][1]['env']), [('sentinel.keep', 'unchanged')])
        env = self.calls[-1][1]['env']
        self.assertFalse(any(key.startswith('GIT_TRACE') or key == 'GIT_CURL_VERBOSE' for key in env))
        config = self.config(env)
        self.assertIn(('http.https://github.com/.extraheader', f'Authorization: Basic {BASIC}'), config)
        self.assertIn(('credential.helper', ''), config)
        self.assertIn(('http.https://github.com/.followRedirects', 'false'), config)
        # Ask real Git to confirm URL matching without any network operation.
        for url, expected in ((REMOTE, 0), ('https://github.com.evil.test/repo', 1),
                              ('https://example.org/repo', 1)):
            result = RAW_RUN(['git', 'config', '--get-urlmatch', 'http.extraheader', url],
                             env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected)
            if expected == 0:
                self.assertEqual(result.stdout.strip(), f'Authorization: Basic {BASIC}')

    def test_other_hosts_ssh_and_mixed_push_urls_receive_no_token(self):
        for remote in ('git@github.com:example/sentinel.git',
                       'ssh://git@github.com/example/sentinel.git',
                       'https://example.org/repo.git', 'https://github.com.evil.test/repo',
                       REMOTE + '\nhttps://example.org/repo.git'):
            with self.subTest(remote=remote):
                self.remote = remote
                with patch.object(runner.subprocess, 'run', side_effect=self.fake_git):
                    runner.run_git(['git', 'push', 'origin', 'main'], auth_remote='origin')
                self.assertIn('--push', self.calls[-2][0])
                self.assert_no_secrets(self.calls[-1][1]['env'])

    def test_tokenless_git_uses_existing_auth(self):
        with patch.dict(os.environ, {'GITHUB_TOKEN': ''}), \
             patch.object(runner.subprocess, 'run', side_effect=self.fake_git):
            runner.run_git(['git', 'fetch', 'origin'], auth_remote='origin')
        self.assertEqual(len(self.calls), 1)
        self.assert_no_secrets(self.calls[0][1]['env'])

    def test_credential_free_remote_escapes_are_preserved(self):
        self.remote = 'https://github.com/example/repo%20name.git'
        with patch.object(runner.subprocess, 'run', side_effect=self.fake_git):
            result = runner.run_git(['git', 'remote', 'get-url', 'origin'])
        self.assertEqual(result.stdout.strip(), self.remote)

    def test_existing_url_credentials_are_rejected_without_rewrite(self):
        self.remote = f'https://{quote(TOKEN, safe="")}@github.com/example/repo.git'
        with patch.object(runner.subprocess, 'run', side_effect=self.fake_git):
            with self.assertRaisesRegex(ValueError, 'credential-free'):
                runner.run_git(['git', 'push', 'origin', 'main'], auth_remote='origin')
        self.assertEqual(len(self.calls), 1)

    def test_redacts_raw_encoded_url_and_basic_credentials(self):
        text = (f'{TOKEN} {quote(quote(TOKEN, safe=""), safe="")} {BASIC} '
                f'https://someone:unknown-password@github.com/repo '
                f'Authorization: Basic {BASIC} Authorization: Bearer {TOKEN}')
        sanitized = runner.sanitize_git_output(text)
        self.assert_no_secrets(sanitized)
        self.assertNotIn('unknown-password', sanitized)
        self.assertIn('[REDACTED]', sanitized)
        output = io.StringIO()
        with redirect_stdout(output):
            runner.print_git_output_tail(text, 'Error:')
        self.assert_no_secrets(output.getvalue())

    def test_failure_timeout_and_interruption_leave_env_unchanged(self):
        for error in (subprocess.CalledProcessError(1, ['git'], output=TOKEN, stderr=BASIC),
                      subprocess.TimeoutExpired(['git'], 5, output=TOKEN, stderr=BASIC),
                      KeyboardInterrupt()):
            self.remote = REMOTE
            before = dict(os.environ)

            def failing(args, **kwargs):
                result = self.fake_git(args, **kwargs)
                if args[1] == 'push':
                    raise error
                return result

            with patch.object(runner.subprocess, 'run', side_effect=failing):
                with self.assertRaises(type(error)) as raised:
                    runner.run_git(['git', 'push', 'origin', 'main'], auth_remote='origin', check=True)
            self.assert_no_secrets(str(raised.exception))
            self.assert_no_secrets(getattr(raised.exception, 'stdout', ''))
            self.assert_no_secrets(getattr(raised.exception, 'stderr', ''))
            self.assertEqual(dict(os.environ), before)

    def test_pull_and_legacy_push_paths_never_rewrite_origin(self):
        self.remote = REMOTE
        output = io.StringIO()
        with patch.object(runner.subprocess, 'run', side_effect=self.fake_git), \
             patch.object(runner, 'get_current_branch', return_value='main'), \
             patch.object(runner, 'get_upstream_branch', return_value='origin/main'), \
             patch.object(runner, 'get_unpushed_commits', return_value=['a' * 40]), \
             redirect_stdout(output):
            self.assertTrue(runner.git_pull())
            self.assertTrue(runner.git_commit_and_push())
        network_calls = [(args, kw) for args, kw in self.calls if args[1] in ('fetch', 'pull', 'push')]
        self.assertGreaterEqual(len(network_calls), 4)
        for args, kw in network_calls:
            self.assertIn(('http.https://github.com/.extraheader', f'Authorization: Basic {BASIC}'),
                          self.config(kw['env']))
        self.assert_no_secrets(output.getvalue())

    def test_pull_failure_logs_are_redacted(self):
        self.remote = REMOTE

        def failing(args, **kwargs):
            result = self.fake_git(args, **kwargs)
            if args[1] in ('fetch', 'pull'):
                result.returncode = 1
                result.stderr = f'bad {TOKEN} {BASIC} https://{quote(TOKEN, safe="")}@github.com/'
            return result

        output = io.StringIO()
        with patch.object(runner.subprocess, 'run', side_effect=failing), redirect_stdout(output):
            self.assertFalse(runner.git_pull())
        self.assert_no_secrets(output.getvalue())

    def test_publish_real_local_git_keeps_temp_config_clean_and_cleans_up(self):
        for outcome in ('success', 'failure', 'interrupt'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'source'
                source.mkdir()
                for args in (['init', '-b', 'main'], ['remote', 'add', 'origin', REMOTE]):
                    RAW_RUN(['git'] + args, cwd=source, check=True, capture_output=True)
                original_config = (source / '.git/config').read_bytes()
                staged = []

                def stage(site):
                    site.mkdir(parents=True)
                    (site / 'index.html').write_text('sentinel site', encoding='utf-8')
                    staged.append(site)

                def local_git(args, **kwargs):
                    self.assert_no_secrets(args)
                    if args[1] == 'push':
                        config = (Path(kwargs['cwd']) / '.git/config').read_text()
                        self.assert_no_secrets(config)
                        self.assertIn(REMOTE, config)
                        self.assertIn(('http.https://github.com/.extraheader', f'Authorization: Basic {BASIC}'),
                                      self.config(kwargs['env']))
                        if outcome == 'interrupt':
                            raise KeyboardInterrupt()
                        return subprocess.CompletedProcess(args, int(outcome == 'failure'), TOKEN, BASIC)
                    return RAW_RUN(args, **kwargs)

                output = io.StringIO()
                before = dict(os.environ)
                with patch.object(runner, 'script_dir', source), \
                     patch.object(runner, 'get_current_branch', return_value='main'), \
                     patch.object(runner, 'stage_static_site', side_effect=stage), \
                     patch.object(runner, 'last_published_fingerprint', return_value=None), \
                     patch.object(runner, 'remember_published_fingerprint') as remember, \
                     patch.object(runner.subprocess, 'run', side_effect=local_git), redirect_stdout(output):
                    if outcome == 'interrupt':
                        with self.assertRaises(KeyboardInterrupt):
                            runner.publish_static_site()
                    else:
                        self.assertEqual(runner.publish_static_site(), outcome == 'success')
                    self.assertEqual(remember.called, outcome == 'success')
                self.assertEqual((source / '.git/config').read_bytes(), original_config)
                self.assertEqual(dict(os.environ), before)
                self.assertEqual(len(staged), 1)
                self.assertFalse(staged[0].exists())
                self.assert_no_secrets(output.getvalue())


if __name__ == '__main__':
    unittest.main()
