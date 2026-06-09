#!/usr/bin/env python3
"""
Install all Python requirements from subdirectories.
Cross-platform script to find and install all requirements.txt files efficiently.
Collects all unique requirements first, then installs each package only once.
"""

import subprocess
import sys
from pathlib import Path


def parse_requirements_file(req_file):
    """Parse a requirements.txt file and return set of requirement lines."""
    requirements = set()
    try:
        with open(req_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    requirements.add(line)
    except Exception as e:
        print(f"Warning: Could not read {req_file}: {e}")
    return requirements


def collect_all_requirements(root_dir, search_dirs):
    """Collect all unique requirements from all requirements.txt files."""
    all_requirements = set()
    req_files = []

    for search_dir in search_dirs:
        dir_path = root_dir / search_dir
        if dir_path.exists():
            req_files.extend(sorted(dir_path.rglob("requirements.txt")))
        else:
            print(f"Warning: Directory '{search_dir}' not found, skipping...")

    if not req_files:
        return None, 0

    print(f"Found {len(req_files)} requirements.txt files")
    print("Collecting unique requirements...\n")

    for req_file in req_files:
        requirements = parse_requirements_file(req_file)
        if requirements:
            all_requirements.update(requirements)
            print(f"  - {req_file.relative_to(root_dir)} ({len(requirements)} requirements)")

    return all_requirements, len(req_files)


def install_requirements(requirements):
    """Install all requirements at once."""
    if not requirements:
        print("No requirements to install.")
        return False

    # Create a temporary requirements file with all unique requirements
    temp_req_file = Path(__file__).parent / "temp_combined_requirements.txt"

    try:
        # Write all unique requirements to temp file
        with open(temp_req_file, 'w', encoding='utf-8') as f:
            for req in sorted(requirements):
                f.write(f"{req}\n")

        print(f"\nInstalling {len(requirements)} unique packages...")
        print("="*60)

        # Install all requirements at once
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", str(temp_req_file)
        ])

        print("="*60)
        return True

    except subprocess.CalledProcessError:
        print("\nERROR: Installation failed")
        return False
    except KeyboardInterrupt:
        print("\n\nINTERRUPTED: Installation cancelled by user")
        sys.exit(1)
    finally:
        # Clean up temp file
        if temp_req_file.exists():
            temp_req_file.unlink()


def main():
    """Find and install all requirements efficiently."""
    print("Installing all Python requirements from subdirectories...\n")

    root_dir = Path(__file__).parent
    search_dirs = ["Bitcoin", "Stock"]

    # Check for root requirements.txt
    root_req_file = root_dir / "requirements.txt"
    if root_req_file.exists():
        print("Installing root requirements first...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "-r", str(root_req_file)
            ])
            print("✓ Root requirements installed\n")
        except subprocess.CalledProcessError:
            print("✗ Failed to install root requirements\n")

    # Collect all unique requirements
    all_requirements, file_count = collect_all_requirements(root_dir, search_dirs)

    if all_requirements is None:
        print("No requirements.txt files found in Bitcoin or Stock directories.")
        return

    print(f"\nTotal unique requirements: {len(all_requirements)}")
    print(f"Total requirements files: {file_count}")

    # Install all requirements at once
    success = install_requirements(all_requirements)

    print("\n" + "="*60)
    if success:
        print("Installation complete!")
        print(f"Successfully installed {len(all_requirements)} unique packages")
    else:
        print("Installation failed or was incomplete")
    print("="*60)


if __name__ == "__main__":
    main()
