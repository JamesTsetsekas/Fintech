#!/usr/bin/env python3
"""
Master script to run all Bitcoin and Stock visualization reports.

This script executes both Bitcoin and Stock report runners and provides
a consolidated summary of all reports.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import os
import shutil
import tempfile
import time
try:
    from zoneinfo import ZoneInfo
    EST = ZoneInfo("America/New_York")
except (ImportError, OSError):
    EST = None  # Python < 3.9 or no tzdata; timestamps use local time
from dotenv import load_dotenv

# Eastern time for timestamps (EST/EDT via America/New_York)
try:
    from zoneinfo import ZoneInfo
    EST = ZoneInfo("America/New_York")
except ImportError:
    # Python < 3.9: use fixed UTC-5 (EST, no DST)
    EST = timezone(timedelta(hours=-5))

# Load environment variables from .env file
load_dotenv()

# Get the script directory (project root)
script_dir = Path(__file__).parent

DEFAULT_PUSH_CHUNK_SIZE = 8
DEFAULT_PUSH_RETRIES = 3
DEFAULT_PUSH_RETRY_DELAY_SECONDS = 30

# Define report runners to execute
REPORT_RUNNERS = [
    {
        'name': 'Bitcoin Reports',
        'path': script_dir / 'Bitcoin' / 'run_all_reports.py',
        'description': 'Bitcoin visualization reports'
    },
    {
        'name': 'Stock Reports',
        'path': script_dir / 'Stock' / 'run_all_reports.py',
        'description': 'Stock visualization reports'
    },
]

def get_env_int(name, default, minimum=1):
    """Read a positive integer env var with a conservative fallback."""
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        print(f"⚠ Invalid {name}={raw_value!r}; using {default}")
        return default
    if value < minimum:
        print(f"⚠ {name} must be at least {minimum}; using {default}")
        return default
    return value

def get_authenticated_remote_url(original_url):
    """Return an authenticated GitHub remote URL, or None if no token is set."""
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        return None

    if original_url.startswith('https://'):
        return original_url.replace('https://', f'https://{github_token}@', 1)
    if original_url.startswith('git@github.com:'):
        repo_path = original_url.replace('git@github.com:', '', 1)
        if not repo_path.endswith('.git'):
            repo_path = f"{repo_path}.git"
        return f"https://{github_token}@github.com/{repo_path}"
    return original_url

def get_current_branch():
    result = subprocess.run(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True,
        text=True,
        cwd=script_dir
    )
    if result.returncode != 0:
        print(f"✗ Could not determine current branch: {result.stderr}")
        return None
    branch = result.stdout.strip()
    if branch == 'HEAD':
        print("✗ Refusing to push from detached HEAD")
        return None
    return branch

def get_upstream_branch(current_branch):
    result = subprocess.run(
        ['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'],
        capture_output=True,
        text=True,
        cwd=script_dir
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return f"origin/{current_branch}"

def get_unpushed_commits(upstream_branch):
    result = subprocess.run(
        ['git', 'rev-list', '--reverse', f'{upstream_branch}..HEAD'],
        capture_output=True,
        text=True,
        cwd=script_dir
    )
    if result.returncode != 0:
        print(f"✗ Could not list unpushed commits: {result.stderr}")
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def print_git_output_tail(output, label):
    lines = [line for line in (output or '').strip().splitlines() if line.strip()]
    if not lines:
        return
    print(label)
    for line in lines[-10:]:
        print(f"  {line}")

def is_non_fast_forward_error(stderr):
    lowered = (stderr or '').lower()
    return (
        'non-fast-forward' in lowered
        or 'fetch first' in lowered
        or 'stale info' in lowered
    )

def is_remote_quota_error(stderr):
    lowered = (stderr or '').lower()
    return (
        'above its size quota' in lowered
        or 'repository size' in lowered and 'quota' in lowered
    )

def push_commit_with_retries(commit_sha, remote_branch, chunk_number, total_chunks):
    retries = get_env_int('GIT_PUSH_RETRIES', DEFAULT_PUSH_RETRIES)
    retry_delay = get_env_int('GIT_PUSH_RETRY_DELAY_SECONDS', DEFAULT_PUSH_RETRY_DELAY_SECONDS)
    refspec = f"{commit_sha}:refs/heads/{remote_branch}"

    for attempt in range(1, retries + 1):
        print(
            f"Push chunk {chunk_number}/{total_chunks}, attempt {attempt}/{retries}: "
            f"{commit_sha[:12]} -> origin/{remote_branch}"
        )
        result = subprocess.run(
            ['git', 'push', 'origin', refspec],
            capture_output=True,
            text=True,
            cwd=script_dir
        )
        if result.returncode == 0:
            print_git_output_tail(result.stdout, "Push output:")
            return True

        print_git_output_tail(result.stderr, "Push error:")
        if is_remote_quota_error(result.stderr):
            print("✗ Push rejected because the GitHub repository is above its size quota.")
            return False
        if is_non_fast_forward_error(result.stderr):
            print("✗ Push rejected because the remote branch moved. Pull/rebase before retrying.")
            return False
        if attempt < retries:
            print(f"Retrying push in {retry_delay} seconds...")
            time.sleep(retry_delay)

    return False

def refresh_origin_branch(remote_branch):
    result = subprocess.run(
        ['git', 'fetch', 'origin', remote_branch],
        capture_output=True,
        text=True,
        cwd=script_dir
    )
    if result.returncode != 0:
        print_git_output_tail(result.stderr, "⚠ Could not refresh origin after push:")
        return False
    return True

def push_pending_commits():
    """Push unpushed commits in smaller fast-forward chunks."""
    os.chdir(script_dir)

    current_branch = get_current_branch()
    if not current_branch:
        return False

    upstream_branch = get_upstream_branch(current_branch)
    remote_branch = upstream_branch.split('/', 1)[1] if '/' in upstream_branch else current_branch
    pending_commits = get_unpushed_commits(upstream_branch)
    if pending_commits is None:
        return False

    if not pending_commits:
        print("No unpushed commits to push.")
        return True

    result = subprocess.run(
        ['git', 'remote', 'get-url', 'origin'],
        capture_output=True,
        text=True,
        check=True,
        cwd=script_dir
    )
    original_url = result.stdout.strip()
    auth_url = get_authenticated_remote_url(original_url)
    if not auth_url:
        print("✗ GITHUB_TOKEN not found in .env file")
        print("Please create a .env file with your GitHub token.")
        print("See .env.example for template.")
        return False

    chunk_size = get_env_int('GIT_PUSH_CHUNK_SIZE', DEFAULT_PUSH_CHUNK_SIZE)
    chunk_targets = pending_commits[chunk_size - 1::chunk_size]
    if not chunk_targets or chunk_targets[-1] != pending_commits[-1]:
        chunk_targets.append(pending_commits[-1])

    print(
        f"Found {len(pending_commits)} unpushed commits. "
        f"Pushing in {len(chunk_targets)} chunk(s) of up to {chunk_size} commits."
    )

    subprocess.run(['git', 'remote', 'set-url', 'origin', auth_url], check=True, cwd=script_dir)
    try:
        for index, commit_sha in enumerate(chunk_targets, start=1):
            if not push_commit_with_retries(commit_sha, remote_branch, index, len(chunk_targets)):
                return False
        refresh_origin_branch(remote_branch)
        print("✓ Pushed pending commits to GitHub")
        return True
    finally:
        subprocess.run(['git', 'remote', 'set-url', 'origin', original_url], check=True, cwd=script_dir)

def git_pull():
    """Pull latest changes from GitHub using token authentication."""
    print("\n" + "="*60)
    print("GIT PULL - UPDATING PROJECT")
    print("="*60)

    try:
        # Change to script directory
        os.chdir(script_dir)
        
        # Initialize result to None
        result = None

        # Get GitHub token from environment
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            print("⚠ GITHUB_TOKEN not found in .env file")
            print("Attempting pull without authentication...")
            # Fetch first to check status
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin'],
                capture_output=True,
                text=True
            )
            
            # Check if branches have diverged
            status_result = subprocess.run(
                ['git', 'status', '-sb'],
                capture_output=True,
                text=True
            )
            status_output = status_result.stdout.strip()
            
            has_diverged = '[' in status_output and 'ahead' in status_output and 'behind' in status_output
            
            if has_diverged:
                print("Branches have diverged. Using rebase strategy...")
                result = subprocess.run(
                    ['git', 'pull', '--rebase', '--no-edit'],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"⚠ Rebase failed, trying merge: {result.stderr}")
                    result = subprocess.run(
                        ['git', 'pull', '--no-edit'],
                        capture_output=True,
                        text=True
                    )
            else:
                result = subprocess.run(
                    ['git', 'pull'],
                    capture_output=True,
                    text=True
                )
            
            if result.returncode != 0:
                print(f"✗ Pull failed: {result.stderr}")
                return False
        else:
            # Get the current remote URL
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                check=True
            )
            original_url = result.stdout.strip()

            # Create authenticated URL
            if original_url.startswith('https://'):
                # Replace https://github.com/ with https://token@github.com/
                auth_url = original_url.replace('https://', f'https://{github_token}@')
            elif original_url.startswith('git@'):
                # Convert SSH to HTTPS with token
                auth_url = original_url.replace('git@github.com:', f'https://{github_token}@github.com/')
                auth_url = auth_url.replace('.git', '') + '.git'
            else:
                auth_url = original_url

            # Temporarily set remote URL with token
            subprocess.run(['git', 'remote', 'set-url', 'origin', auth_url], check=True)

            try:
                # First fetch to check status
                fetch_result = subprocess.run(
                    ['git', 'fetch', 'origin'],
                    capture_output=True,
                    text=True
                )
                if fetch_result.returncode != 0:
                    print(f"⚠ Fetch failed: {fetch_result.stderr}")
                    # Continue anyway, might still work
                
                # Check if branches have diverged
                status_result = subprocess.run(
                    ['git', 'status', '-sb'],
                    capture_output=True,
                    text=True
                )
                if status_result.returncode != 0:
                    print(f"⚠ Status check failed: {status_result.stderr}")
                    # Use normal pull as fallback
                    result = subprocess.run(
                        ['git', 'pull'],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        print(f"✗ Pull failed: {result.stderr}")
                        return False
                    # Pull succeeded, skip divergence check
                else:
                    status_output = status_result.stdout.strip()
                    
                    # Check for divergence (ahead and behind)
                    has_diverged = '[' in status_output and 'ahead' in status_output and 'behind' in status_output
                    
                    if has_diverged:
                        print("Branches have diverged. Using rebase strategy to integrate changes...")
                        # Use pull with rebase to put local commits on top of remote
                        result = subprocess.run(
                            ['git', 'pull', '--rebase', '--no-edit'],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode != 0:
                            print(f"⚠ Rebase failed: {result.stderr}")
                            print("Attempting merge strategy...")
                            # If rebase fails, try merge
                            result = subprocess.run(
                                ['git', 'pull', '--no-edit'],
                                capture_output=True,
                                text=True
                            )
                            if result.returncode != 0:
                                print(f"✗ Pull with merge also failed: {result.stderr}")
                                return False
                    else:
                        # Normal pull (no divergence)
                        result = subprocess.run(
                            ['git', 'pull'],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode != 0:
                            print(f"✗ Pull failed: {result.stderr}")
                            return False
            finally:
                # Restore original remote URL
                subprocess.run(['git', 'remote', 'set-url', 'origin', original_url], check=True)

        # Ensure result is defined before using it
        if result is None:
            print("✗ Internal error: result variable not defined")
            return False
        
        if not hasattr(result, 'stdout') or result.stdout is None:
            print("✗ Internal error: result.stdout is not available")
            return False
            
        print(result.stdout.strip())

        if "Already up to date" in result.stdout or "Already up-to-date" in result.stdout or "Current branch main is up to date" in result.stdout:
            print("✓ Project is already up to date")
        elif "Fast-forward" in result.stdout or "Updating" in result.stdout or "Rebasing" in result.stdout or "Merging" in result.stdout:
            print("✓ Project updated successfully")
        else:
            print("✓ Project synchronized")

        return True

    except subprocess.CalledProcessError as e:
        print(f"✗ Git pull failed: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Error output: {e.stderr}")
        elif hasattr(e, 'stdout') and e.stdout:
            print(f"Output: {e.stdout}")
        return False
    except Exception as e:
        print(f"✗ Exception during git pull: {e}")
        return False

def check_requirements_changed():
    """Check if any requirements.txt files have changed or if we need to verify installation."""
    try:
        os.chdir(script_dir)
        
        # Get list of all requirements.txt files
        req_files = []
        for search_dir in ['Bitcoin', 'Stock']:
            dir_path = script_dir / search_dir
            if dir_path.exists():
                req_files.extend(dir_path.rglob("requirements.txt"))
        
        # Also check root requirements.txt
        root_req = script_dir / "requirements.txt"
        if root_req.exists():
            req_files.append(root_req)
        
        if not req_files:
            return False
        
        # Check if any requirements files were modified in the last commit
        result = subprocess.run(
            ['git', 'log', '-1', '--name-only', '--pretty=format:', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=script_dir
        )
        
        recent_changes = set(result.stdout.strip().split('\n'))
        
        # Check if any requirements.txt files are in recent changes
        for req_file in req_files:
            req_path = str(req_file.relative_to(script_dir))
            if req_path in recent_changes:
                print(f"  Detected changes in: {req_path}")
                return True
        
        # Also check git status for modified files
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            cwd=script_dir
        )
        
        status_output = status_result.stdout.strip()
        for req_file in req_files:
            req_path = str(req_file.relative_to(script_dir))
            # Check if file is modified (M) or untracked (??)
            if req_path in status_output or any(req_path in line for line in status_output.split('\n') if line):
                print(f"  Detected changes in: {req_path}")
                return True
        
        return False
        
    except Exception as e:
        print(f"⚠ Could not check requirements changes: {e}")
        # If we can't check, assume they need verification
        return True

def get_venv_python():
    """Get the Python executable from venv if it exists, otherwise return system Python."""
    venv_python = script_dir / 'venv' / 'bin' / 'python'
    if venv_python.exists():
        return str(venv_python)
    
    # Check for Windows venv
    venv_python = script_dir / 'venv' / 'Scripts' / 'python.exe'
    if venv_python.exists():
        return str(venv_python)
    
    return sys.executable

def install_requirements_if_needed():
    """Install requirements if they have changed or if venv doesn't have packages."""
    print("\n" + "="*60)
    print("CHECKING AND INSTALLING REQUIREMENTS")
    print("="*60)
    
    try:
        os.chdir(script_dir)
        
        venv_python = get_venv_python()
        venv_exists = 'venv' in venv_python
        
        if not venv_exists:
            print("⚠ Virtual environment not found. Using system Python.")
            print("⚠ Consider running setup_ubuntu.sh to create a virtual environment.")
            # Try to install anyway (might work on some systems)
            venv_python = sys.executable
        
        # Check if requirements changed
        requirements_changed = check_requirements_changed()
        
        if not requirements_changed:
            # Quick check: try importing a common package to see if venv has packages
            print("Verifying requirements are installed...")
            try:
                # Check for pandas (common package used in reports)
                result = subprocess.run(
                    [venv_python, '-c', 'import pandas; import matplotlib; import numpy'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    print("✓ Key packages verified, skipping installation")
                    return True
                else:
                    print("⚠ Some packages missing, will install...")
                    requirements_changed = True
            except subprocess.TimeoutExpired:
                print("⚠ Package check timed out, will install to be safe...")
                requirements_changed = True
            except Exception as e:
                print(f"⚠ Could not verify packages: {e}")
                print("  Will install requirements to be safe...")
                requirements_changed = True
        
        if requirements_changed:
            print("Requirements changed or need installation. Installing...")
            
            # Install root requirements first if it exists
            root_req = script_dir / "requirements.txt"
            if root_req.exists():
                print("\nInstalling root requirements...")
                try:
                    result = subprocess.run(
                        [venv_python, '-m', 'pip', 'install', '-r', str(root_req)],
                        capture_output=True,
                        text=True,
                        timeout=600  # 10 minute timeout
                    )
                    if result.returncode == 0:
                        print("✓ Root requirements installed")
                    else:
                        print(f"⚠ Root requirements installation had issues: {result.stderr[:200]}")
                except subprocess.TimeoutExpired:
                    print("✗ Root requirements installation timed out")
                    return False
                except Exception as e:
                    print(f"⚠ Root requirements installation error: {e}")
            
            # Install all project requirements
            print("\nInstalling all project requirements...")
            
            # Collect all requirements.txt files
            req_files = []
            for search_dir in ['Bitcoin', 'Stock']:
                dir_path = script_dir / search_dir
                if dir_path.exists():
                    req_files.extend(sorted(dir_path.rglob("requirements.txt")))
            
            if not req_files:
                print("⚠ No requirements.txt files found")
                return True
            
            # Collect unique requirements
            all_requirements = set()
            for req_file in req_files:
                try:
                    with open(req_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                all_requirements.add(line)
                except Exception as e:
                    print(f"⚠ Could not read {req_file}: {e}")
            
            if not all_requirements:
                print("⚠ No requirements to install")
                return True
            
            # Install all unique requirements at once
            temp_req_file = script_dir / "temp_requirements.txt"
            try:
                with open(temp_req_file, 'w', encoding='utf-8') as f:
                    for req in sorted(all_requirements):
                        f.write(f"{req}\n")
                
                print(f"Installing {len(all_requirements)} unique packages...")
                result = subprocess.run(
                    [venv_python, '-m', 'pip', 'install', '-r', str(temp_req_file), '--quiet'],
                    capture_output=True,
                    text=True,
                    timeout=1800  # 30 minute timeout
                )
                
                if result.returncode == 0:
                    print(f"✓ Successfully installed {len(all_requirements)} packages")
                    return True
                else:
                    print(f"⚠ Installation had issues: {result.stderr[:500]}")
                    # Still return True to continue - some packages might already be installed
                    return True
            except subprocess.TimeoutExpired:
                print("✗ Installation timed out")
                return False
            except Exception as e:
                print(f"✗ Installation error: {e}")
                return False
            finally:
                # Clean up temp file
                if temp_req_file.exists():
                    try:
                        temp_req_file.unlink()
                    except:
                        pass
        else:
            print("✓ No requirement changes detected")
            return True
            
    except Exception as e:
        print(f"✗ Error checking/installing requirements: {e}")
        return False

def git_commit_and_push():
    """Commit and push changes to GitHub using token authentication."""
    print("\n" + "="*60)
    print("GIT COMMIT AND PUSH")
    print("="*60)

    try:
        # Change to script directory
        os.chdir(script_dir)

        # Check git status
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True
        )

        if not result.stdout.strip():
            print("No working tree changes to commit.")
            return push_pending_commits()

        print("Changes detected. Committing and pushing...")

        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True)

        # Commit with timestamp (EST when available)
        now = datetime.now(EST) if EST else datetime.now()
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
        commit_message = f"Auto-update charts and reports - {timestamp}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        print(f"✓ Committed: {commit_message}")

        return push_pending_commits()

    except subprocess.CalledProcessError as e:
        print(f"✗ Git operation failed: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"✗ Exception during git operation: {e}")
        return False

def run_report_runner(runner_info):
    """Run a report runner script and return success status."""
    name = runner_info['name']
    script_path = runner_info['path']

    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"Description: {runner_info['description']}")
    print(f"Script: {script_path}")
    print(f"{'='*60}")
    
    # Check if script exists
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        return False
    
    try:
        # Use venv Python if available, otherwise use system Python
        python_exe = get_venv_python()
        
        # Run the script
        result = subprocess.run(
            [python_exe, str(script_path)],
            cwd=script_dir,
            capture_output=False,  # Let output stream directly for better visibility
            text=True,
            timeout=3600  # 1 hour timeout per runner (some reports can take a while)
        )
        
        if result.returncode == 0:
            print(f"\n✓ Successfully completed: {name}")
            return True
        else:
            print(f"\n✗ Failed: {name} (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"\n✗ Timeout: {name} (exceeded 1 hour)")
        return False
    except Exception as e:
        print(f"\n✗ Exception running {name}: {e}")
        return False

def run_site_generator():
    """Generate static website data after report images are refreshed."""
    generator_path = script_dir / 'web' / 'generate_site.py'

    print(f"\n{'='*60}")
    print("GENERATING STATIC WEBSITE DATA")
    print(f"Script: {generator_path}")
    print(f"{'='*60}")

    if not generator_path.exists():
        print(f"ERROR: Site generator not found: {generator_path}")
        return False

    try:
        python_exe = get_venv_python()
        result = subprocess.run(
            [python_exe, str(generator_path)],
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=900,
        )

        if result.returncode == 0:
            print("✓ Static website data generated")
            if result.stdout:
                for line in result.stdout.strip().split('\n')[-10:]:
                    if line.strip():
                        print(f"  {line}")
            return True

        print("✗ Static website generation failed")
        if result.stderr:
            print("Error output:")
            for line in result.stderr.strip().split('\n')[-10:]:
                if line.strip():
                    print(f"  {line}")
        if result.stdout:
            print("Standard output:")
            for line in result.stdout.strip().split('\n')[-10:]:
                if line.strip():
                    print(f"  {line}")
        return False

    except subprocess.TimeoutExpired:
        print("✗ Static website generation timed out")
        return False
    except Exception as e:
        print(f"✗ Exception during static website generation: {e}")
        return False

def copy_path_to_site(source_path, site_dir, destination_path=None):
    """Copy a file or directory into the static site staging directory."""
    source_path = Path(source_path)
    if not source_path.exists():
        return

    if destination_path is None:
        destination_path = source_path.relative_to(script_dir)
    destination = site_dir / destination_path
    destination.parent.mkdir(parents=True, exist_ok=True)

    if source_path.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source_path, destination)
    else:
        shutil.copy2(source_path, destination)

def stage_static_site(site_dir):
    """Build the latest-only static site payload for GitHub Pages."""
    site_dir.mkdir(parents=True, exist_ok=True)

    for relative_path in [
        Path("index.html"),
        Path("Bitcoin/index.html"),
        Path("Stocks/index.html"),
        Path("web/assets"),
        Path("web/data"),
    ]:
        copy_path_to_site(script_dir / relative_path, site_dir, relative_path)

    for png_path in sorted((script_dir / "Bitcoin").rglob("*.png")):
        copy_path_to_site(png_path, site_dir)
    for png_path in sorted((script_dir / "Stock").rglob("*.png")):
        copy_path_to_site(png_path, site_dir)
    for png_path in sorted(script_dir.glob("*.png")):
        copy_path_to_site(png_path, site_dir)

    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

def publish_static_site():
    """Force-publish the latest generated site to a history-light Pages branch."""
    publish_branch = os.getenv("PUBLISH_BRANCH", "gh-pages")

    print(f"\n{'='*60}")
    print("PUBLISHING STATIC WEBSITE")
    print(f"Branch: {publish_branch}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            check=True,
            cwd=script_dir,
        )
        original_url = result.stdout.strip()
        auth_url = get_authenticated_remote_url(original_url) or original_url

        now = datetime.now(EST) if EST else datetime.now()
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
        commit_message = f"Publish generated site - {timestamp}"

        with tempfile.TemporaryDirectory(prefix="fintech-site-") as temp_dir:
            site_dir = Path(temp_dir) / "site"
            stage_static_site(site_dir)

            subprocess.run(['git', 'init'], cwd=site_dir, check=True, capture_output=True, text=True)
            subprocess.run(['git', 'checkout', '-B', publish_branch], cwd=site_dir, check=True, capture_output=True, text=True)
            subprocess.run(['git', 'config', 'user.name', 'Fintech Automation'], cwd=site_dir, check=True)
            subprocess.run(['git', 'config', 'user.email', 'actions@users.noreply.github.com'], cwd=site_dir, check=True)
            subprocess.run(['git', 'add', '.'], cwd=site_dir, check=True)
            commit_result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=site_dir,
                capture_output=True,
                text=True,
            )
            if commit_result.returncode != 0:
                print("✗ Static site commit failed")
                print_git_output_tail(commit_result.stderr, "Commit error:")
                print_git_output_tail(commit_result.stdout, "Commit output:")
                return False

            subprocess.run(['git', 'remote', 'add', 'origin', auth_url], cwd=site_dir, check=True)
            push_result = subprocess.run(
                ['git', 'push', '--force', 'origin', f'{publish_branch}:refs/heads/{publish_branch}'],
                cwd=site_dir,
                capture_output=True,
                text=True,
            )
            if push_result.returncode != 0:
                print("✗ Static site publish failed")
                print_git_output_tail(push_result.stderr, "Push error:")
                return False

            print_git_output_tail(push_result.stdout, "Push output:")
            print(f"✓ Published latest static site to {publish_branch}")
            return True

    except subprocess.CalledProcessError as e:
        print(f"✗ Static site publish git operation failed: {e}")
        if e.stderr:
            print_git_output_tail(e.stderr, "Error output:")
        return False
    except Exception as e:
        print(f"✗ Exception publishing static site: {e}")
        return False

def main():
    """Main function to run all report runners."""
    start_time = datetime.now(EST) if EST else datetime.now()
    tz_label = " EST" if EST else ""

    print("\n" + "="*60)
    print("MASTER REPORT RUNNER")
    print("="*60)
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}{tz_label}")
    print(f"Total report runners: {len(REPORT_RUNNERS)}")
    print("="*60)
    print("\nThis will run all Bitcoin and Stock visualization reports.")
    print("Note: This may take a considerable amount of time.")
    print("Individual runners will show detailed progress for each report.\n")

    # Pull latest changes from GitHub
    pull_success = git_pull()
    if not pull_success:
        print("\n" + "="*60)
        print("ERROR: Failed to pull latest changes from GitHub.")
        print("Continuing with current version...")
        print("="*60)
    
    # Install/update requirements if needed (after git pull, in case requirements changed)
    if not install_requirements_if_needed():
        print("\n" + "="*60)
        print("WARNING: Requirements installation had issues.")
        print("Reports may fail if packages are missing.")
        print("Continuing anyway...")
        print("="*60)

    # Track results
    results = {
        'success': [],
        'failed': []
    }
    
    # Run each report runner
    for runner in REPORT_RUNNERS:
        success = run_report_runner(runner)
        if success:
            results['success'].append(runner['name'])
        else:
            results['failed'].append(runner['name'])
    
    # Summary
    end_time = datetime.now(EST) if EST else datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print("MASTER SUMMARY")
    print("="*60)
    print(f"Total report runners: {len(REPORT_RUNNERS)}")
    print(f"Successful: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Total duration: {duration}")
    print("="*60)
    
    if results['success']:
        print("\nSuccessful runners:")
        for name in results['success']:
            print(f"  ✓ {name}")
    
    if results['failed']:
        print("\nFailed runners:")
        for name in results['failed']:
            print(f"  ✗ {name}")
        print("\nSkipping git commit due to failed runners.")
        sys.exit(1)

    print("\nAll report runners completed successfully!")
    print("All Bitcoin and Stock visualization reports have been generated.")

    if not run_site_generator():
        print("\n" + "="*60)
        print("ERROR: Static website generation failed.")
        print("Skipping git commit to avoid pushing stale web data.")
        print("="*60)
        sys.exit(1)

    # Publish the generated site without committing generated outputs to main.
    publish_success = publish_static_site()

    if publish_success:
        print("\n" + "="*60)
        print("SUCCESS: Reports generated and published to GitHub Pages!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("WARNING: Reports generated but site publish failed.")
        print("="*60)
        sys.exit(1)

if __name__ == '__main__':
    if '--publish-only' in sys.argv:
        sys.exit(0 if publish_static_site() else 1)
    if '--push-pending-only' in sys.argv:
        sys.exit(0 if push_pending_commits() else 1)
    main()
