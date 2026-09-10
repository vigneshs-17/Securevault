"""Add typed notes and nullable timestamps; preserve unknown dates on old items."""
from alembic import op
import sqlalchemy as sa

revision = "0002_vault_metadata"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("vault_items", sa.Column("item_type", sa.String(20), nullable=False, server_default="password"))
    op.add_column("vault_items", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vault_items", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("vault_items", "updated_at")
    op.drop_column("vault_items", "created_at")
    op.drop_column("vault_items", "item_type")
