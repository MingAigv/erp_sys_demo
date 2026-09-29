from alembic import context
from app.config import Settings
from app.db import Base, make_engine
import app.models

if context.is_offline_mode():
    context.configure(url='sqlite:///', target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(Settings().database_path)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
