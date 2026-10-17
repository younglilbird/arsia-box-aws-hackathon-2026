"""Offline checks for the hosted demo's persistent configuration and modes."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.hosted_bootstrap import _readable_runtime_tree, _runtime_secret, bootstrap


def deployment_secret():
    return {"BOX_CLIENT_ID": "example-id", "BOX_CLIENT_SECRET": "example-secret", "BOX_USER_ID": "123",
            "ARSIA_DEMO_USERNAME": "judge", "ARSIA_DEMO_PASSWORD": "a" * 32, "ARSIA_ORIGIN_TOKEN": "b" * 32,
            "ARSIA_PUBLIC_ORIGIN": "https://example.cloudfront.net", "ARSIA_ALLOWED_HOSTS": "example.cloudfront.net"}


def test_secret_allowlist_never_copies_local_aws_credentials():
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": json.dumps({**deployment_secret(), "AWS_PROFILE": "local-only", "AWS_SECRET_ACCESS_KEY": "must-not-copy"})}
    environment = _runtime_secret(client, "secret-arn", 0)
    assert "AWS_PROFILE" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert environment["ARSIA_PUBLIC_ORIGIN"] == "https://example.cloudfront.net"


def test_runtime_modes_allow_service_imports_without_exposing_env(tmp_path):
    runtime = tmp_path / "venv"
    package = runtime / "lib" / "site-packages"
    package.mkdir(parents=True, mode=0o700)
    source = package / "module.py"
    source.write_text("VALUE = 1\n")
    source.chmod(0o600)
    executable = runtime / "runner"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o700)
    env = runtime / ".env"
    env.write_text("PRIVATE=secret\n")
    env.chmod(0o600)
    _readable_runtime_tree(runtime)
    assert runtime.stat().st_mode & 0o777 == 0o755
    assert package.stat().st_mode & 0o777 == 0o755
    assert source.stat().st_mode & 0o777 == 0o644
    assert executable.stat().st_mode & 0o777 == 0o755
    assert env.stat().st_mode & 0o777 == 0o600


def test_bootstrap_seeds_native_configuration_under_persistent_data(tmp_path):
    app = tmp_path / "app"
    data = tmp_path / "persistent"
    for directory in (app / "app", app / "frontend" / "dist", app / "seed" / "runs", tmp_path / "venv"):
        directory.mkdir(parents=True)
    (app / "app" / "main.py").write_text("# application\n")
    (app / "frontend" / "dist" / "index.html").write_text("<html></html>")
    (app / "seed" / "native-config.json").write_text('{"root_folder_id":"123"}')
    (app / "requirements-local.txt").write_text("")
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": json.dumps(deployment_secret())}
    session = Mock()
    session.client.return_value = client
    account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
    previous_umask = os.umask(0o022)
    try:
        with patch("scripts.hosted_bootstrap.boto3.Session", return_value=session), patch("scripts.hosted_bootstrap.pwd.getpwnam", return_value=account), patch("scripts.hosted_bootstrap.os.chown"), patch("scripts.hosted_bootstrap.os.fchown"), patch("scripts.hosted_bootstrap.subprocess.run") as command, patch.object(Path, "write_text") as write_unit:
            bootstrap("secret-arn", "us-east-2", app, data, 0)
        assert json.loads((data / "native-config.json").read_text()) == {"root_folder_id": "123"}
        assert not (app / ".local" / "native-config.json").exists()
        assert (app / ".env").stat().st_mode & 0o777 == 0o600
        assert not (app / "seed").exists()
        unit = write_unit.call_args.args[0]
        assert "--workers 1" in unit
        assert "TimeoutStopSec=1800" in unit
        assert any(call.kwargs.get("umask") == 0o022 for call in command.call_args_list)
    finally:
        os.umask(previous_umask)
