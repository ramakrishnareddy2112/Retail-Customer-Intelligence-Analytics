"""Download and extract Online Retail II from the official UCI repository."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_analytics.config import (  # noqa: E402
    RAW_ARCHIVE_PATH,
    RAW_WORKBOOK_PATH,
    UCI_DATASET_URL,
    ensure_data_directories,
)


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    """Download a URL with a descriptive user agent and progress output."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Retail-Customer-Intelligence/0.1 (internship project)"},
    )
    print(f"Downloading official UCI dataset to {destination} ...")
    with urllib.request.urlopen(request, timeout=120) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        with destination.open("wb") as file_handle:
            while chunk := response.read(1024 * 1024):
                file_handle.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"  {downloaded / total:6.1%}", end="\r")
    print("  download complete")


def extract_workbook(archive_path: Path, output_directory: Path) -> Path:
    """Safely extract the expected workbook from the UCI ZIP archive."""
    with zipfile.ZipFile(archive_path) as archive:
        workbook_members = [
            member
            for member in archive.namelist()
            if Path(member).suffix.lower() in {".xlsx", ".xls"}
        ]
        if len(workbook_members) != 1:
            raise RuntimeError(
                f"Expected one workbook in archive, found: {workbook_members}"
            )
        member = workbook_members[0]
        target = output_directory / Path(member).name
        with archive.open(member) as source, target.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                destination.write(chunk)
    return target


def main() -> None:
    """Acquire the raw workbook without modifying its contents."""
    ensure_data_directories()

    if RAW_WORKBOOK_PATH.exists():
        print(f"Raw workbook already exists: {RAW_WORKBOOK_PATH}")
        print(f"SHA-256: {sha256(RAW_WORKBOOK_PATH)}")
        return

    if not RAW_ARCHIVE_PATH.exists():
        download_file(UCI_DATASET_URL, RAW_ARCHIVE_PATH)
    else:
        print(f"Using existing archive: {RAW_ARCHIVE_PATH}")

    extracted = extract_workbook(RAW_ARCHIVE_PATH, RAW_ARCHIVE_PATH.parent)
    if extracted != RAW_WORKBOOK_PATH:
        extracted.replace(RAW_WORKBOOK_PATH)

    print(f"Extracted workbook: {RAW_WORKBOOK_PATH}")
    print(f"Size: {RAW_WORKBOOK_PATH.stat().st_size:,} bytes")
    print(f"SHA-256: {sha256(RAW_WORKBOOK_PATH)}")


if __name__ == "__main__":
    main()
