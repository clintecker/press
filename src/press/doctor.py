"""press doctor: name what this machine can and cannot do.

The press leans on external tools with different failure smells: a
missing pandoc kills every build, a missing lualatex kills only PDFs,
a missing epubcheck merely softens one gate, and a missing claude CLI
disables the operator. The doctor examines each dependency, says what
works, what does not, and what each absence costs, so a new machine's
first failure is a diagnosis instead of a traceback.
"""

from __future__ import annotations

import os
import shutil
import subprocess


CHECKS = [
    ("pandoc", "every build target", True),
    ("lualatex", "PDF and print builds", True),
    ("latexmk", "PDF and print builds (multi-pass convergence)", True),
    ("pdftoppm", "PDF verification renders", True),
    ("pdffonts", "font-embedding verification", True),
    ("pdfinfo", "PDF structure verification", True),
    ("pdftotext", "PDF text verification", True),
    ("git", "scaffolding identity and book repositories", True),
    ("epubcheck", "the retail EPUB gate (softens to a warning locally)", False),
    ("claude", "the operator: press improve, research, aesthetic briefs", False),
]

KEYS = [
    ("OPENAI_API_KEY", "press art commission --model openai"),
    ("GEMINI_API_KEY", "press art commission --model gemini"),
]


def tool_runs(tool: str) -> bool:
    try:
        for flag in ("--version", "-v"):
            if subprocess.run(
                [tool, flag], capture_output=True, timeout=15
            ).returncode == 0:
                return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


def main() -> int:
    print("press doctor")
    missing_required = []
    for tool, purpose, required in CHECKS:
        if shutil.which(tool) is None:
            state = "MISSING" if required else "absent"
            if required:
                missing_required.append(tool)
            print(f"  [{state:>7}] {tool:<10} {purpose}")
        elif not tool_runs(tool):
            missing_required.append(tool)
            print(f"  [ BROKEN] {tool:<10} present but cannot execute; {purpose}")
        else:
            print(f"  [     ok] {tool:<10} {purpose}")
    for key, purpose in KEYS:
        state = "ok" if os.environ.get(key) else "unset"
        print(f"  [{state:>7}] {key:<16} {purpose}")
    try:
        from PIL import Image  # noqa: F401
        import pypdf  # noqa: F401
        import yaml  # noqa: F401

        print("  [     ok] python     Pillow, pypdf, PyYAML importable")
    except ImportError as exc:
        missing_required.append("python-deps")
        print(f"  [MISSING] python     {exc}")

    if missing_required:
        print(f"\nnot ready: {', '.join(missing_required)} "
              "(macOS: brew install pandoc mactex-no-gui poppler; "
              "Debian/Ubuntu: see the Dockerfile's package list)")
        return 1
    print("\nthis machine can make books")
    return 0
