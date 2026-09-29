"""Initial local order schema and allocation guards."""
from pathlib import Path
import runpy
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def snapshot():
    return runpy.run_path(str(Path(__file__).resolve().parents[1] / 'schema_v1.py'))

def upgrade():
    for statement in snapshot()['DDL']:
        op.execute(statement)

def downgrade():
    for table in reversed(snapshot()['TABLES']):
        op.execute(f'DROP TABLE {table}')
