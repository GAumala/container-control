#!/usr/bin/env python3
"""Example constrained SSH client for restricted-docker-control.

Copy this file outside an agent workspace, set the three policy constants below,
and allowlist this script rather than the ssh executable.
"""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

# Deployment policy: edit these values when copying this example.
HOST = "homelab.local"
USER = "devops"
IDENTITY_FILE = Path.home() / ".ssh" / "id_ed25519_container_control"
KNOWN_HOSTS_FILE = Path.home() / ".ssh" / "known_hosts"
TRUSTED_PATH = "/usr/local/bin:/usr/bin:/bin"
MAX_LOG_LINES = 500
SSH = shutil.which("ssh", path=TRUSTED_PATH)
CONTAINER_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
ACTIONS = frozenset(("start", "stop", "restart"))


class RequestError(Exception):
    pass


def parse_request(argv: Sequence[str]) -> list[str]:
    if not argv:
        raise RequestError("missing command")
    command = argv[0]
    if command == "list" and len(argv) == 1:
        return ["list"]
    if command == "status" and len(argv) == 2:
        return [command, container_reference(argv[1])]
    if command == "logs" and len(argv) in (2, 3):
        lines = MAX_LOG_LINES if len(argv) == 2 else line_count(argv[2])
        return [command, container_reference(argv[1]), str(lines)]
    if command in ACTIONS and len(argv) == 2:
        return [command, container_reference(argv[1])]
    raise RequestError("unsupported command")


def container_reference(value: str) -> str:
    if not CONTAINER_REFERENCE.fullmatch(value):
        raise RequestError("invalid container name or ID")
    return value


def line_count(value: str) -> int:
    try:
        count = int(value, 10)
    except ValueError as exc:
        raise RequestError("log line count must be an integer") from exc
    if not 1 <= count <= MAX_LOG_LINES:
        raise RequestError(f"log line count must be from 1 to {MAX_LOG_LINES}")
    return count


def main(argv: Sequence[str]) -> int:
    try:
        request = parse_request(argv)
    except RequestError as exc:
        print(f"container-client: {exc}", file=sys.stderr)
        return 64
    if SSH is None:
        print("container-client: ssh not found in trusted path", file=sys.stderr)
        return 69
    if not IDENTITY_FILE.is_file() or not KNOWN_HOSTS_FILE.is_file():
        print("container-client: identity file or known_hosts file is missing", file=sys.stderr)
        return 66
    command = [
        SSH,
        "-F", "/dev/null",
        "-i", str(IDENTITY_FILE),
        "-o", "IdentitiesOnly=yes",
        "-o", "BatchMode=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "ForwardAgent=no",
        "-o", "ClearAllForwardings=yes",
        "-o", "RequestTTY=no",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={KNOWN_HOSTS_FILE}",
        "-o", "UpdateHostKeys=no",
        f"{USER}@{HOST}",
        shlex.join(request),
    ]
    environment = {"PATH": TRUSTED_PATH, "LANG": "C", "LC_ALL": "C"}
    try:
        return subprocess.run(command, stdin=subprocess.DEVNULL, env=environment).returncode
    except OSError as exc:
        print(f"container-client: cannot execute ssh: {exc}", file=sys.stderr)
        return 69


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
