from datetime import timedelta
from functools import lru_cache

from app.banking.audit import InMemoryAuditSink
from app.banking.repository import CuratedBankingRepository
from app.banking.service import BankingService
from app.banking.sessions import SessionStore
from app.core.config import get_settings


@lru_cache
def get_banking_service() -> BankingService:
    """Single in-process banking service.

    Sessions and the audit buffer are per-process and local to the prototype. The repository
    opens the curated DuckDB database read-only, so the service can be rebuilt at any time.
    """
    settings = get_settings()
    return BankingService(
        repository=CuratedBankingRepository(settings.curated_database_path),
        sessions=SessionStore(ttl=timedelta(seconds=settings.session_ttl_seconds)),
        audit=InMemoryAuditSink(capacity=settings.audit_capacity),
    )
