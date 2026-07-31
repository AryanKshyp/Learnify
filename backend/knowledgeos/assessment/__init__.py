"""Layer 4 boundary - Assessment interface.

Generates Schema A (out) and strictly validates Schema B (in). The assessment engine itself is
external and replaceable; KnowledgeOS knows nothing about how it works. Schema B is the ONLY
way knowledge state changes.

Stage 4 populates this package.
"""
