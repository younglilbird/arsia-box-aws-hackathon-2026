#!/usr/bin/env python3
"""Check the public source snapshot without printing credential values."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {".local", ".venv", ".aws", ".box", "node_modules", "work", "secrets", "credentials"}
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".md", ".txt", ".yaml", ".yml", ".json", ".html", ".css", ".sh", ".toml", ".mjs"}
SECRET_PATTERN = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def local_secret_values() -> list[str]:
    path = ROOT / ".env"
    if not path.is_file():
        return []
    values = []
    for line in path.read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        if len(value) > 12 and any(word in key.upper() for word in ("SECRET", "TOKEN", "PASSWORD", "ACCESS_KEY")):
            values.append(value)
    return values


def main() -> int:
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    secrets = local_secret_values()
    problems = []
    checked = 0
    for name in filter(None, names):
        path = ROOT / name
        if PRIVATE_PARTS.intersection(Path(name).parts) or (path.name.startswith(".env") and path.name != ".env.example") or path.suffix in {".pem", ".key"}:
            problems.append(f"{name}: private runtime or credential file is tracked")
            continue
        if path.suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        content = path.read_text()
        checked += 1
        if re.search(r"[\u3400-\u9fff]", content):
            problems.append(f"{name}: project text must remain English")
        if SECRET_PATTERN.search(content) or any(value in content for value in secrets):
            problems.append(f"{name}: possible credential value")
    for problem in problems:
        print(problem)
    print(f"Checked {checked} tracked text files; {len(problems)} problems.")
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
