from datetime import timedelta
from functools import lru_cache

from app.banking.audit import InMemoryAuditSink
from app.banking.repository import CuratedBankingRepository
from app.banking.service import BankingService
from app.banking.sessions import SessionStore
from app.core.config import get_settings
from app.workflow.orchestrator import IncidentWorkflow
from app.workflow.storage import OperationalStore


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


@lru_cache
def get_incident_workflow() -> IncidentWorkflow:
    """Single in-process incident workflow.

    It coordinates the one banking service above, so both share the same session registry, and
    holds no state of its own beyond the local operational store.
    """
    store = OperationalStore(get_settings().operational_database_path)
    store.initialize()
    return IncidentWorkflow(service=get_banking_service(), store=store)
