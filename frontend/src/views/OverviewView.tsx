import { useCallback } from "react";
import { Link } from "react-router-dom";

import { MovementList } from "../components/MovementList";
import { Card, ErrorNotice, Field, Loading } from "../components/primitives";
import { useResource } from "../hooks/useResource";
import { formatAmount, humanize } from "../lib/format";
import { useSession } from "../state/SessionProvider";

/**
 * Home.
 *
 * The account summary a customer recognises first: who they are to us, what they hold and what has
 * moved recently. Every figure is a curated balance or amount, never a derived one.
 */
export function OverviewView() {
  const { api, session, endSession } = useSession();
  const loadContext = useCallback((client: typeof api) => client.getCustomerContext(), [api]);
  const loadMovements = useCallback((client: typeof api) => client.getTransactions(), [api]);

  const context = useResource(api, loadContext, endSession);
  const movements = useResource(api, loadMovements, endSession);

  const products = context.data?.products ?? [];
  const transactions = movements.data?.transactions ?? [];
  const needsAttention = transactions.filter((row) => row.transaction_status !== "Approved");

  return (
    <main className="page">
      <header className="page__header">
        <div>
          <p className="eyebrow">Overview</p>
          <h1 className="page__title">Hello, {session?.display_name ?? "there"}.</h1>
        </div>
      </header>

      {context.error !== null && (
        <ErrorNotice title="We could not read your account" onRetry={context.reload}>
          <p>{context.error}</p>
        </ErrorNotice>
      )}

      <div className="grid grid--summary">
        <Card title="Your details">
          {context.loading || context.data === null ? (
            <Loading label="Loading your details" />
          ) : (
            <dl className="fields">
              <Field label="Account status">{humanize(context.data.customer.customer_status)}</Field>
              <Field label="Segment">{humanize(context.data.customer.segment)}</Field>
              <Field label="Country">{humanize(context.data.customer.country)}</Field>
            </dl>
          )}
        </Card>

        <Card
          title="Worth checking"
          actions={
            needsAttention.length > 0 ? (
              <Link className="button button--quiet" to="/movements">
                See all
              </Link>
            ) : undefined
          }
        >
          {movements.loading ? (
            <Loading label="Checking recent movements" />
          ) : needsAttention.length === 0 ? (
            <p className="muted">
              Every movement on record is approved. If something still does not look right, report it
              and we will check the exact movement.
            </p>
          ) : (
            <>
              <p className="muted">
                {needsAttention.length} of your {transactions.length} movements are not approved.
                Declined and reversed movements are final answers; anything still in progress is not.
              </p>
              <MovementList transactions={needsAttention} emptyTitle="" />
            </>
          )}
        </Card>
      </div>

      <Card
        title="Your products"
        actions={<span className="muted">{products.length} on record</span>}
      >
        {context.loading ? (
          <Loading label="Loading your products" />
        ) : products.length === 0 ? (
          <p className="muted">No products are recorded against this account.</p>
        ) : (
          <ul className="products">
            {products.map((product) => (
              <li className="product" key={product.product_id}>
                <div>
                  <p className="product__type">{product.product_type}</p>
                  <p className="product__meta">
                    {humanize(product.product_status)} · opened {humanize(product.opening_channel)}
                    {product.has_linked_app ? " · app linked" : ""}
                  </p>
                </div>
                <p className="product__balance">
                  {formatAmount(product.current_balance, product.currency)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Recent movements">
        {movements.loading ? (
          <Loading label="Loading movements" />
        ) : (
          <>
            <MovementList transactions={transactions} emptyTitle="No movements are recorded." />
            {transactions.length > 0 && (
              <Link className="button button--primary" to="/movements">
                Review all movements
              </Link>
            )}
          </>
        )}
      </Card>
    </main>
  );
}