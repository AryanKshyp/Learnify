"""Every [TUNABLE] parameter of the deterministic engine (Layer 3), in one place.

`CALC_ENGINE_SPEC.md` requires "config, not constants": no numeric literal may appear inline
in engine logic. Stage 3 populates this module from the spec's defaults — until then it is
deliberately empty, since Stage 0 forbids writing calculation code.

Nothing here may import I/O, a clock, or a random source (see the import-linter contract in
pyproject.toml). Time enters the engine as an explicit parameter, never by reading a clock.
"""
