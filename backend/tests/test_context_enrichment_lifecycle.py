from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from ai_workbench_common.models import Context
from common.context_enrichment import plan_missing_evidence as plan_missing_evidence_shared
from common.context_enrichment_contract import EvidenceRequirement, HitlRoutingConfiguration
from common.database import HumanEvidenceResponseVersionRecord
from common.models import Alert, AlertSeverity
from common.repository import ContextEnrichmentRepository
from context_agent.connectors import execute_enrichment_plan
from context_agent.context_quality import plan_missing_evidence
from sqlalchemy import select


def context_for(incident_id, *, tenant_id="tenant-a") -> Context:
    alert = Alert(
        tenant_id=tenant_id, source="prometheus", name="LatencyHigh",
        service="checkout-api", environment="prod", severity=AlertSeverity.CRITICAL,
        description="p99 latency is above threshold",
    )
    return Context(tenant_id=tenant_id, incident_id=incident_id, alert=alert)


def test_shared_planner_validates_identity_normalizes_priority_and_keeps_stable_ids():
    incident_id = uuid4()
    context = context_for(incident_id)
    report = {
        "missing_evidence": [
            {"category": "logs", "question": " Which errors preceded the alert? ", "priority": "urgent"}
        ]
    }
    kwargs = {
        "tenant_id": "tenant-a",
        "incident_id": incident_id,
        "rca_version": 2,
        "investigation_report": report,
        "context": context,
        "now": datetime.now(UTC),
    }
    first = plan_missing_evidence_shared(**kwargs)
    second = plan_missing_evidence_shared(**kwargs)
    assert first[0].priority == "high"
    assert first[0].requirement_id == second[0].requirement_id

    with pytest.raises(ValueError, match="tenant mismatch"):
        plan_missing_evidence_shared(**{**kwargs, "tenant_id": "tenant-b"})
    with pytest.raises(ValueError, match="incident mismatch"):
        plan_missing_evidence_shared(**{**kwargs, "incident_id": uuid4()})


@pytest.mark.asyncio
async def test_missing_automatic_evidence_creates_idempotent_enrichment_jobs(
    sqlite_session_factory,
):
    incident_id = uuid4()
    requirements = await plan_missing_evidence(
        context_for(incident_id),
        {"tenant_id": "tenant-a", "incident_id": str(incident_id), "rca_version": 2,
         "missing_evidence": [{"category": "logs", "question": "Which errors preceded the alert?"}]},
    )
    result = await execute_enrichment_plan(requirements, authorized_connectors={"opensearch"})
    assert result.scheduled_requirement_ids == [requirements[0].requirement_id]

    now = datetime.now(UTC)
    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        await repo.upsert_context_evidence_requirements(requirements)
        first = await repo.schedule_context_enrichment_job(
            tenant_id="tenant-a", incident_id=incident_id,
            requirement_id=requirements[0].requirement_id, connector_id="opensearch",
            query_payload={"service": "checkout-api", "environment": "prod"},
            observation_start=now - timedelta(minutes=10), observation_end=now,
        )
        second = await repo.schedule_context_enrichment_job(
            tenant_id="tenant-a", incident_id=incident_id,
            requirement_id=requirements[0].requirement_id, connector_id="opensearch",
            query_payload={"service": "checkout-api", "environment": "prod"},
            observation_start=now - timedelta(minutes=10), observation_end=now,
        )
        assert first.job_id == second.job_id


@pytest.mark.asyncio
async def test_connector_unavailable_becomes_human_request_without_stopping_other_work(
    sqlite_session_factory,
):
    incident_id = uuid4()
    requirements = await plan_missing_evidence(
        context_for(incident_id),
        {"tenant_id": "tenant-a", "incident_id": str(incident_id), "rca_version": 1,
         "missing_evidence": ["logs", "ownership"]},
    )
    result = await execute_enrichment_plan(requirements, authorized_connectors={"opensearch"})
    assert len(result.scheduled_requirement_ids) == 1
    assert len(result.human_requirement_ids) == 1

    human_requirement = next(row for row in requirements if row.collection_mode == "human_required")
    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        await repo.upsert_context_evidence_requirements(requirements)
        request = await repo.create_human_evidence_request(
            tenant_id="tenant-a", incident_id=incident_id,
            requirement_id=human_requirement.requirement_id,
            expected_responder="checkout-service-owner", due_at=datetime.now(UTC) + timedelta(hours=1),
            acceptable_format="Account ID or governed support group",
            evidence_already_checked=["cmdb", "service-catalog"],
            hypothesis_impact="Determines the authorized approver",
            investigation_can_continue=True,
        )
        assert request.investigation_can_continue is True


@pytest.mark.asyncio
async def test_enrichment_job_leases_are_exclusive_reclaimable_and_retry_with_backoff(
    sqlite_session_factory,
):
    incident_id = uuid4()
    requirements = await plan_missing_evidence(
        context_for(incident_id),
        {
            "tenant_id": "tenant-a", "incident_id": str(incident_id), "rca_version": 1,
            "missing_evidence": ["logs"],
        },
    )
    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        await repo.upsert_context_evidence_requirements(requirements)
        now = datetime.now(UTC)
        job = await repo.schedule_context_enrichment_job(
            tenant_id="tenant-a", incident_id=incident_id,
            requirement_id=requirements[0].requirement_id, connector_id="opensearch",
            query_payload={"rca_version": 1, "observation_window_version": "snapshot-1"},
            observation_start=now - timedelta(minutes=10), observation_end=now,
        )
        claimed = await repo.claim_context_enrichment_jobs(worker_id="worker-a", limit=10, lease_seconds=30)
        assert [row.job_id for row in claimed] == [job.job_id]
        assert await repo.claim_context_enrichment_jobs(worker_id="worker-b", limit=10, lease_seconds=30) == []

        job.status = "retry"
        job.available_at = now - timedelta(seconds=1)
        job.lease_expires_at = now - timedelta(seconds=1)
        reclaimed = await repo.claim_context_enrichment_jobs(worker_id="worker-b", limit=10, lease_seconds=30)
        assert [row.job_id for row in reclaimed] == [job.job_id]
        await repo.retry_context_enrichment_job(
            job_id=job.job_id, worker_id="worker-b", error="temporary outage", retry_after_seconds=60,
        )
        retry_at = job.available_at.replace(tzinfo=UTC) if job.available_at.tzinfo is None else job.available_at
        assert retry_at >= datetime.now(UTC) + timedelta(seconds=55)


@pytest.mark.asyncio
async def test_human_response_is_tenant_scoped_and_recorded_as_assertion(sqlite_session_factory):
    incident_id = uuid4()
    requirement = EvidenceRequirement(
        requirement_id=uuid4(), tenant_id="tenant-a", incident_id=incident_id,
        rca_version=1, category="business_impact", question="Is checkout customer-facing?",
        reason="Impact classification requires business ownership", priority="high",
        collection_mode="human_required", created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        await repo.upsert_context_evidence_requirements([requirement])
        await repo.create_human_evidence_request(
            tenant_id="tenant-a", incident_id=incident_id, requirement_id=requirement.requirement_id,
            expected_responder="checkout-product-owner", due_at=datetime.now(UTC) + timedelta(hours=1),
            acceptable_format="yes/no with service catalog link", evidence_already_checked=["cmdb"],
            hypothesis_impact="Changes customer-impact classification",
        )
        with pytest.raises(LookupError):
            await repo.record_human_evidence_response(
                tenant_id="tenant-b", incident_id=incident_id, requirement_id=requirement.requirement_id,
                response={"response": "yes", "responder_id": "owner-a", "responded_at": datetime.now(UTC).isoformat()},
            )
        with pytest.raises(PermissionError, match="assigned HITL"):
            await repo.record_human_evidence_response(
                tenant_id="tenant-a", incident_id=incident_id, requirement_id=requirement.requirement_id,
                response={"response": "yes", "responder_id": "owner-a", "responded_at": datetime.now(UTC).isoformat()},
            )
        recorded = await repo.record_human_evidence_response(
            tenant_id="tenant-a", incident_id=incident_id, requirement_id=requirement.requirement_id,
            response={
                "response": "yes", "responder_id": "checkout-product-owner",
                "responded_at": datetime.now(UTC).isoformat(),
            },
        )
        assert recorded["evidence_id"].startswith("HUMAN-")
        gaps = await repo.list_context_evidence_requirements(
            tenant_id="tenant-a", incident_id=incident_id,
        )
        assert gaps[0]["status"] == "answered"
        assert gaps[0]["evidence_ids"] == [recorded["evidence_id"]]
        assert gaps[0]["human_request"]["status"] == "answered"
        assert gaps[0]["human_request"]["expected_responder"] == "checkout-product-owner"
        assert gaps[0]["response_history"][0]["response_text"] == "yes"
        assert gaps[0]["response_history"][0]["evidence_id"] == recorded["evidence_id"]
        with pytest.raises(ValueError, match="explicit correction"):
            await repo.record_human_evidence_response(
                tenant_id="tenant-a", incident_id=incident_id, requirement_id=requirement.requirement_id,
                response={
                    "response": "corrected", "responder_id": "checkout-product-owner",
                    "responded_at": datetime.now(UTC).isoformat(),
                },
            )
        corrected = await repo.record_human_evidence_response(
            tenant_id="tenant-a", incident_id=incident_id, requirement_id=requirement.requirement_id,
            response={
                "response": "corrected", "responder_id": "checkout-product-owner",
                "responded_at": datetime.now(UTC).isoformat(), "correction": True,
            },
        )
        assert corrected["response_version"] == 2
        rows = (await session.execute(
            select(HumanEvidenceResponseVersionRecord).order_by(
                HumanEvidenceResponseVersionRecord.response_version
            )
        )).scalars().all()
        assert [row.response_text for row in rows] == ["yes", "corrected"]
        assert rows[1].supersedes_response_id == rows[0].response_id


def test_hitl_routing_configuration_rejects_placeholder_identity():
    with pytest.raises(ValueError, match="explicit governed identities"):
        HitlRoutingConfiguration(
            default_approver_group="admin", l2_group="checkout-l2", l3_group="checkout-l3",
            service_owner="checkout-owner", timezone="Asia/Calcutta", business_hours={},
            severity_sla_minutes={"critical": 15}, jira_project_key="KAN", jira_issue_type="Bug",
            jira_transition_mapping={"approved": "31"}, fallback_assignment_group="platform-l2",
        )
