"""Support one blank sample image per template page."""

from alembic import op
import sqlalchemy as sa

revision = "0002_template_pages"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "template_page_samples" not in tables:
        op.create_table(
            "template_page_samples",
            sa.Column("template_id", sa.String(36), sa.ForeignKey("form_templates.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("page_number", sa.Integer(), primary_key=True, server_default="1"),
            sa.Column("stored_path", sa.Text(), nullable=False),
            sa.Column("original_filename", sa.String(260), nullable=False),
        )
    if "template_samples" in tables:
        op.execute(sa.text("INSERT OR IGNORE INTO template_page_samples (template_id, page_number, stored_path, original_filename) SELECT template_id, 1, stored_path, original_filename FROM template_samples"))


def downgrade() -> None:
    # Keep template sample rows intact for safe rollback.
    pass
