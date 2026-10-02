import { Link } from "react-router-dom";

import type { Transaction } from "../api/types";
import { formatAmount, formatDateTime } from "../lib/format";
import { StatusPill } from "./primitives";

/** A curated movement as a row. Identifiers are curated and stay off the screen. */
export function TransactionRow({ transaction }: { transaction: Transaction }) {
  return (
    <li className="movement">
      <div className="movement__main">
        <p className="movement__type">{transaction.transaction_type}</p>
        <p className="movement__meta">
          {formatDateTime(transaction.transaction_date)} · {transaction.channel}
        </p>
      </div>
      <div className="movement__side">
        <p className="movement__amount">{formatAmount(transaction.amount, transaction.currency)}</p>
        <StatusPill status={transaction.transaction_status} />
      </div>
      <Link className="movement__link" to={`/movements/${encodeURIComponent(transaction.transaction_id)}`}>
        <span className="visually-hidden">Open this movement</span>
        <span aria-hidden="true">→</span>
      </Link>
    </li>
  );
}

export function MovementList({
  transactions,
  emptyTitle,
}: {
  transactions: Transaction[];
  emptyTitle: string;
}) {
  if (transactions.length === 0) {
    return <p className="muted">{emptyTitle}</p>;
  }
  return (
    <ul className="movements">
      {transactions.map((transaction) => (
        <TransactionRow key={transaction.transaction_id} transaction={transaction} />
      ))}
    </ul>
  );
}