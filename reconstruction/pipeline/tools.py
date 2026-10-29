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
    return shutil.which(name) or name
