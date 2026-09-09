from app.db.base import Base
from app.db.database import engine
import app.models  # noqa: F401 -- register all tables with Base.metadata


def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
