"""Shared pytest fixtures.

Stage 0 ships an empty but runnable harness: `pytest` collects 0 tests and exits clean.
Stage 1 adds the first real fixtures (curriculum loaded from curriculum_fixture.json).
"""

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    """Absolute path to the repository root (where the curriculum JSON lives)."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixture_curriculum_path(repo_root: pathlib.Path) -> pathlib.Path:
    """Path to the small connected curriculum slice used by Stages 1-3."""
    return repo_root / "curriculum_fixture.json"


def pytest_sessionfinish(session, exitstatus):
    """Treat an empty suite as success.

    Stage 0 ships zero tests deliberately, but pytest exits 5 (NO_TESTS_COLLECTED) for an
    empty run, which would fail CI for the wrong reason. Once Stage 1 adds real tests this
    branch stops firing on its own — it never masks a genuine failure, since any collected
    test that fails produces exit 1.
    """
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
