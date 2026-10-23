"""Settings from a `.env` file in the project folder, such as GEMINI_API_KEY.

A variable already set in the environment wins over the file. The file is ignored by git.
"""

import os
from pathlib import Path

from pasalkini.paths import ROOT


def load_env(path: Path = ROOT / ".env") -> list[str]:
    """Read KEY=value lines into the environment. Returns the names it set (never values)."""
    if not path.exists():
        return []
    added = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if name and value and name not in os.environ:
            os.environ[name] = value
            added.append(name)
    return added
