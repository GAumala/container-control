#!/usr/bin/env python3
"""Restricted Docker control, with an unprivileged SSH phase and a root phase."""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

TRUSTED_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SUDO = shutil.which("sudo", path=TRUSTED_PATH)
DOCKER = shutil.which("docker", path=TRUSTED_PATH)
if SUDO is None or DOCKER is None:
    raise RuntimeError("sudo and docker must be available in the trusted system path")
ACTIONS = frozenset(("start", "stop", "restart"))
MAX_LOG_LINES = 500
COMMAND_TIMEOUT_SECONDS = 20
CONTAINER_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


class RequestError(Exception):
    pass


def parse_request(argv: Sequence[str]) -> list[str]:
    if not argv:
        raise RequestError("missing command")
    command = argv[0]
    if command == "list" and len(argv) == 1:
        return [DOCKER, "ps", "--all", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"]
    if command == "status" and len(argv) == 2:
        return [DOCKER, "inspect", "--format", "{{.Name}}\t{{.State.Status}}\t{{.State.Running}}", container_reference(argv[1])]
    if command == "logs" and len(argv) in (2, 3):
        lines = MAX_LOG_LINES if len(argv) == 2 else parse_line_count(argv[2])
        return [DOCKER, "logs", "--tail", str(lines), "--timestamps", container_reference(argv[1])]
    if command in ACTIONS and len(argv) == 2:
        return [DOCKER, command, container_reference(argv[1])]
    raise RequestError("unsupported command")


def container_reference(value: str) -> str:
    if not CONTAINER_REFERENCE.fullmatch(value):
        raise RequestError("invalid container name or ID")
    return value


def parse_line_count(value: str) -> int:
    try:
        lines = int(value, 10)
    except ValueError as exc:
        raise RequestError("log line count must be an integer") from exc
    if not 1 <= lines <= MAX_LOG_LINES:
        raise RequestError(f"log line count must be from 1 to {MAX_LOG_LINES}")
    return lines


def dispatch_ssh_request() -> int:
    """Unprivileged phase: parse SSH's original command, then request one sudo action."""
    try:
        arguments = shlex.split(os.environ.get("SSH_ORIGINAL_COMMAND", ""), posix=True)
    except ValueError:
        print("container-control: invalid SSH command quoting", file=sys.stderr)
        return 64
    if not arguments:
        print("container-control: command required", file=sys.stderr)
        return 64
    environment = {"PATH": TRUSTED_PATH, "LANG": "C", "LC_ALL": "C"}
    os.execve(SUDO, ["sudo", "-n", str(Path(__file__).resolve()), "--internal", *arguments], environment)
    return 125


def run_as_root(argv: Sequence[str]) -> int:
    if not argv or argv[0] != "--internal":
        print("container-control: internal invocation required", file=sys.stderr)
        return 64
    try:
        command = parse_request(argv[1:])
    except RequestError as exc:
        print(f"container-control: {exc}", file=sys.stderr)
        return 64
    environment = {"PATH": TRUSTED_PATH, "LANG": "C", "LC_ALL": "C"}
    try:
        return subprocess.run(command, stdin=subprocess.DEVNULL, env=environment, timeout=COMMAND_TIMEOUT_SECONDS).returncode
    except subprocess.TimeoutExpired:
        print("docker command timed out", file=sys.stderr)
        return 124
    except OSError as exc:
        print(f"cannot execute docker: {exc}", file=sys.stderr)
        return 125


def main(argv: Sequence[str]) -> int:
    return run_as_root(argv) if os.geteuid() == 0 else dispatch_ssh_request()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
