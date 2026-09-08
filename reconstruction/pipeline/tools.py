"""Resolve external tool executables reproducibly.

Order of precedence for each tool:
  1. environment variable  (FFMPEG_BIN / COLMAP_BIN / BRUSH_BIN ...)
  2. config "tools" block   (pipeline.json -> {"tools": {"colmap": "..."}})
  3. the bare name on PATH

This keeps machine-specific absolute paths OUT of the committed config: set an
env var (this session) or a gitignored local config on machines where the tools
are not on PATH.
"""
from __future__ import annotations

import json
import os
import shutil


def load_config(path: str | None) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def resolve_tool(name: str, cfg: dict, env_var: str | None = None) -> str:
    if env_var:
        v = os.environ.get(env_var)
        if v:
            return v
    v = (cfg.get("tools") or {}).get(name)
    if v:
        return v
    return shutil.which(name) or name  # fall back to bare name (errors on run if absent)
