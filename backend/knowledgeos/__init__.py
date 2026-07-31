"""KnowledgeOS - evidence-based interview-readiness modelling.

Four layers with hard boundaries (see ARCHITECTURE.md):
    curriculum/  L1  static DAG - what SHOULD be known
    state/       L2  per-node user overlay - what the user knows
    engine/      L3  deterministic calculation - pure, no I/O
    assessment/  L4  boundary - Schema A out, Schema B in
    api/             HTTP layer over L1-L4
"""
