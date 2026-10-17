#!/usr/bin/env python3
"""Check Box authentication and folder access without printing credentials."""

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CheckError(Exception):
    pass


def load_config(path):
    config = {}
    if path.is_file():
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise CheckError("Invalid configuration at line {}.".format(number))
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            config[key.strip()] = value
    for key in ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_ENTERPRISE_ID", "BOX_ACCESS_TOKEN"):
        if os.environ.get(key):
            config[key] = os.environ[key]
    return config


def request_box(path, label, token=None, form=None):
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urlencode(form).encode("utf-8")
    request = Request("https://api.box.com" + path, data=body, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        # Error bodies may contain request details; do not print them.
        raise CheckError("{}: Box returned HTTP {}.".format(label, error.code)) from None
    except URLError:
        raise CheckError("{}: could not connect to Box.".format(label)) from None
    except (ValueError, OSError, TimeoutError):
        raise CheckError("{}: Box did not return a valid response.".format(label)) from None


def run(config):
    required = ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_ENTERPRISE_ID")
    if all(config.get(key) for key in required):
        response = request_box("/oauth2/token", "CCG authentication", form={
            "grant_type": "client_credentials",
            "client_id": config["BOX_CLIENT_ID"],
            "client_secret": config["BOX_CLIENT_SECRET"],
            "box_subject_type": "enterprise",
            "box_subject_id": config["BOX_ENTERPRISE_ID"],
        })
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise CheckError("CCG authentication: no access token was returned.")
        auth_mode = "client_credentials"
    elif config.get("BOX_ACCESS_TOKEN"):
        token = config["BOX_ACCESS_TOKEN"]
        auth_mode = "access_token"
    else:
        missing = [key for key in required if not config.get(key)]
        raise CheckError("Missing local configuration: {}.".format(", ".join(missing)))

    identity = request_box("/2.0/users/me?fields=id,type", "Current user", token=token)
    if not isinstance(identity, dict) or not identity.get("id"):
        raise CheckError("Current user: no user ID was returned.")
    folder = request_box(
        "/2.0/folders/0/items?limit=1&fields=id,type", "Root folder listing", token=token)
    if not isinstance(folder, dict) or not isinstance(folder.get("entries"), list):
        raise CheckError("Root folder listing: no entries list was returned.")
    return {
        "status": "passed",
        "authentication": auth_mode,
        "checks": ["authenticate", "get_current_user", "list_root_folder"],
        "writes_performed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path,
                        default=Path(__file__).resolve().parents[1] / ".env")
    args = parser.parse_args()
    try:
        result = run(load_config(args.env_file))
    except (CheckError, OSError) as error:
        message = str(error) if isinstance(error, CheckError) else "Cannot read local configuration."
        print(json.dumps({"status": "failed", "message": message}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
