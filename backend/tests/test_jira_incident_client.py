from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from monitoring_adapter.jira_client import JiraClient
from common.database import MonitoringIntegrationRecord
from common.repository import ContextEnrichmentRepository


@pytest.mark.asyncio
async def test_jira_client_uses_configured_project_issue_type_and_basic_auth(monkeypatch):
    requests = []

    async def request(self, method, url, **kwargs):
        requests.append((method, url, kwargs))
        return httpx.Response(201, json={"key": "KAN-42"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    client = JiraClient(
        "https://kaiops-test.atlassian.net", "service@example.com", "secret-token", "KAN", "Bug"
    )
    key = await client.create_issue(
        summary="Checkout incident", description="Bound incident details", severity="critical"
    )
    assert key == "KAN-42"
    payload = requests[0][2]["json"]["fields"]
    assert payload["project"] == {"key": "KAN"}
    assert payload["issuetype"] == {"name": "Bug"}
    assert client._auth == ("service@example.com", "secret-token")
    await client.close()


@pytest.mark.asyncio
async def test_jira_reconciliation_uses_overlapping_ordered_cursor(monkeypatch):
    captured = {}

    async def request(self, method, url, **kwargs):
        captured.update(kwargs["params"])
        return httpx.Response(200, json={"issues": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    client = JiraClient("https://kaiops-test.atlassian.net", "svc@example.com", "token", "KAN")
    await client.search_updated_issues(updated_since=datetime(2026, 8, 30, 10, 5, tzinfo=UTC))
    assert 'project = "KAN"' in captured["jql"]
    assert 'updated >= "2026-08-30 10:00"' in captured["jql"]
    assert "ORDER BY updated ASC, id ASC" in captured["jql"]
    assert "key >" not in captured["jql"]
    await client.close()


@pytest.mark.asyncio
async def test_jira_reconciliation_follows_every_next_page_token(monkeypatch):
    tokens = []

    async def request(self, method, url, **kwargs):
        token = kwargs["params"].get("nextPageToken")
        tokens.append(token)
        body = (
            {"issues": [{"id": "1", "key": "OPS-9"}], "nextPageToken": "page-2"}
            if token is None
            else {"issues": [{"id": "2", "key": "OPS-1"}]}
        )
        return httpx.Response(200, json=body, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    client = JiraClient("https://example.atlassian.net", "svc@example.com", "token", "OPS")
    issues = await client.search_updated_issues(
        updated_since=datetime(2026, 8, 30, 10, 5, tzinfo=UTC), after_issue_key="OPS-99",
    )
    assert [row["key"] for row in issues] == ["OPS-9", "OPS-1"]
    assert tokens == [None, "page-2"]
    await client.close()


@pytest.mark.asyncio
async def test_jira_actions_and_issue_bindings_are_connection_scoped(sqlite_session_factory):
    tenant_id = "tenant-a"
    incident_id = uuid4()
    request_id = uuid4()
    connections = [uuid4(), uuid4()]
    async with sqlite_session_factory() as session:
        for connection_id in connections:
            session.add(MonitoringIntegrationRecord(
                id=connection_id, tenant_id=tenant_id, project_name="OPS", provider="jira",
                status="active", active=True, auth_type="basic", endpoint_url="https://example.atlassian.net",
                webhook_path="/api/v1/alerts/jira", config_payload={}, validation_payload={},
            ))
        await session.flush()
        repo = ContextEnrichmentRepository(session)
        actions = [await repo.enqueue_jira_action(
            tenant_id=tenant_id, jira_connection_id=connection_id, incident_id=incident_id,
            action_type="ensure_hitl_issue", idempotency_key="same-logical-action",
            payload={"context_snapshot_id": str(uuid4())},
        ) for connection_id in connections]
        assert actions[0].action_id != actions[1].action_id
        payload = {
            "context_snapshot_id": str(uuid4()), "context_fingerprint": "a" * 64,
            "hitl_request_id": str(request_id), "rca_version": 1,
        }
        bindings = [await repo.bind_jira_hitl_issue(
            tenant_id=tenant_id, jira_connection_id=connection_id, incident_id=incident_id,
            jira_issue_key="OPS-42", jira_issue_id=str(index), jira_project_key="OPS",
            assignee_account_id="account-1", payload=payload,
        ) for index, connection_id in enumerate(connections, start=1)]
        assert bindings[0].binding_id != bindings[1].binding_id


@pytest.mark.asyncio
async def test_jira_webhook_receipt_is_durable_and_idempotent(sqlite_session_factory):
    connection_id = uuid4()
    updated_at = datetime(2026, 8, 31, 8, 15, tzinfo=UTC)
    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        first, created = await repo.record_jira_webhook_receipt(
            tenant_id="tenant-a", jira_connection_id=connection_id, jira_issue_id="10042",
            jira_updated_at=updated_at, event_id="event-42", payload_checksum="sha256:first",
        )
        await session.commit()
        assert created is True

    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        duplicate, created = await repo.record_jira_webhook_receipt(
            tenant_id="tenant-a", jira_connection_id=connection_id, jira_issue_id="10042",
            jira_updated_at=updated_at, event_id="event-42", payload_checksum="sha256:first",
        )
        assert created is False
        assert duplicate.receipt_id == first.receipt_id
        await repo.mark_jira_webhook_receipt(receipt_id=duplicate.receipt_id, status="processed")
        await session.commit()


@pytest.mark.asyncio
async def test_jira_poll_cursor_only_advances_on_success(sqlite_session_factory):
    connection_id = uuid4()
    first_updated = datetime(2026, 8, 31, 7, 0, tzinfo=UTC)
    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        first = await repo.save_jira_sync_cursor(
            tenant_id="tenant-a", jira_connection_id=connection_id, project_key="KAN",
            jira_updated_at=first_updated, issue_key="KAN-7", status="succeeded",
        )
        assert first.version == 1
        await session.commit()

    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        failed = await repo.save_jira_sync_cursor(
            tenant_id="tenant-a", jira_connection_id=connection_id, project_key="KAN",
            jira_updated_at=datetime(2026, 8, 31, 9, 0, tzinfo=UTC), issue_key="KAN-9",
            status="failed", error="temporary Jira failure",
        )
        assert failed.last_jira_updated_timestamp.replace(tzinfo=UTC) == first_updated
        assert failed.last_issue_key == "KAN-7"
        assert failed.poll_status == "failed"
        await session.commit()
