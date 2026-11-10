import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

logger = logging.getLogger(__name__)


def database_is_reachable(session: Session) -> bool:
    """Run a trivial query. Any DB/driver error means "not reachable"."""
    try:
        session.connection().execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database health check failed", exc_info=True)
        return False
    return True
