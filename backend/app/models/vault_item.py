from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VaultItem(Base):
    __tablename__ = "vault_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    encrypted_password: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    website: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    encrypted_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )