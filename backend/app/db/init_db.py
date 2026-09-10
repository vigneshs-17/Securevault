from app.db.database import engine
from app.db.migrate import upgrade_database


def init_db():
    upgrade_database(engine)

if __name__ == "__main__":
    init_db()
