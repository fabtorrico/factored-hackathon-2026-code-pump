from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app -> backend -> repository root
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = REPOSITORY_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Banking Incident Resolution API"
    host: str = "127.0.0.1"
    port: int = 8000

    # The banking core reads the curated DuckDB database built by `python -m app.data`. It never
    # touches the raw organizer sources, so a missing database is a configuration state rather
    # than a data-quality problem.
    data_root: Path = DEFAULT_DATA_ROOT
    database_path: Path | None = None

    # Demo session lifetime. There is no refresh, no revocation list and no credential check:
    # sessions are local to the process and exist only to prove the identity invariant.
    session_ttl_seconds: int = 1800
    audit_capacity: int = 500

    @property
    def curated_database_path(self) -> Path:
        if self.database_path is not None:
            return self.database_path
        return self.data_root / "processed" / "banking.duckdb"

    @property
    def operational_database_path(self) -> Path:
        """Local SQLite file for application-generated operational state.

        It holds incidents, support cases and workflow events, never banking facts. It lives
        under the gitignored data root so operational rows are never committed.
        """

        return self.data_root / "operational" / "app.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
