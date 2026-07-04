"""revamp to kyb and business tables

Revision ID: 213b6f55906e
Revises: 929fd0d4d221
Create Date: 2026-07-04 23:13:24.983132+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '213b6f55906e'
down_revision: Union[str, None] = '929fd0d4d221'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    enum_exists = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'verification_status_enum');")
    ).scalar()

    if not enum_exists:
        op.execute("CREATE TYPE verification_status_enum AS ENUM ('pending', 'verified', 'rejected', 'expired');")

    op.execute(
        "ALTER TABLE kyb_verifications "
        "ALTER COLUMN status TYPE verification_status_enum "
        "USING status::verification_status_enum"
    )

    op.execute(
        "ALTER TABLE kyc_verifications "
        "ALTER COLUMN status TYPE verification_status_enum "
        "USING status::verification_status_enum"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE kyc_verifications "
        "ALTER COLUMN status TYPE VARCHAR(20) "
        "USING status::text"
    )

    op.execute(
        "ALTER TABLE kyb_verifications "
        "ALTER COLUMN status TYPE VARCHAR(20) "
        "USING status::text"
    )
