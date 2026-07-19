#!/usr/bin/env python3
"""Write the deterministic fuzz corpus.

Run once; the files it writes are the checked-in, replayable inputs
that tests/test_fuzz.py feeds to the hostile parsers. There is no RNG
here and none at test time: a fuzz finding is a file, reproducible
forever, not a seed nobody can reconstruct. Add a hostile input by
adding an entry here and running this script.

Usage: python3 tests/fuzz/generate_corpus.py
"""

from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).resolve().parent / "corpus"

YAML = {
    "empty.yaml": "",
    "just-null.yaml": "null\n",
    "unclosed-quote.yaml": 'title: "Unclosed\n',
    "tab-indent.yaml": "title:\n\tbad: 1\n",
    "list-not-map.yaml": "- a\n- b\n",
    "scalar.yaml": "just a string\n",
    "deep-nest.yaml": "a:\n" + "".join(f"{' ' * i}k{i}:\n" for i in range(1, 40)),
    "duplicate-key.yaml": "title: a\ntitle: b\n",
    "binary-tag.yaml": "x: !!binary invalid**base64\n",
    "huge-anchor.yaml": "a: &x [1]\nb: *x\n",
    "control-chars.yaml": 'title: ""\n',
    "combining-key.yaml": "\u0301\u0302: value\n",
}

DOCX = {
    "empty.bin": b"",
    "not-xml.bin": b"\x00\x01\x02\xff\xfe garbage",
    "truncated-xml.bin": b"<?xml version='1.0'?><w:document><w:body><w:p><w:r><w:t>hi",
    "unclosed-tag.bin": b"<w:t>text without end",
    "entity-storm.bin": b"<w:t>" + b"&amp;" * 5000 + b"</w:t>",
    "wrong-namespace.bin": b"<doc><para><run><text>words</text></run></para></doc>",
    "nested-deep.bin": b"<w:t>" + b"<x>" * 2000 + b"deep" + b"</x>" * 2000 + b"</w:t>",
    "null-bytes.bin": b"<w:t>a\x00b\x00c</w:t>",
    "high-unicode.bin": "<w:t>\U0001F4A9 あ text</w:t>".encode("utf-8"),
}

HTML = {
    "empty.html": "",
    "unclosed.html": "<html><body><a href='x.html'>link",
    "malformed-attr.html": "<a href=no-quotes.html src=>x</a>",
    "script.html": "<script>while(1){}</script><a href='y.html'>z</a>",
    "nested-style.html": "<style>body{background:url(a.png)}</style>",
    "broken-url.html": "<style>a{b:url(}</style>",
    "many-refs.html": "".join(f"<a href='p{i}.html'>x</a>" for i in range(500)),
    "entities.html": "<a href='a&amp;b.html'>&lt;&gt;&#x1F4A9;</a>",
    "fragment-only.html": "<a href='#top'>top</a><b id='top'>x</b>",
}

MEMBER = {
    "absolute.txt": "/etc/passwd",
    "traversal.txt": "../../../etc/passwd",
    "backslash.txt": "..\\..\\windows",
    "nul.txt": "site/evil",
    "empty.txt": "",
    "dotdot-embedded.txt": "site/../../escape",
    "long.txt": "site/" + "a" * 4000,
    "bidi.txt": "site/\u202e ",
}


def main() -> int:
    # The genuinely-hostile control bytes are built here, not written as
    # literals in source (an editor silently strips a raw NUL).
    YAML["control-chars.yaml"] = f'title: "{chr(1)}{chr(2)}{chr(3)}"\n'
    MEMBER["nul.txt"] = f"site/{chr(0)}evil"
    for kind, entries in (("yaml", YAML), ("html", HTML), ("member", MEMBER)):
        (BASE / kind).mkdir(parents=True, exist_ok=True)
        for name, content in entries.items():
            (BASE / kind / name).write_text(content, encoding="utf-8")
    (BASE / "docx").mkdir(parents=True, exist_ok=True)
    for name, content in DOCX.items():
        (BASE / "docx" / name).write_bytes(content)
    total = sum(1 for _ in BASE.rglob("*") if _.is_file())
    print(f"corpus written: {total} files under {BASE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
