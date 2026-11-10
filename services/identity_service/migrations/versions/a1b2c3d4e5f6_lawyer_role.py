"""Rename the legacy role in the dedicated JURION database."""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "45d0aff8f33e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role RENAME VALUE 'player' TO 'lawyer'")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'lawyer'")


def downgrade() -> None:
    op.execute("ALTER TYPE user_role RENAME VALUE 'lawyer' TO 'player'")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'player'")
