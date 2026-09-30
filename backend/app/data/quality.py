from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import duckdb

from app.data.contracts import TableContract


@dataclass(frozen=True)
class CheckResult:
    metrics: dict[str, Any]
    findings: list[dict[str, Any]]


def _blank(column: str) -> str:
    return f"({column} IS NULL OR trim({column}) = '')"


def _populated(column: str) -> str:
    return f"NOT {_blank(column)}"


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def _finding(check: str, count: int, detail: str | None = None) -> dict[str, Any]:
    finding: dict[str, Any] = {"check": check, "count": count}
    if detail is not None:
        finding["detail"] = detail
    return finding


def _identifier_metrics(
    con: duckdb.DuckDBPyConnection, table: str, column: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    duplicated = f"FROM {table} WHERE {_populated(column)} GROUP BY {column} HAVING count(*) > 1"
    metrics = {
        f"null_{column}": _scalar(con, f"SELECT count(*) FROM {table} WHERE {_blank(column)}"),
        f"duplicate_{column}_values": _scalar(con, f"SELECT count(*) FROM (SELECT 1 {duplicated})"),
        f"duplicate_{column}_surplus_rows": _scalar(
            con,
            f"SELECT coalesce(sum(copies - 1), 0) FROM (SELECT count(*) AS copies {duplicated})",
        ),
    }
    findings: list[dict[str, Any]] = []
    if metrics[f"null_{column}"]:
        findings.append(_finding(f"null_{column}", metrics[f"null_{column}"]))
    if metrics[f"duplicate_{column}_values"]:
        findings.append(
            _finding(
                f"duplicate_{column}",
                metrics[f"duplicate_{column}_values"],
                f"{metrics[f'duplicate_{column}_surplus_rows']} surplus row(s)",
            )
        )
    return metrics, findings


def _foreign_key_misses(
    con: duckdb.DuckDBPyConnection,
    table: str,
    column: str,
    parent_table: str,
    parent_column: str,
) -> int:
    return _scalar(
        con,
        f"SELECT count(*) FROM {table} AS child "
        f"WHERE {_populated(f'child.{column}')} AND child.{column} NOT IN "
        f"(SELECT {parent_column} FROM {parent_table} WHERE {_populated(parent_column)})",
    )


def _distribution(con: duckdb.DuckDBPyConnection, table: str, column: str) -> dict[str, int]:
    rows = con.execute(
        f"SELECT coalesce(nullif(trim({column}), ''), '<null>') AS value, count(*) AS n "
        f"FROM {table} GROUP BY 1 ORDER BY n DESC, value"
    ).fetchall()
    return {str(value): int(count) for value, count in rows}


def _domain_findings(
    column: str, domain: frozenset[str], distribution: dict[str, int]
) -> list[dict[str, Any]]:
    unexpected = {
        value: count
        for value, count in distribution.items()
        if value != "<null>" and value not in domain
    }
    if not unexpected:
        return []
    detail = ", ".join(f"{value}={count}" for value, count in unexpected.items())
    return [_finding(f"unexpected_{column}", sum(unexpected.values()), detail)]


def _invalid_count(con: duckdb.DuckDBPyConnection, table: str, column: str, dtype: str) -> int:
    return _scalar(
        con,
        f"SELECT count(*) FROM {table} "
        f"WHERE {_populated(column)} AND TRY_CAST({column} AS {dtype}) IS NULL",
    )


def check_customers(con: duckdb.DuckDBPyConnection, staging: str) -> CheckResult:
    metrics, findings = _identifier_metrics(con, staging, "customer_id")
    return CheckResult(
        {"row_count": _scalar(con, f"SELECT count(*) FROM {staging}"), **metrics}, findings
    )


def check_products(
    con: duckdb.DuckDBPyConnection, staging: str, customers_staging: str
) -> CheckResult:
    metrics, findings = _identifier_metrics(con, staging, "product_id")
    null_customer_id = _scalar(con, f"SELECT count(*) FROM {staging} WHERE {_blank('customer_id')}")
    orphan_customer_id = _foreign_key_misses(
        con, staging, "customer_id", customers_staging, "customer_id"
    )
    metrics["null_customer_id"] = null_customer_id
    metrics["orphan_customer_id"] = orphan_customer_id
    if null_customer_id:
        findings.append(_finding("null_customer_id", null_customer_id))
    if orphan_customer_id:
        findings.append(
            _finding("orphan_customer_id", orphan_customer_id, "customer_id absent from customers")
        )
    return CheckResult(
        {"row_count": _scalar(con, f"SELECT count(*) FROM {staging}"), **metrics}, findings
    )


def check_transactions(
    con: duckdb.DuckDBPyConnection,
    staging: str,
    customers_staging: str,
    products_staging: str,
    contract: TableContract,
) -> CheckResult:
    metrics, findings = _identifier_metrics(con, staging, "transaction_id")
    for column in ("customer_id", "product_id"):
        metrics[f"null_{column}"] = _scalar(
            con, f"SELECT count(*) FROM {staging} WHERE {_blank(column)}"
        )
        if metrics[f"null_{column}"]:
            findings.append(_finding(f"null_{column}", metrics[f"null_{column}"]))
    for column, parent in (("customer_id", customers_staging), ("product_id", products_staging)):
        metrics[f"orphan_{column}"] = _foreign_key_misses(con, staging, column, parent, column)
        if metrics[f"orphan_{column}"]:
            findings.append(_finding(f"orphan_{column}", metrics[f"orphan_{column}"]))

    ownership_mismatch = _scalar(
        con,
        f"SELECT count(*) FROM {staging} AS t JOIN {products_staging} AS p "
        f"ON p.product_id = t.product_id "
        f"WHERE t.customer_id IS DISTINCT FROM p.customer_id",
    )
    metrics["ownership_mismatch"] = ownership_mismatch
    if ownership_mismatch:
        findings.append(
            _finding(
                "ownership_mismatch",
                ownership_mismatch,
                "transaction.customer_id differs from the owner of transaction.product_id",
            )
        )

    metrics["null_response_code"] = _scalar(
        con, f"SELECT count(*) FROM {staging} WHERE {_blank('response_code')}"
    )
    if metrics["null_response_code"]:
        findings.append(_finding("null_response_code", metrics["null_response_code"]))
    for metric, column, dtype in (
        ("invalid_transaction_date", "transaction_date", "TIMESTAMP"),
        ("invalid_amount", "amount", "DECIMAL(18,2)"),
    ):
        metrics[metric] = _invalid_count(con, staging, column, dtype)
        if metrics[metric]:
            findings.append(_finding(metric, metrics[metric], f"unparseable as {column}"))

    for column, domain in contract.expected_domains.items():
        distribution = _distribution(con, staging, column)
        metrics[f"{column}_distribution"] = distribution
        findings.extend(_domain_findings(column, domain, distribution))
    metrics["response_code_distribution"] = _distribution(con, staging, "response_code")
    metrics["currency_distribution"] = _distribution(con, staging, "currency")

    return CheckResult(
        {"row_count": _scalar(con, f"SELECT count(*) FROM {staging}"), **metrics}, findings
    )


def iter_findings(results: Iterable[CheckResult]) -> list[dict[str, Any]]:
    return [finding for result in results for finding in result.findings]
