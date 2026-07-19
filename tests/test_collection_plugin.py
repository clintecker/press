"""The collection plugin proves itself by rejecting malformed suites.

Each test here spins up a sub-pytest session (pytester) whose conftest
installs press.pytest_invariants, feeds it one deliberately broken test,
and asserts collection fails for the intended reason -- unknown
invariant, missing proof metadata, unknown layer, an assertionless
marked test, an xfail with no cited limitation, or a skip that names no
capability. A final case proves a well-formed suite is *not* rejected,
so the plugin is shown to have both teeth and restraint.

The plugin's real proof is negative (it must turn red), so these run as
plain unit tests over its collection behaviour rather than carrying the
very markers they police.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

_SRC = Path(__file__).resolve().parent.parent / "src"

# A conftest for the sub-session: put src on the path, register the
# strict markers the sub-session's ini does not know about, and install
# the enforcement plugin under test.
_CONFTEST = f'''
import sys
from pathlib import Path

SRC = Path(r"{_SRC}")
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from press import pytest_invariants


def pytest_configure(config):
    for name in ("invariant", "layer", "proof"):
        config.addinivalue_line("markers", f"{{name}}: metadata under test")
    pytest_invariants._install(config)
'''


def _run(pytester: pytest.Pytester, body: str):
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(body)
    return pytester.runpytest()


def _combined(result) -> str:
    return "\n".join(result.outlines + result.errlines)


def test_unknown_invariant_id_fails_collection(pytester):
    result = _run(pytester, '''
        import pytest

        @pytest.mark.invariant("INV-not-a-real-id")
        @pytest.mark.layer("property")
        @pytest.mark.proof("positive")
        def test_thing():
            assert True
    ''')
    assert result.ret != 0
    assert "unknown invariant" in _combined(result)
    assert "test_thing" in _combined(result)


def test_invariant_without_proof_fails_collection(pytester):
    result = _run(pytester, '''
        import pytest

        @pytest.mark.invariant("INV-config-slug")
        @pytest.mark.layer("property")
        def test_no_proof():
            assert True
    ''')
    assert result.ret != 0
    combined = _combined(result)
    assert "requires a proof marker" in combined
    assert "test_no_proof" in combined


def test_unknown_layer_fails_collection(pytester):
    result = _run(pytester, '''
        import pytest

        @pytest.mark.invariant("INV-config-slug")
        @pytest.mark.layer("wrong-tier")
        @pytest.mark.proof("positive")
        def test_bad_layer():
            assert True
    ''')
    assert result.ret != 0
    assert "unknown layer" in _combined(result)


def test_assertionless_marked_test_fails_collection(pytester):
    result = _run(pytester, '''
        import pytest

        @pytest.mark.invariant("INV-config-slug")
        @pytest.mark.layer("property")
        @pytest.mark.proof("positive")
        def test_proves_nothing():
            value = 1 + 1
    ''')
    assert result.ret != 0
    combined = _combined(result)
    assert "no assertion" in combined
    assert "test_proves_nothing" in combined


def test_xfail_without_limitation_fails_collection(pytester):
    result = _run(pytester, '''
        import pytest

        @pytest.mark.xfail(reason="flaky, will look at it later")
        def test_unexplained_xfail():
            assert False
    ''')
    assert result.ret != 0
    assert "declared invariant limitation" in _combined(result)


def test_environment_skip_without_capability_fails_collection(pytester):
    result = _run(pytester, '''
        import pytest

        @pytest.mark.skipif(True, reason="not in the mood")
        def test_unexplained_skip():
            assert True
    ''')
    assert result.ret != 0
    assert "must name a declared capability" in _combined(result)


def test_wellformed_suite_is_accepted(pytester):
    """The plugin has restraint: a valid marked test, a properly cited
    xfail, and a capability-gated skip all collect cleanly."""

    result = _run(pytester, '''
        import pytest

        @pytest.mark.invariant("INV-config-slug")
        @pytest.mark.layer("property")
        @pytest.mark.proof("positive")
        def test_valid_marked():
            assert True

        @pytest.mark.xfail(reason="known limit of INV-config-slug")
        def test_cited_xfail():
            assert False

        @pytest.mark.skipif(False, reason="requires capability:pandoc")
        def test_capability_skip():
            assert True
    ''')
    assert result.ret == 0
    result.assert_outcomes(passed=2, xfailed=1)
