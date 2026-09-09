"""Database package; importing models must not eagerly import other models."""


def init_db():
    from app.db.init_db import init_db as initialize

    initialize()
