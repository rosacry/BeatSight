#!/usr/bin/env python3
"""
Download External Benchmark Datasets

This script helps download the external benchmark datasets for validation:
1. IDMT-SMT-Drums - Freely available from Fraunhofer IDMT
2. ENST-Drums - Requires registration at IRCAM

Usage:
    python tools/download_benchmarks.py --dataset idmt --output-dir data/benchmarks
    python tools/download_benchmarks.py --dataset enst --output-dir data/benchmarks
"""

import argparse
import os
import sys
import zipfile
import tarfile
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# IDMT-SMT-Drums is freely available on Zenodo
# Old URL (no longer works): https://www.idmt.fraunhofer.de/content/dam/idmt/downloads/IDMT-SMT-DRUMS-V2.zip
# New Zenodo location: https://zenodo.org/record/7544164
IDMT_ZENODO_URL = "https://zenodo.org/records/7544164/files/IDMT-SMT-DRUMS-V2.zip?download=1"

# ENST-Drums requires registration - provide instructions
ENST_INFO = """
ENST-Drums requires registration at IRCAM:

1. Go to: https://perso.telecom-paristech.fr/griMDELFRN/ENST-drums/
2. Fill out the download form
3. Download the dataset (usually arrives via email)
4. Extract to: {output_dir}/ENST-Drums/

Alternative direct link (if still available):
http://perso.telecom-paristech.fr/grimdelf/ENST-drums/ENST-drums-public.zip

The dataset structure should be:
ENST-Drums/
    drummer_1/
        audio/
            accompaniment/  (full mix)
            drums only/     (isolated drums - use this!)
        annotation/
    drummer_2/
    drummer_3/
"""


def download_file(url: str, output_path: str, chunk_size: int = 8192) -> bool:
    """Download a file with progress."""
    print(f"Downloading: {url}")
    print(f"To: {output_path}")
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = downloaded / total_size * 100
                        mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        print(f"\r  Progress: {mb:.1f}/{total_mb:.1f} MB ({pct:.1f}%)", end='')
        
        print()  # newline
        return True
        
    except Exception as e:
        print(f"Download failed: {e}")
        return False


def extract_archive(archive_path: str, output_dir: str) -> bool:
    """Extract zip or tar archive."""
    print(f"Extracting: {archive_path}")
    
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(output_dir)
        elif archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
            with tarfile.open(archive_path, 'r:gz') as tf:
                tf.extractall(output_dir)
        elif archive_path.endswith('.tar'):
            with tarfile.open(archive_path, 'r') as tf:
                tf.extractall(output_dir)
        else:
            print(f"Unknown archive format: {archive_path}")
            return False
        
        print(f"Extracted to: {output_dir}")
        return True
        
    except Exception as e:
        print(f"Extraction failed: {e}")
        return False


def download_idmt(output_dir: str) -> bool:
    """Download IDMT-SMT-Drums dataset."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = output_dir / "IDMT-SMT-DRUMS.zip"
    
    print("=" * 60)
    print("DOWNLOADING IDMT-SMT-Drums")
    print("=" * 60)
    print()
    print("Source: Zenodo (Fraunhofer IDMT)")
    print("Size: ~500 MB")
    print("Contents: Drum loops with onset annotations")
    print()
    
    # Check if already exists (check for both possible names)
    idmt_dir = output_dir / "IDMT-SMT-DRUMS"
    idmt_dir_v2 = output_dir / "IDMT-SMT-DRUMS-V2"
    if idmt_dir.exists():
        print(f"Dataset already exists at: {idmt_dir}")
        return True
    if idmt_dir_v2.exists():
        print(f"Dataset already exists at: {idmt_dir_v2}")
        return True
    
    # Download from Zenodo
    if not HAS_REQUESTS:
        print("ERROR: 'requests' package not installed.")
        print("Install with: pip install requests")
        print(f"\nOr download manually from:\n  {IDMT_ZENODO_URL}")
        return False
    
    if not download_file(IDMT_ZENODO_URL, str(zip_path)):
        print("\nDownload failed. You can try downloading manually:")
        print(f"  https://zenodo.org/record/7544164")
        return False
    
    # Extract
    if not extract_archive(str(zip_path), str(output_dir)):
        return False
    
    # Cleanup zip
    print("Cleaning up archive...")
    zip_path.unlink()
    
    print()
    print("IDMT-SMT-Drums downloaded successfully!")
    print(f"Location: {idmt_dir}")
    return True


def download_enst(output_dir: str) -> bool:
    """Provide instructions for ENST-Drums download."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("ENST-Drums DOWNLOAD INSTRUCTIONS")
    print("=" * 60)
    print(ENST_INFO.format(output_dir=output_dir))
    
    enst_dir = output_dir / "ENST-Drums"
    if enst_dir.exists():
        # Count drummers
        drummers = [d for d in enst_dir.iterdir() if d.is_dir() and d.name.startswith('drummer')]
        if drummers:
            print(f"\nDataset already exists at: {enst_dir}")
            print(f"Found {len(drummers)} drummer directories")
            return True
    
    print("\nAfter downloading, extract to:")
    print(f"  {enst_dir}")
    
    # Try the public link
    public_url = "http://perso.telecom-paristech.fr/grimdelf/ENST-drums/ENST-drums-public.zip"
    
    print(f"\nAttempting public download link...")
    
    if HAS_REQUESTS:
        try:
            response = requests.head(public_url, timeout=10)
            if response.status_code == 200:
                print("Public link is available!")
                zip_path = output_dir / "ENST-drums-public.zip"
                
                if download_file(public_url, str(zip_path)):
                    if extract_archive(str(zip_path), str(output_dir)):
                        zip_path.unlink()
                        print("\nENST-Drums downloaded successfully!")
                        return True
            else:
                print(f"Public link not available (status: {response.status_code})")
                print("Please use the registration method above.")
        except Exception as e:
            print(f"Could not access public link: {e}")
            print("Please use the registration method above.")
    
    return False


def main():
    parser = argparse.ArgumentParser(description="Download external benchmark datasets")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        choices=["idmt", "enst", "all"],
        help="Dataset to download",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/benchmarks",
        help="Output directory for datasets",
    )
    
    args = parser.parse_args()
    
    success = True
    
    if args.dataset in ("idmt", "all"):
        if not download_idmt(args.output_dir):
            success = False
    
    if args.dataset in ("enst", "all"):
        if not download_enst(args.output_dir):
            success = False
    
    if success:
        print("\n" + "=" * 60)
        print("DOWNLOAD COMPLETE")
        print("=" * 60)
        print("\nTo run benchmarks:")
        print(f"  python tools/evaluate_external.py --dataset idmt --data-dir {args.output_dir}/IDMT-SMT-DRUMS-V2")
        print(f"  python tools/evaluate_external.py --dataset enst --data-dir {args.output_dir}/ENST-Drums")
    else:
        print("\nSome downloads failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
