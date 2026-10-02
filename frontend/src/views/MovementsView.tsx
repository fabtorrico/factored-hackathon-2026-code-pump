import { useCallback, useState } from "react";

import type { TransactionFilters } from "../api/types";
import { MovementList } from "../components/MovementList";
import { Card, ErrorNotice, Loading } from "../components/primitives";
import { useResource } from "../hooks/useResource";
import { useSession } from "../state/SessionProvider";

const STATUSES = ["Approved", "Declined", "Pending", "Reversed"];
const TYPES = ["Transfer", "Payment", "Withdrawal", "Deposit", "Purchase", "Adjustment"];
const CURRENCIES = ["USD", "ARS", "COP"];
const CHANNELS = ["App", "Web", "ATM", "POS", "Transfer", "Branch"];

/**
 * Movements.
 *
 * Filters map one to one onto the curated read's own parameters, so nothing here narrows the result
 * set in a way the backend did not. An empty filter set means "everything on record".
 */
export function MovementsView() {
  const { api, endSession } = useSession();
  const [filters, setFilters] = useState<TransactionFilters>({});

  const load = useCallback(
    (client: typeof api) =>
      client.getTransactions(
        Object.fromEntries(
          Object.entries(filters)
            .filter(([, value]) => value !== undefined && value !== "")
            .map(([key, value]) => [key, String(value)]),
        ),
      ),
    [api, filters],
  );

  const { data, error, loading, reload } = useResource(api, load, endSession);
  const transactions = data?.transactions ?? [];

  function set(key: keyof TransactionFilters, value: string): void {
    setFilters((current) => ({ ...current, [key]: value === "" ? undefined : value }));
  }

  return (
    <main className="page">
      <header className="page__header">
        <div>
          <p className="eyebrow">Movements</p>
          <h1 className="page__title">Everything on record</h1>
        </div>
        <p className="muted page__note">
          Statuses below are what our systems recorded. Nothing is inferred from them.
        </p>
      </header>

      <Card title="Filter">
        <div className="filters">
          <Select
            id="filter-status"
            label="Status"
            value={filters.transaction_status ?? ""}
            options={STATUSES}
            onChange={(value) => set("transaction_status", value)}
          />
          <Select
            id="filter-type"
            label="Type"
            value={filters.transaction_type ?? ""}
            options={TYPES}
            onChange={(value) => set("transaction_type", value)}
          />
          <Select
            id="filter-currency"
            label="Currency"
            value={filters.currency ?? ""}
            options={CURRENCIES}
            onChange={(value) => set("currency", value)}
          />
          <Select
            id="filter-channel"
            label="Channel"
            value={filters.channel ?? ""}
            options={CHANNELS}
            onChange={(value) => set("channel", value)}
          />
          <div className="filters__actions">
            <button
              type="button"
              className="button button--quiet"
              onClick={() => setFilters({})}
              disabled={Object.keys(filters).length === 0}
            >
              Clear filters
            </button>
          </div>
        </div>
      </Card>

      {error !== null && (
        <ErrorNotice title="We could not load your movements" onRetry={reload}>
          <p>{error}</p>
        </ErrorNotice>
      )}

      <Card
        title={transactions.length === 1 ? "1 movement" : `${transactions.length} movements`}
      >
        {loading ? <Loading label="Loading movements" /> : <MovementList transactions={transactions} emptyTitle="No movement on record matches these filters." />}
      </Card>
    </main>
  );
}

function Select({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="control">
      <label className="control__label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="control__input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}