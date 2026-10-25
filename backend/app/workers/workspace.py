"""Prepare an isolated workspace to scan for repository projects.

A repository project can point at either:
- an existing local directory (used directly, read-only), or
- a remote git URL (shallow-cloned into a disposable temp directory).

Cloned content is untrusted: we only read it with scanner tools, never execute
it. The caller must call cleanup() when done.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable


@dataclass
class Workspace:
    path: str | None
    cleanup: Callable[[], None]
    note: str
    error: str | None = None


def _noop() -> None:
    pass


def prepare_repo_workspace(repo_url: str | None, *, timeout: int = 120) -> Workspace:
    """Return a Workspace for a repository project."""
    if not repo_url:
        return Workspace(None, _noop, "no repository location", error="no repo_url")

    # Case 1: a local directory path (or file:// URL) that exists.
    local = repo_url
    if local.startswith("file://"):
        local = local[len("file://"):]
    if os.path.isdir(local):
        return Workspace(os.path.realpath(local), _noop,
                         f"scanned local directory (read-only): {local}")

    # Case 2: a remote git URL -> shallow clone into a disposable temp dir.
    if _looks_like_git_url(repo_url):
        if shutil.which("git") is None:
            return Workspace(None, _noop, "git not available",
                             error="git is not installed; cannot clone remote repository")
        tmp = tempfile.mkdtemp(prefix="aipentest_ws_")

        def cleanup() -> None:
            shutil.rmtree(tmp, ignore_errors=True)

        try:
            proc = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, tmp],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            cleanup()
            return Workspace(None, _noop, "clone timed out", error="git clone timed out")
        if proc.returncode != 0:
            cleanup()
            return Workspace(None, _noop, "clone failed",
                             error=f"git clone failed: {proc.stderr.strip()[:300]}")
        return Workspace(tmp, cleanup, f"shallow-cloned {repo_url} into a disposable workspace")

    return Workspace(None, _noop, "unrecognized repository location",
                     error=f"cannot resolve repository location: {repo_url}")


def _looks_like_git_url(url: str) -> bool:
    return (
        url.startswith(("http://", "https://", "git://", "ssh://"))
        or url.endswith(".git")
        or url.startswith("git@")
    )
