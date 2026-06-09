# Ubuntu Server Setup Instructions

This guide will help you set up the Fintech reports on Ubuntu Server with automated git pull/push.

## Prerequisites

1. **Install required system packages:**
   ```bash
   sudo apt update
   sudo apt install python3 python3-venv python3-pip git -y
   ```

## Setup Steps

### 1. Clone the repository (if not already done)
```bash
cd ~
git clone https://github.com/yourusername/Fintech.git
cd Fintech
```

### 2. Run the setup script
```bash
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

This script will:
- Create a virtual environment in `venv/`
- Install all Python dependencies
- Display setup instructions

### 3. Create your `.env` file with GitHub token
```bash
cp .env.example .env
nano .env
```

Add your GitHub token:
```
GITHUB_TOKEN=ghp_your_actual_token_here
```

**To create a GitHub token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name it "Fintech Auto-Update"
4. Select scope: `repo` (full control of private repositories)
5. Generate and copy the token

### 4. Create logs directory
```bash
mkdir -p logs
```

### 5. Test the script manually
```bash
./venv/bin/python run.py
```

This will:
- Pull latest changes from GitHub
- Generate all reports
- Generate static dashboard data
- Publish the latest generated site to the `gh-pages` branch

Generated PNGs, downloaded CSV snapshots, and `web/data/` JSON are ignored on `main` so hourly runs do not grow repository history.

## Automated Execution with Cron

### Setup cron job
```bash
crontab -e
```

Add one of these lines:

**Run every day at 2 AM:**
```cron
0 2 * * * cd ~/Fintech && ~/Fintech/venv/bin/python run.py >> ~/Fintech/logs/reports.log 2>&1
```

**Run every 6 hours:**
```cron
0 */6 * * * cd ~/Fintech && ~/Fintech/venv/bin/python run.py >> ~/Fintech/logs/reports.log 2>&1
```

**Run every hour:**
```cron
0 * * * * cd ~/Fintech && ~/Fintech/venv/bin/python run.py >> ~/Fintech/logs/reports.log 2>&1
```

### View logs
```bash
tail -f logs/reports.log
```

### View last 100 lines of logs
```bash
tail -n 100 logs/reports.log
```

## Troubleshooting

### Check if cron job is running
```bash
grep CRON /var/log/syslog | tail -20
```

### Test git authentication
```bash
cd ~/Fintech
source venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Token loaded!' if os.getenv('GITHUB_TOKEN') else 'Token NOT found')"
```

### Manual git pull/push test
```bash
cd ~/Fintech
git pull
git status
```

### Reinstall dependencies
```bash
cd ~/Fintech
rm -rf venv
./setup_ubuntu.sh
```

## File Structure

```
Fintech/
├── run.py                      # Main script
├── setup_ubuntu.sh             # Setup script for Ubuntu
├── install_all_requirements.py # Installs all requirements
├── requirements.txt            # Root dependencies (python-dotenv)
├── .env                        # Your GitHub token (not committed)
├── .env.example                # Template for .env
├── .gitignore                  # Git ignore rules
├── venv/                       # Virtual environment (not committed)
├── logs/                       # Log files (not committed)
├── Bitcoin/                    # Bitcoin reports
└── Stock/                      # Stock reports
```

## What the automation does

1. **Git Pull**: Updates project with latest source changes
2. **Generate Reports**: Runs all Bitcoin and Stock visualization scripts
3. **Generate Website Data**: Refreshes `web/data/`
4. **Publish Website**: Force-pushes the latest static site to `gh-pages`

All output is logged to `logs/reports.log` for debugging.
