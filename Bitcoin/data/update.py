"""Incrementally refresh Bitcoin CSV inputs from Wicked Smart Bitcoin."""

import hashlib
import json
import os
from pathlib import Path
import time

import requests

# Configuration
BASE_URL = "https://raw.githubusercontent.com/w-s-bitcoin/animations/main/assets"
SAVE_DIR = "bitcoin_csv_data"          # ← folder where files will be saved
DELAY = 0.4                         # seconds between requests (be nice to GitHub)
METADATA_PATH = Path(SAVE_DIR) / ".download_metadata.json"

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

def file_sha256(path):
    """Return a streaming SHA-256 digest without loading large CSVs into RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_metadata():
    """Load conditional-request metadata, tolerating an absent/corrupt cache."""
    try:
        payload = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def save_metadata(metadata):
    """Atomically persist download validators for the next hourly check."""
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    partial_path = METADATA_PATH.with_suffix(".json.part")
    partial_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(partial_path, METADATA_PATH)


def download_file(url, save_path, metadata_entry=None):
    """Download one file conditionally and return ``(success, changed, metadata)``."""
    is_update = save_path.exists()
    action = "Updating" if is_update else "Downloading"
    print(f"{action}: {save_path.name} ... ", end="", flush=True)
    partial_path = save_path.with_name(f"{save_path.name}.part")
    request_headers = {}
    metadata_entry = metadata_entry if isinstance(metadata_entry, dict) else {}
    if is_update and metadata_entry.get("etag"):
        request_headers["If-None-Match"] = metadata_entry["etag"]
    if is_update and metadata_entry.get("last_modified"):
        request_headers["If-Modified-Since"] = metadata_entry["last_modified"]

    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=30, headers=request_headers) as response:
            if response.status_code == 304 and is_update:
                print("[OK] unchanged")
                return True, False, metadata_entry
            response.raise_for_status()
            with open(partial_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            downloaded_hash = file_sha256(partial_path)
            existing_hash = metadata_entry.get("sha256")
            if is_update and not existing_hash:
                existing_hash = file_sha256(save_path)
            changed = not is_update or downloaded_hash != existing_hash
            if changed:
                os.replace(partial_path, save_path)
            else:
                partial_path.unlink(missing_ok=True)

            updated_metadata = {
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "sha256": downloaded_hash,
                "url": response.url,
            }

        print("[OK] updated" if changed else "[OK] unchanged")
        return True, changed, updated_metadata

    except Exception as e:
        partial_path.unlink(missing_ok=True)
        print(f"[FAILED] {e}")
        return False, False, metadata_entry


def main():
    """Download/update all Bitcoin data files."""
    print(f"Target directory: {Path(SAVE_DIR).resolve()}\n")
    print(f"Updating {len(FILES)} files...\n")

    metadata = load_metadata()
    success_count = 0
    changed_count = 0
    
    for filename in FILES:
        url = f"{BASE_URL}/{filename}"
        save_path = Path(SAVE_DIR) / filename
        
        success, changed, updated_metadata = download_file(url, save_path, metadata.get(filename))
        if success:
            success_count += 1
            metadata[filename] = updated_metadata
        if changed:
            changed_count += 1
        
        time.sleep(DELAY)  # polite delay
    
    print("\n" + "="*60)
    save_metadata(metadata)
    print("Download finished!")
    print(f"Successful: {success_count}/{len(FILES)} files")
    print(f"Changed: {changed_count}/{len(FILES)} files")
    print(f"Saved to: {Path(SAVE_DIR).resolve()}")
    print("="*60)

    if success_count != len(FILES):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
