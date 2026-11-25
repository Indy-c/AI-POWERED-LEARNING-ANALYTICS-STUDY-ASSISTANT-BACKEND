from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from app.core.config import settings

def create_database_engine(url: str, **options):
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enforce_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


def begin_sqlite_transaction(db: Session, *, write: bool = False) -> None:
    if db.get_bind().dialect.name != "sqlite":
        return
    connection = db.connection()
    # SQLite's default driver mode does not begin a transaction for SELECT.
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")


engine = create_database_engine(settings.database_url)
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
