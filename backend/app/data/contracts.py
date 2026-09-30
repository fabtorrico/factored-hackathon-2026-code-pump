from collections.abc import Mapping
from dataclasses import dataclass, field

CUSTOMER_FILE = "raw/customers.csv"
PRODUCT_FILE = "raw/products.csv"
TRANSACTION_FILE = "sample/transactions_20260617.csv"

# Incident scenarios drive the status domain: Declined, Pending and Reversed are the
# customer-visible problem states, Approved is the success baseline.
TRANSACTION_STATUS_DOMAIN = frozenset({"Approved", "Declined", "Pending", "Reversed"})
TRANSACTION_TYPE_DOMAIN = frozenset(
    {"Purchase", "Withdrawal", "Transfer", "Payment", "Deposit", "Adjustment"}
)
CHANNEL_DOMAIN = frozenset({"POS", "ATM", "Web", "App", "Branch", "Transfer"})


class ContractViolationError(RuntimeError):
    """A source file cannot satisfy its declared contract."""


@dataclass(frozen=True)
class TypedColumn:
    name: str
    dtype: str


@dataclass(frozen=True)
class TableContract:
    key: str
    table: str
    source: str
    primary_key: str
    # curated_columns is the allowlist projected into DuckDB. Everything else the organizer
    # ships - names, documents, addresses, phone numbers, demographics - stays in the raw CSV
    # and never reaches a table a banking tool can query.
    curated_columns: tuple[str, ...]
    typed_columns: tuple[TypedColumn, ...] = ()
    expected_domains: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Source columns the run cannot proceed without, validated before projection."""
        return self.curated_columns

    def missing_columns(self, available: frozenset[str]) -> list[str]:
        return [name for name in self.curated_columns if name not in available]


CUSTOMERS = TableContract(
    key="customers",
    table="customers",
    source=CUSTOMER_FILE,
    primary_key="customer_id",
    # customer_id joins every fact table; country/detected_accent drive locale routing for the
    # agent response; segment and customer_status decide which policy branch an incident takes.
    # Identity, contact, address and demographic attributes are deliberately excluded.
    curated_columns=(
        "customer_id",
        "customer_status",
        "segment",
        "country",
        "detected_accent",
    ),
)

PRODUCTS = TableContract(
    key="products",
    table="products",
    source=PRODUCT_FILE,
    primary_key="product_id",
    # product_id/customer_id establish transaction ownership; product_type and product_status
    # select the playbook; currency normalises amounts; opening_channel and has_linked_app
    # explain how the customer reaches the service and whether self-service recovery is even
    # possible. current_balance is read-only context for the agent. It is never a decline reason:
    # a transaction fails because of the recorded transaction_status/response_code, never because
    # a balance looked low. product_number is a customer-facing account number and is excluded,
    # and credit_limit is excluded because limit breaches are one of the causes we must verify
    # from evidence rather than infer from a stored figure.
    curated_columns=(
        "product_id",
        "customer_id",
        "product_type",
        "product_status",
        "currency",
        "current_balance",
        "opening_channel",
        "has_linked_app",
    ),
    typed_columns=(
        TypedColumn("current_balance", "DECIMAL(18,2)"),
        TypedColumn("has_linked_app", "BOOLEAN"),
    ),
)

TRANSACTIONS = TableContract(
    key="transactions",
    table="transactions",
    source=TRANSACTION_FILE,
    primary_key="transaction_id",
    # The minimum incident record: who, which product, when, what kind, how much, how it was
    # initiated, and what the bank decided (transaction_status/response_code are the only
    # decline evidence in the schema).
    # process_date separates customer initiation from bank processing, which is the anchor for
    # how long a Pending transfer or payment has been stuck.
    # amount_usd is the verified normalised amount; the book runs in USD, COP and ARS, so any
    # currency-independent comparison or threshold needs it. It is supplementary - it is absent
    # on most rows and never the sole basis for a decision.
    curated_columns=(
        "transaction_id",
        "customer_id",
        "product_id",
        "transaction_date",
        "process_date",
        "transaction_type",
        "amount",
        "currency",
        "amount_usd",
        "channel",
        "transaction_status",
        "response_code",
    ),
    typed_columns=(
        TypedColumn("transaction_date", "TIMESTAMP"),
        TypedColumn("process_date", "TIMESTAMP"),
        TypedColumn("amount", "DECIMAL(18,2)"),
        TypedColumn("amount_usd", "DECIMAL(18,2)"),
    ),
    expected_domains={
        "transaction_type": TRANSACTION_TYPE_DOMAIN,
        "transaction_status": TRANSACTION_STATUS_DOMAIN,
        "channel": CHANNEL_DOMAIN,
    },
)

CONTRACTS: tuple[TableContract, ...] = (CUSTOMERS, PRODUCTS, TRANSACTIONS)
