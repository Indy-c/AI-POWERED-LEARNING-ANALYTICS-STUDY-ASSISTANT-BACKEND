from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for db models
class Base(DeclarativeBase):
    pass

# Provides a database session for each API request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()