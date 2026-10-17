#!/usr/bin/env python3
"""Package prebuilt Linux dependencies and the native worker, excluding secrets."""
import argparse
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("__init__.py", "config.py", "box_client.py", "guidelines.py", "evaluation.py", "workflow.py", "exports.py", "native.py", "cloud.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (args.dependencies / "boto3" / "__init__.py").is_file():
        parser.error("Build Linux dependencies from requirements-lambda.txt first.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    uncompressed = 0
    with ZipFile(args.output, "w", compression=ZIP_DEFLATED) as archive:
        for path in args.dependencies.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            name = path.relative_to(args.dependencies)
            if name.parts[0] == "bin":
                continue
            archive.write(path, str(name))
            uncompressed += path.stat().st_size
        for name in MODULES:
            path = ROOT / "app" / name
            archive.write(path, "app/" + name)
            uncompressed += path.stat().st_size
    if uncompressed > 250 * 1024 * 1024:
        parser.error("The package exceeds Lambda's uncompressed size limit.")
    print(f"Created {args.output.name}: {args.output.stat().st_size:,} bytes zipped, {uncompressed:,} bytes expanded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
