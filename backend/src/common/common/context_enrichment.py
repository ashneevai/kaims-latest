from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from ai_workbench_common.models import Context

from common.context_enrichment_contract import EvidenceRequirement
from common.tenant_identity import require_tenant_id

_CATEGORIES = {
    "metrics", "logs", "traces", "topology", "deployment", "change",
    "source_code", "database", "ticket", "runbook", "ownership",
    "business_impact", "validation",
}
_ALIASES = {
    "metric": "metrics", "telemetry": "metrics", "prometheus": "metrics",
    "log": "logs", "trace": "traces", "deployments": "deployment",
    "changes": "change", "code": "source_code", "source": "source_code",
    "tickets": "ticket", "jira": "ticket", "rag": "runbook",
    "knowledge": "runbook", "cmdb": "topology", "kubernetes": "topology",
    "dependency": "topology", "mysql": "database",
}
_CONNECTORS = {
    "metrics": ["prometheus"], "logs": ["opensearch"], "traces": ["jaeger"],
    "topology": ["discovery-mcp", "cmdb"], "deployment": ["deployment-history"],
    "change": ["jira", "source-control"], "source_code": ["source-control"],
    "database": ["database-observer"], "ticket": ["jira"],
    "runbook": ["vector-db"], "validation": ["prometheus"],
}
_HUMAN_CATEGORIES = {"ownership", "business_impact"}
_PRIORITIES = {"critical", "high", "medium", "low"}


def _canonical_question(value: Any, category: str) -> str:
    question = re.sub(r"\s+", " ", str(value or "").strip())
    return question or f"Collect {category} evidence for this incident."


def plan_missing_evidence(
    *,
    tenant_id: str,
    incident_id: UUID,
    rca_version: int,
    investigation_report: dict[str, Any],
    context: Context,
    now: datetime,
) -> list[EvidenceRequirement]:
    """Create stable, identity-bound requirements from declared investigation gaps."""
    governed_tenant = require_tenant_id(tenant_id, source="context enrichment request")
    if require_tenant_id(context.tenant_id, source="context enrichment context") != governed_tenant:
        raise ValueError("context enrichment tenant mismatch")
    if UUID(str(context.incident_id)) != incident_id:
        raise ValueError("context enrichment incident mismatch")

    raw_gaps = investigation_report.get("missing_evidence") or investigation_report.get("missing_sources") or []
    requirements: list[EvidenceRequirement] = []
    for raw_gap in raw_gaps:
        gap = raw_gap if isinstance(raw_gap, dict) else {"category": raw_gap}
        raw_category = str(gap.get("category") or gap.get("source") or raw_gap).strip().lower()
        category = _ALIASES.get(raw_category, raw_category)
        if category not in _CATEGORIES:
            continue
        question = _canonical_question(gap.get("question"), category)
        priority = str(gap.get("priority") or "high").strip().lower()
        if priority not in _PRIORITIES:
            priority = "high"
        connectors = [
            str(value).strip()
            for value in (gap.get("candidate_connectors") or _CONNECTORS.get(category, []))
            if str(value).strip()
        ]
        mode = (
            "human_required"
            if category in _HUMAN_CATEGORIES
            else "automatic" if connectors else "connector_required"
        )
        identity = ":".join(
            (governed_tenant, str(incident_id), str(max(1, rca_version)), category, question.casefold())
        )
        requirements.append(
            EvidenceRequirement(
                requirement_id=uuid5(NAMESPACE_URL, identity),
                tenant_id=governed_tenant,
                incident_id=incident_id,
                rca_version=max(1, rca_version),
                category=category,
                question=question,
                reason=str(gap.get("reason") or "Required to test the current RCA hypothesis."),
                priority=priority,
                collection_mode=mode,
                candidate_connectors=connectors,
                status="identified",
                created_at=now,
                updated_at=now,
            )
        )
    return requirements
