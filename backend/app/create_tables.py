# Deprecated: use Alembic migrations instead.

from app.core.database import engine, Base
from app.domains.users.model import User

# Create all tables in the database for imported models
Base.metadata.create_all(bind=engine)
