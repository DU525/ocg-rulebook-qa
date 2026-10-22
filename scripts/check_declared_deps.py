#!/usr/bin/env python
"""Fail if the backend imports a third-party module it does not declare.

`pip install -r backend/requirements.txt` used to produce a backend that could
not start, because nine imported packages were never declared. This check
catches that class of defect without touching the network: it compares the
module-level imports in backend/app against the names listed in
backend/requirements.txt and backend/requirements-optional.txt.

Only module-level imports are checked. Imports inside functions are assumed to
be optional paths, which the code guards explicitly.

    python scripts/check_declared_deps.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# module name -> distribution name, where they differ
ALIASES = {
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "dotenv": "python-dotenv",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "jwt": "pyjwt",
    "yaml": "pyyaml",
}


def declared() -> set[str]:
    names: set[str] = set()
    for rel in ("requirements.txt", "requirements-optional.txt"):
        path = BACKEND / rel
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            dist = re.split(r"[=<>!~\[;]", line)[0].strip()
            if not dist:
                continue
            names.add(dist.lower().replace("-", "_"))
            # faiss-cpu provides the faiss module
            names.add(dist.lower().replace("-", "_").split("_")[0])
    return names


def local_modules() -> set[str]:
    """Modules that live in this repository rather than on PyPI."""
    names = set()
    for base in (BACKEND, BACKEND / "app"):
        for p in base.rglob("*.py"):
            names.add(p.stem)
        for p in base.iterdir():
            if p.is_dir():
                names.add(p.name)
    return names


def module_level_imports() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in (BACKEND / "app").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in tree.body:  # module level only
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    mods = [node.module.split(".")[0]]
            for mod in mods:
                found.setdefault(mod, set()).add(str(path.relative_to(ROOT)))
    return found


def main() -> int:
    stdlib = set(sys.stdlib_module_names)
    decl = declared()
    local = local_modules()

    missing = []
    for mod, files in sorted(module_level_imports().items()):
        if mod in stdlib or mod in local or mod.startswith("_"):
            continue
        normalized = ALIASES.get(mod, mod).lower().replace("-", "_")
        if mod.lower() in decl or normalized in decl:
            continue
        missing.append((mod, sorted(files)))

    if not missing:
        print("all module-level third-party imports are declared")
        return 0

    print("undeclared module-level imports:", file=sys.stderr)
    for mod, files in missing:
        print(f"  {mod:<24} {files[0]}", file=sys.stderr)
    print(
        "\nAdd them to backend/requirements.txt (runtime) or "
        "backend/requirements-optional.txt (guarded).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())