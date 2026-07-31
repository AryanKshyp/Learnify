"""Layer 3 - Decision Engine (deterministic). The heart of the system.

Pure functions: state + inputs in, new values out, no I/O. Identical inputs must always
produce identical outputs. Implemented strictly per CALC_ENGINE_SPEC.md, whose SS1 pipeline
fixes the ordering (never compute EM before PC, nor readiness before EM).

Stage 3 populates this package.
"""
