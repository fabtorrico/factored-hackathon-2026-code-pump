from conftest import ABSENT_CUSTOMER, OTHER, OWNER, SESSION_TTL

from app.banking.errors import Reason


def test_api_can_open_a_session(api_client) -> None:
    response = api_client.post("/api/sessions", json={"customer_id": OWNER})

    assert response.status_code == 201
    body = response.json()
    assert body["customer_id"] == OWNER
    assert len(body["session_id"]) >= 32


def test_api_requires_session_header_to_read_context(api_client) -> None:
    response = api_client.get(f"/api/customers/{OWNER}/context")

    assert response.status_code == 401
    assert response.json()["error"] == Reason.INVALID_SESSION.value


def test_api_customer_context_authorized(api_client, customer_session: str) -> None:
    response = api_client.get(
        f"/api/customers/{OWNER}/context", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["customer_id"] == OWNER


def test_api_customer_context_denied(api_client, customer_session: str) -> None:
    response = api_client.get(
        f"/api/customers/{OTHER}/context", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 403
    assert response.json()["error"] == Reason.UNAUTHORIZED_RESOURCE.value


def test_api_transactions_filtered(api_client, customer_session: str) -> None:
    response = api_client.get(
        "/api/transactions?transaction_type=Transfer&limit=1",
        headers={"X-Session-Id": customer_session},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["transactions"]) == 1
    assert body["transactions"][0]["transaction_type"] == "Transfer"


def test_api_customer_id_scope_cannot_widen_a_read(api_client, customer_session: str) -> None:
    response = api_client.get(
        f"/api/transactions?customer_id={OTHER}", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 403


def test_api_customer_id_scope_is_accepted_for_the_own_customer(
    api_client, customer_session: str
) -> None:
    response = api_client.get(
        f"/api/transactions?customer_id={OWNER}", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 200
    assert response.json()["customer_id"] == OWNER


def test_api_context_ignores_nothing_about_the_session_customer(
    api_client, customer_session: str
) -> None:
    response = api_client.get(
        f"/api/customers/{OWNER}/context", headers={"X-Session-Id": customer_session}
    )

    body = response.json()
    assert set(body) == {"customer", "products"}
    assert body["products"][0]["current_balance"] == 1250.75


def test_api_unknown_session_is_unauthorized(api_client) -> None:
    response = api_client.get(f"/api/customers/{OWNER}/context", headers={"X-Session-Id": "forged"})

    assert response.status_code == 401
    assert response.json()["error"] == Reason.INVALID_SESSION.value


def test_api_unknown_customer_session_is_not_found(api_client, service) -> None:
    session = service.create_session(ABSENT_CUSTOMER).session_id

    response = api_client.get(
        f"/api/customers/{ABSENT_CUSTOMER}/context", headers={"X-Session-Id": session}
    )

    assert response.status_code == 404
    assert response.json()["error"] == Reason.CUSTOMER_NOT_FOUND.value


def test_api_malformed_filter_is_rejected(api_client, customer_session: str) -> None:
    response = api_client.get(
        "/api/transactions?limit=9999", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 400
    assert response.json()["error"] == Reason.INVALID_REQUEST.value


def test_api_missing_transaction_is_not_found(api_client, customer_session: str) -> None:
    response = api_client.get(
        "/api/transactions/TXN-999", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 404
    assert response.json()["error"] == Reason.TRANSACTION_NOT_FOUND.value


def test_api_candidates_support_amount_ranges(api_client, customer_session: str) -> None:
    response = api_client.get(
        "/api/transactions/candidates?amount_min=100&amount_max=500",
        headers={"X-Session-Id": customer_session},
    )

    assert response.status_code == 200
    assert [item["transaction_id"] for item in response.json()["candidates"]] == ["TXN-001"]


def test_api_unavailable_data_is_service_unavailable(api_client_without_data) -> None:
    response = api_client_without_data.get(
        f"/api/customers/{OWNER}/context", headers={"X-Session-Id": "anything"}
    )

    assert response.status_code == 401

    session = api_client_without_data.post("/api/sessions", json={"customer_id": OWNER}).json()
    response = api_client_without_data.get(
        f"/api/customers/{OWNER}/context",
        headers={"X-Session-Id": session["session_id"]},
    )

    assert response.status_code == 503
    assert response.json()["error"] == Reason.DATA_UNAVAILABLE.value
    assert "banking.duckdb" not in response.text


def test_api_audit_events_never_expose_the_session_id(api_client, customer_session: str) -> None:
    api_client.get(f"/api/customers/{OWNER}/context", headers={"X-Session-Id": customer_session})

    body = api_client.get("/api/audit/events").json()

    assert customer_session not in str(body)
    assert body["events"][0]["session_fingerprint"]


def test_api_transaction_not_found_is_indistinguishable(api_client, customer_session: str) -> None:
    foreign = api_client.get(
        "/api/transactions/TXN-004", headers={"X-Session-Id": customer_session}
    )
    absent = api_client.get("/api/transactions/TXN-999", headers={"X-Session-Id": customer_session})

    assert foreign.status_code == 404
    assert absent.status_code == 404
    assert foreign.json()["error"] == Reason.TRANSACTION_NOT_FOUND.value
    assert absent.json()["message"] == foreign.json()["message"]


def test_api_ownership_verification(api_client, customer_session: str) -> None:
    response = api_client.get(
        "/api/transactions/TXN-001/ownership", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 200
    assert response.json()["owned"] is True


def test_api_candidates_search(api_client, customer_session: str) -> None:
    response = api_client.get(
        "/api/transactions/candidates?transaction_type=Transfer",
        headers={"X-Session-Id": customer_session},
    )

    assert response.status_code == 200
    assert len(response.json()["candidates"]) == 2


def test_api_candidates_enforce_scope(api_client, customer_session: str) -> None:
    owned = api_client.get(
        f"/api/transactions/candidates?customer_id={OWNER}",
        headers={"X-Session-Id": customer_session},
    )
    foreign = api_client.get(
        f"/api/transactions/candidates?customer_id={OTHER}",
        headers={"X-Session-Id": customer_session},
    )

    assert owned.status_code == 200
    assert foreign.status_code == 403


def test_api_rejects_unknown_query_parameter(api_client, customer_session: str) -> None:
    response = api_client.get(
        "/api/transactions?merchant_name=foo", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 400
    assert response.json()["error"] == Reason.INVALID_REQUEST.value


def test_api_audit_events_are_returned(api_client, customer_session: str) -> None:
    api_client.get(f"/api/customers/{OWNER}/context", headers={"X-Session-Id": customer_session})
    response = api_client.get("/api/audit/events")

    assert response.status_code == 200
    body = response.json()
    assert body["events"]
    assert body["events"][0]["tool"] == "get_customer_context"
    assert body["events"][0]["outcome"] == "success"


def test_api_expired_session_is_unauthorized(
    api_client, service, customer_session: str, clock
) -> None:
    clock.advance(SESSION_TTL)
    response = api_client.get(
        f"/api/customers/{OWNER}/context", headers={"X-Session-Id": customer_session}
    )

    assert response.status_code == 401
    assert response.json()["error"] == Reason.EXPIRED_SESSION.value
