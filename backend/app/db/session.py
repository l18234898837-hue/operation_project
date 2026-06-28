import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def prewarm_database_connection() -> None:
    if not settings.db_connection_prewarm_enabled:
        logger.info("db_connection_prewarm skipped disabled=True")
        return

    start = time.perf_counter()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("db_connection_prewarm failed", exc_info=True)
        return

    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info("db_connection_prewarm success duration_ms=%s", duration_ms)
