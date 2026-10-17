#!/usr/bin/env python3
"""Initialize one private persistent demo host without printing credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


ENV_KEYS = (
    "BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_ENTERPRISE_ID", "BOX_USER_ID",
    "AWS_REGION", "BEDROCK_MODEL_ID", "ARSIA_DEMO_USERNAME", "ARSIA_DEMO_PASSWORD",
    "ARSIA_ORIGIN_TOKEN", "ARSIA_PUBLIC_ORIGIN", "ARSIA_ALLOWED_HOSTS",
)


def _runtime_secret(client, secret_arn: str, wait_seconds: int) -> dict[str, str]:
    """Wait for the operator to bind the newly allocated CloudFront hostname."""
    deadline = time.monotonic() + wait_seconds
    while True:
        response = client.get_secret_value(SecretId=secret_arn)
        value = json.loads(response["SecretString"])
        if not isinstance(value, dict):
            raise ValueError("The deployment secret must contain a JSON object.")
        origin = urlsplit(str(value.get("ARSIA_PUBLIC_ORIGIN", "")))
        hosts = str(value.get("ARSIA_ALLOWED_HOSTS", "")).split(",")
        ready = origin.scheme == "https" and origin.hostname in {host.strip() for host in hosts} and not origin.path and not origin.query and not origin.fragment
        if ready:
            required = ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_USER_ID", "ARSIA_DEMO_USERNAME", "ARSIA_DEMO_PASSWORD", "ARSIA_ORIGIN_TOKEN")
            if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required):
                raise ValueError("The deployment secret is missing required Box or demo credentials.")
            if len(value["ARSIA_DEMO_PASSWORD"]) < 16 or len(value["ARSIA_ORIGIN_TOKEN"]) < 16:
                raise ValueError("Demo and origin credentials must each contain at least sixteen characters.")
            return {key: str(value[key]) for key in ENV_KEYS if key in value}
        if time.monotonic() >= deadline:
            raise TimeoutError("The HTTPS public origin and exact allowed host were not configured within the bootstrap window.")
        time.sleep(5)


def _private_file(path: Path, contents: str, uid: int, gid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        os.fchmod(handle.fileno(), 0o600)
        os.fchown(handle.fileno(), uid, gid)
        handle.write(contents)


def _readable_runtime_tree(directory: Path) -> None:
    """Permit service reads while preserving root ownership and executables."""
    directory.chmod(0o755)
    for path in directory.rglob("*"):
        if path.is_symlink() or ".local" in path.relative_to(directory).parts or path == directory / ".env":
            continue
        executable = bool(path.stat().st_mode & 0o111)
        path.chmod(0o755 if path.is_dir() or executable else 0o644)


def bootstrap(secret_arn: str, region: str, app_dir: Path, data_dir: Path, wait_seconds: int) -> None:
    os.umask(0o077)
    if not (app_dir / "app" / "main.py").is_file() or not (app_dir / "frontend" / "dist" / "index.html").is_file():
        raise ValueError("The artifact must contain the application and its built frontend.")
    session = boto3.Session(region_name=region)
    client = session.client("secretsmanager", config=Config(retries={"mode": "standard", "total_max_attempts": 3}, connect_timeout=8, read_timeout=20))
    environment = _runtime_secret(client, secret_arn, wait_seconds)
    environment.update(AWS_REGION=region, BEDROCK_MODEL_ID=environment.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"), REVIEW_DATA_DIR=str(data_dir))
    try:
        account = pwd.getpwnam("arsia")
    except KeyError:
        subprocess.run(["useradd", "--system", "--no-create-home", "--shell", "/sbin/nologin", "arsia"], check=True)
        account = pwd.getpwnam("arsia")
    uid, gid = account.pw_uid, account.pw_gid
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chown(data_dir, uid, gid)
    os.chmod(data_dir, 0o700)
    runtime_config = data_dir / "native-config.json"
    runtime_config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chown(runtime_config.parent, uid, gid)
    if not runtime_config.exists():
        seed = json.loads((app_dir / "seed" / "native-config.json").read_text())
        _private_file(runtime_config, json.dumps(seed, indent=2), uid, gid)
    seed_runs = app_dir / "seed" / "runs"
    runs = data_dir / "workbench" / "runs"
    runs.mkdir(parents=True, exist_ok=True, mode=0o700)
    for directory in (runs.parent, runs):
        os.chown(directory, uid, gid)
        os.chmod(directory, 0o700)
    for source in seed_runs.glob("*.json"):
        if not re.fullmatch(r"[a-f0-9]{32}\.json", source.name):
            raise ValueError("A seed run has an invalid file name.")
        destination = runs / source.name
        if not destination.exists():
            seed_run = json.loads(source.read_text())
            if seed_run.get("status") not in {"completed", "failed"}:
                raise ValueError("Only inactive completed or failed demo records may be seeded.")
            _private_file(destination, json.dumps(seed_run, indent=2), uid, gid)
    _private_file(app_dir / ".env", "".join(key + "=" + json.dumps(value) + "\n" for key, value in environment.items()), uid, gid)
    # The seed can contain source excerpts and private record metadata. Once
    # copied into restricted runtime storage it must not remain in public code.
    shutil.rmtree(app_dir / "seed")
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(app_dir / "requirements-local.txt")], cwd=app_dir, check=True, umask=0o022)
    # Correct restrictive inherited modes as well as newly installed package
    # modes. The service can read root-owned code but can write only its data.
    app_dir.parent.chmod(0o755)
    _readable_runtime_tree(app_dir)
    _readable_runtime_tree(app_dir.parent / "venv")
    shutil.rmtree(app_dir.parent / "staging", ignore_errors=True)
    unit = "\n".join((
        "[Unit]", "Description=Arsia authenticated annual review demo", "After=network-online.target", "Wants=network-online.target", "",
        "[Service]", "Type=simple", "User=arsia", "Group=arsia", "WorkingDirectory=" + str(app_dir),
        "Environment=AWS_REGION=" + region, "UnsetEnvironment=AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN",
        "ExecStart=" + sys.executable + " -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --workers 1 --no-access-log",
        "Restart=on-failure", "RestartSec=5", "TimeoutStopSec=1800", "UMask=0077", "NoNewPrivileges=true", "PrivateTmp=true", "",
        "[Install]", "WantedBy=multi-user.target", "",
    ))
    Path("/etc/systemd/system/arsia.service").write_text(unit)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "arsia.service"], check=True)
    print("Arsia service initialized with private persistent state and secret-backed access.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret-arn", required=True)
    parser.add_argument("--region", default="us-east-2")
    parser.add_argument("--app-dir", type=Path, default=Path("/opt/arsia/app"))
    parser.add_argument("--data-dir", type=Path, default=Path("/data"))
    parser.add_argument("--wait-seconds", type=int, default=600)
    args = parser.parse_args()
    try:
        bootstrap(args.secret_arn, args.region, args.app_dir.resolve(), args.data_dir.resolve(), min(600, max(0, args.wait_seconds)))
        return 0
    except (BotoCoreError, ClientError, OSError, ValueError, KeyError, TimeoutError, subprocess.CalledProcessError) as error:
        # Never print SDK payloads, secret JSON, subprocess environments or
        # exceptions that might contain a credential supplied by an operator.
        print("Arsia bootstrap failed (" + type(error).__name__ + "). Inspect service or cloud-init status without exposing secrets.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
