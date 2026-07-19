"""The artifact registry: every product of the press, stated once.

Formats and outputs were restated in CLI routing, build dispatch,
verification, Pages downloads, and documentation, and the copies had
already drifted (`press pages` crashed on a clean book because its
real prerequisites lived only in the order `press all` happened to
run). Each artifact here declares its outputs, prerequisites, builder,
publication role, and optionality; target lists, download names, and
build order derive from the declaration, and the selftest proves the
graph is acyclic with no duplicated outputs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Artifact:
    name: str
    outputs: tuple[str, ...]          # dist-relative, {slug} substituted
    prerequisites: tuple[str, ...] = ()
    published: bool = True            # listed as a public download
    condition: str | None = None      # e.g. "authorities": only when configured
    format_target: bool = True        # built via build.build_target(name)


ARTIFACTS: dict[str, Artifact] = {a.name: a for a in [
    Artifact("pdf", ("{slug}.pdf",)),
    Artifact("epub", ("{slug}.epub",)),
    Artifact("html", ("{slug}.html",)),
    Artifact("markdown", ("{slug}.md",)),
    Artifact("txt", ("{slug}.txt",)),
    Artifact("docx", ("{slug}.docx",)),
    Artifact("site", ("site", "{slug}-site.zip")),
    Artifact("source", ("{slug}-source.zip",), format_target=False),
    Artifact("sources", ("{slug}-sources.md",), prerequisites=("markdown",),
             condition="authorities", format_target=False),
    Artifact("pages", ("pages",),
             prerequisites=("pdf", "epub", "html", "markdown", "txt", "docx",
                            "site", "source", "sources"),
             published=False, format_target=False),
    Artifact("print", ("{slug}-interior.pdf",), published=False),
    Artifact("coverwrap", ("{slug}-coverwrap.pdf",), prerequisites=("print",),
             published=False, format_target=False),
]}

FORMATS = [a.name for a in ARTIFACTS.values()
           if a.format_target and a.name not in ("print",)]


def condition_holds(artifact: Artifact) -> bool:
    from . import booklib

    if artifact.condition is None:
        return True
    if artifact.condition == "authorities":
        return (booklib.root() / "config" / "authorities.yaml").is_file()
    raise SystemExit(f"unknown artifact condition: {artifact.condition}")


def download_names() -> list[str]:
    """Every published artifact file, in registry order."""

    from . import booklib

    slug = booklib.slug()
    names: list[str] = []
    for artifact in ARTIFACTS.values():
        if not artifact.published or not condition_holds(artifact):
            continue
        for output in artifact.outputs:
            name = output.format(slug=slug)
            if "." in name:  # directories are not downloads
                names.append(name)
    return names


def build_order(targets: list[str]) -> list[str]:
    """The targets plus every prerequisite, dependency-first."""

    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in ordered:
            return
        if name in visiting:
            raise SystemExit(f"artifact dependency cycle at {name}")
        artifact = ARTIFACTS.get(name)
        if artifact is None:
            raise SystemExit(f"unknown artifact: {name}")
        visiting.add(name)
        for prerequisite in artifact.prerequisites:
            visit(prerequisite)
        visiting.discard(name)
        ordered.append(name)

    for target in targets:
        visit(target)
    return ordered


def build(name: str) -> None:
    """Build an artifact and everything it stands on, dependency-first."""

    import time

    timings: list[tuple[str, float]] = []
    for step in build_order([name]):
        if not condition_holds(ARTIFACTS[step]):
            continue
        started = time.monotonic()
        _execute(step)
        timings.append((step, time.monotonic() - started))
    ran = [(step, elapsed) for step, elapsed in timings if elapsed >= 0.05]
    if len(ran) > 1:
        total = sum(elapsed for _, elapsed in timings)
        stages = "; ".join(f"{step} {elapsed:.1f}s" for step, elapsed in ran)
        print(f"press timings: {stages}; total {total:.1f}s")


def _execute(step: str) -> None:
    from . import booklib, build as builder

    if step == "source":
        from . import package_source

        package_source.main()
    elif step == "sources":
        pass  # generated alongside any pandoc build of the manuscript
    elif step == "pages":
        builder.build_target("pages")
    elif step == "coverwrap":
        from . import gen_coverwrap

        root = booklib.root()
        slug = booklib.slug()
        gen_coverwrap.generate(
            root / "dist" / f"{slug}-interior.pdf",
            root / "dist" / f"{slug}-coverwrap.pdf",
        )
    else:
        builder.build_target(step)
