"""HTTP layer over Layers 1-4 (FastAPI).

    from knowledgeos.api import create_app
    app = create_app()

Transport and error mapping only. Every calculation belongs to the engine, and every state
change goes through the Layer 4 boundary - this layer must never compute a protected quantity
or write state directly.
"""

from .app import create_app

__all__ = ["create_app"]
