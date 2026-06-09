# download_bitcoin_github_csvs.py
import requests
import os
from pathlib import Path
import time

# Configuration
BASE_URL = "https://raw.githubusercontent.com/w-s-bitcoin/animations/main/assets"
SAVE_DIR = "bitcoin_csv_data"          # ← folder where files will be saved
DELAY = 0.4                         # seconds between requests (be nice to GitHub)

FILES = [
    "bitcoin_node_history.csv",
    "btcusd_10m_prices.csv",
    "daily_price.csv",
    "node_software_counts_grouped.csv",
    "node_software_counts_with_reachability.csv",
]

# All block data ranges (0–999999)
for i in range(10):
    start = i * 100000
    end = start + 99999
    filename = f"block_data_{start}_{end}.csv"
    FILES.append(filename)

def download_file(url, save_path, is_update=False):
    """Download file with progress indication"""
    action = "Updating" if is_update else "Downloading"
    print(f"{action}: {save_path.name} ... ", end="", flush=True)
    
    try:
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()
        
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print("[OK] done")
        return True

    except Exception as e:
        print(f"[FAILED] {e}")
        return False


def main():
    """Download/update all Bitcoin data files."""
    print(f"Target directory: {Path(SAVE_DIR).resolve()}\n")
    print(f"Updating {len(FILES)} files...\n")
    
    success_count = 0
    
    for filename in FILES:
        url = f"{BASE_URL}/{filename}"
        save_path = Path(SAVE_DIR) / filename
        
        # Always update all files
        is_update = save_path.exists()
        if download_file(url, save_path, is_update=is_update):
            success_count += 1
        
        time.sleep(DELAY)  # polite delay
    
    print("\n" + "="*60)
    print(f"Download finished!")
    print(f"Successful: {success_count}/{len(FILES)} files")
    print(f"Saved to: {Path(SAVE_DIR).resolve()}")
    print("="*60)


if __name__ == "__main__":
    main()