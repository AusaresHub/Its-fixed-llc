"""
pipeline.py — run the CLI pipeline (lead_finder.py / demos.py) from the dashboard.

These shell out to the root scripts, so they only work on a host that has the full
repo checked out (i.e. locally). On the VPS the Docker image only contains
phase4_backend/, so PIPELINE_ENABLED defaults off there and these endpoints 403.

Streaming: each runner is a generator yielding stdout lines, which routes.py relays
as Server-Sent Events. All arguments are validated and passed as an argv list
(never shell=True) so user input can't inject commands.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from . import db

REPO_ROOT = Path(os.environ.get("REPO_ROOT", db._REPO_ROOT))

_CATEGORY_RE = re.compile(r"^[A-Za-z0-9 ,/&'\-]{2,60}$")
_ZIP_RE      = re.compile(r"^\d{5}$")
_LEAD_RE     = re.compile(r"^[A-Za-z0-9 .,'&\-]{2,80}$")


def enabled() -> bool:
    return os.environ.get("PIPELINE_ENABLED", "").lower() in ("1", "true", "yes")


class PipelineError(Exception):
    pass


def _ensure_enabled() -> None:
    if not enabled():
        raise PipelineError(
            "Pipeline execution is disabled on this host (set PIPELINE_ENABLED=true "
            "where the full repo is checked out)."
        )


def _stream(argv: list[str]) -> "Iterator[str]":
    """Run a command from REPO_ROOT, yielding combined stdout/stderr lines."""
    script = argv[1] if len(argv) > 1 else "?"
    if not (REPO_ROOT / Path(script).name).exists():
        yield f"❌  Script not found at repo root: {script}"
        return
    yield f"$ {' '.join(argv)}\n"
    proc = subprocess.Popen(
        argv, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        yield line.rstrip("\n")
    proc.wait()
    yield f"\n✓ finished (exit {proc.returncode})"


# ── Runners (generators) ──────────────────────────────────────────────────────
def run_find(categories: list[str], zips: list[str]) -> "Iterator[str]":
    _ensure_enabled()
    cats = [c.strip() for c in categories if c.strip()]
    zps  = [z.strip() for z in zips if z.strip()]
    for c in cats:
        if not _CATEGORY_RE.match(c):
            raise PipelineError(f"Invalid category: {c!r}")
    for z in zps:
        if not _ZIP_RE.match(z):
            raise PipelineError(f"Invalid ZIP: {z!r}")

    argv = [sys.executable, "lead_finder.py"]
    if cats:
        argv += ["--categories", *cats]
    if zps:
        argv += ["--zips", *zps]

    yield from _stream(argv)
    yield "\n📥  Syncing new leads into the dashboard…"
    result = db.import_csv()
    yield f"   {result}"


def run_demo(lead_name: str) -> "Iterator[str]":
    _ensure_enabled()
    name = lead_name.strip()
    if not _LEAD_RE.match(name):
        raise PipelineError(f"Invalid lead name: {name!r}")
    yield from _stream([sys.executable, "demos.py", "--lead", name])


# ── Non-streaming sync helpers ────────────────────────────────────────────────
def sync_from_csv() -> dict:
    return db.import_csv()


def export_to_csv() -> dict:
    return db.export_csv()
