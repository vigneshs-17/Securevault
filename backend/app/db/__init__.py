from app.db.base import Base
from app.db.database import engine
from app.models import AuditLog, RefreshSession, User, VaultItem


def init_db():
    Base.metadata.create_all(bind=engine)