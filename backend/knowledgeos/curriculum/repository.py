"""Curriculum access behind an interface (Layer 1).

The curriculum is static and user-independent, so it is served from JSON and held in memory —
566 nodes is nothing, and keeping Layer 1 free of a database is what lets Stages 1-3, including
the engine, be tested with no infrastructure at all.

The protocol exists so that stays a choice rather than an assumption: a database-backed
implementation can be substituted later without touching a single caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .graph import CurriculumGraph
from .loader import load_curriculum

#: repo root — this file is backend/knowledgeos/curriculum/repository.py
_REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CURRICULUM_PATH = _REPO_ROOT / "curriculum_graph.json"
FIXTURE_CURRICULUM_PATH = _REPO_ROOT / "curriculum_fixture.json"


@runtime_checkable
class CurriculumRepository(Protocol):
    """Somewhere a validated curriculum can be obtained from."""

    def get(self) -> CurriculumGraph: ...


class JsonCurriculumRepository:
    """Loads the curriculum from a JSON file, caching after the first read.

    The cache is safe because Layer 1 is immutable: nothing in the running system can change
    the curriculum, so a reload would always produce an identical graph. Call `reload()` if the
    file changed on disk (regenerating it via `build_graph.py`, say).
    """

    def __init__(self, path: Path | str = DEFAULT_CURRICULUM_PATH) -> None:
        self._path = Path(path)
        self._cached: CurriculumGraph | None = None

    @property
    def path(self) -> Path:
        return self._path

    def get(self) -> CurriculumGraph:
        if self._cached is None:
            self._cached = load_curriculum(self._path)
        return self._cached

    def reload(self) -> CurriculumGraph:
        self._cached = None
        return self.get()


def fixture_repository() -> JsonCurriculumRepository:
    """The small connected slice used by Stages 1-3 (`make_fixture.py` generates it)."""
    return JsonCurriculumRepository(FIXTURE_CURRICULUM_PATH)
