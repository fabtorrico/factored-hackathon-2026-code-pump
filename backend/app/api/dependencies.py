from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from app.agent import AgentSessionStore, AgentWorkspace
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
def get_demo_database_path() -> Path:
    """The curated database the demo profile catalogue is derived from.

    A dependency rather than a direct `get_settings()` call in the routes so the demo endpoints can
    be pointed at a fixture database in tests without touching global settings.
    """
    return get_settings().curated_database_path


@lru_cache
def get_operational_store() -> OperationalStore:
    """The one local operational store both the workflow and the agent workspace read.

    Initialization is idempotent, so every caller can safely ensure the schema exists.
    """
    store = OperationalStore(get_settings().operational_database_path)
    store.initialize()
    return store


@lru_cache
def get_incident_workflow() -> IncidentWorkflow:
    """Single in-process incident workflow.

    It coordinates the one banking service above, so both share the same session registry, and
    holds no state of its own beyond the local operational store.
    """
    return IncidentWorkflow(service=get_banking_service(), store=get_operational_store())


@lru_cache
def get_agent_workspace() -> AgentWorkspace:
    """Single in-process agent workspace.

    Read-only and demo-only: it reads the same operational store the workflow writes, and gates
    access with its own agent session store that no customer session can satisfy.
    """
    return AgentWorkspace(
        store=get_operational_store(),
        sessions=AgentSessionStore(ttl=timedelta(seconds=get_settings().session_ttl_seconds)),
    )
