"""Count prose words in the ordered book manuscript."""

from __future__ import annotations

import re

from . import booklib


def main() -> int:
    root = booklib.root()
    total = 0
    for path in booklib.chapter_files():
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"`[^`]+`", " ", text)
        words = re.findall(r"\b[\w'-]+\b", text)
        total += len(words)
        print(f"{len(words):6d}  {path.relative_to(root)}")
    print(f"{total:6d}  TOTAL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
