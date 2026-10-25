"""Helper for running an external tool as a subprocess, safely.

Tools are invoked through the current Python interpreter (`python -m <tool>`)
so they resolve without depending on PATH. Timeouts and missing tools are
turned into normal return values, not exceptions.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ProcResult:
    ok: bool                 # the process ran to completion (any exit code)
    returncode: int | None
    stdout: str
    stderr: str
    error: str | None = None  # set when the process could not be run / timed out


def run_module(module_args: list[str], *, cwd: str | None = None,
               timeout: int = 180) -> ProcResult:
    """Run `python -m <module_args...>` and capture output.

    Never raises for the common failure modes (missing module, timeout); returns
    a ProcResult with error set instead.
    """
    cmd = [sys.executable, "-m", *module_args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ProcResult(ok=False, returncode=None, stdout="", stderr="",
                          error=f"timed out after {timeout}s")
    except (OSError, ValueError) as exc:  # pragma: no cover - defensive
        return ProcResult(ok=False, returncode=None, stdout="", stderr="",
                          error=f"could not start tool: {exc}")
    return ProcResult(ok=True, returncode=proc.returncode,
                      stdout=proc.stdout, stderr=proc.stderr)
