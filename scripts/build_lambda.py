"""Build the Lambda deployment zip (Linux-compatible, from any OS).

Usage::

    python scripts/build_lambda.py [--output dist/lambda.zip]

Downloads ``manylinux`` wheels (so binary extensions like pydantic-core,
psycopg-binary, bcrypt match the Lambda runtime), installs them into a staging
directory, overlays the app source, prunes packages the Lambda runtime
provides (boto3/botocore/s3transfer), and zips the result.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "dist" / "lambda"
WHEELS = ROOT / "dist" / "wheels"
DEFAULT_OUTPUT = ROOT / "dist" / "lambda.zip"

# Bundled with the Lambda runtime — pinning them in the zip causes conflicts.
RUNTIME_PROVIDED = {"boto3", "botocore", "s3transfer"}

# Top-level entries of the repo to ship in the zip.
APP_ENTRIES = (
    "api",
    "agents",
    "alembic",
    "alembic.ini",
    "common",
    "database",
    "models",
    "orchestration",
    "prompts",
    "repositories",
    "scripts",
    "sdk",
    "services",
)

# Binary wheels must match the Lambda runtime: Python 3.12 on Amazon Linux
# (glibc >= 2.17, x86_64).
PIP_DOWNLOAD_ARGS = [
    "--only-binary=:all:",
    "--platform", "manylinux2014_x86_64",
    "--platform", "manylinux_2_28_x86_64",
    "--python-version", "312",
    "--implementation", "cp",
]


def download_linux_wheels() -> None:
    """Resolve deps as manylinux wheels so the zip runs on the Lambda runtime."""
    shutil.rmtree(WHEELS, ignore_errors=True)
    WHEELS.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "download", "--dest", str(WHEELS),
         *PIP_DOWNLOAD_ARGS, str(ROOT)],
        check=True,
    )


def install_wheels(staging: Path) -> None:
    """Extract wheels into the staging dir (bypasses pip's host-platform check)."""
    wheels = sorted(WHEELS.glob("*.whl"))
    if not wheels:
        raise RuntimeError("no wheels downloaded — run download first")
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(staging)
    print(f"installed {len(wheels)} wheels into {staging}")


def copy_app(staging: Path) -> None:
    for name in APP_ENTRIES:
        src = ROOT / name
        dst = staging / name
        if src.is_dir():
            shutil.copytree(
                src, dst, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        elif src.is_file():
            shutil.copy2(src, dst)


def prune_runtime_provided(staging: Path) -> None:
    for pkg in RUNTIME_PROVIDED:
        for pattern in (pkg, f"{pkg}-*.dist-info"):
            for path in staging.glob(pattern):
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)


def build_zip(staging: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging))
    print(f"lambda zip: {output} ({output.stat().st_size / 1024:.0f} KiB)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Lambda deployment zip")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    download_linux_wheels()
    install_wheels(STAGING)
    copy_app(STAGING)
    prune_runtime_provided(STAGING)
    build_zip(STAGING, args.output)
    shutil.rmtree(STAGING, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
