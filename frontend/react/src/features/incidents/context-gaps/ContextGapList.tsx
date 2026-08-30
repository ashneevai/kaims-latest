import ContextEnrichmentProgress from "./ContextEnrichmentProgress";
import HumanEvidenceResponseForm from "./HumanEvidenceResponseForm";
import type { ContextGap } from "./contextGapSchemas";

interface Props {
  gaps: ContextGap[]; username: string; roleName: string; currentRcaVersion: number;
  onRespond: (gap: ContextGap, response: string, correction: boolean) => Promise<void>;
}

const HUMAN_ROLES = new Set(["admin", "administrator", "l2_engineer", "l3_engineer"]);

export default function ContextGapList({ gaps, username, roleName, currentRcaVersion, onRespond }: Props) {
  return <div className="context-gap-list">{gaps.map((gap) => {
    const request = gap.human_request;
    const terminal = ["expired", "cancelled"].includes(request?.status || gap.status);
    const answered = request?.status === "answered";
    const stale = gap.rca_version !== currentRcaVersion || (
      request?.binding_rca_version != null && request.binding_rca_version !== currentRcaVersion
    );
    const assigned = String(request?.expected_responder || gap.assigned_to || "").toLowerCase();
    const authorized = HUMAN_ROLES.has(roleName.toLowerCase()) && (
      ["admin", "administrator"].includes(roleName.toLowerCase()) || !assigned || assigned === username.toLowerCase()
    );
    const disabledReason = stale ? "This request belongs to an older RCA version. Refresh the incident."
      : terminal ? `This request is ${request?.status || gap.status}.`
      : !authorized ? "Only the assigned responder or an administrator can submit evidence."
      : answered ? "An immutable answer already exists; submit an explicit correction if required." : "";
    return <article className={`context-gap-card is-${gap.status}`} key={gap.requirement_id}>
      <header><div><span>{gap.priority} priority · {gap.category}</span><h4>{gap.question}</h4></div><b>{gap.status.replaceAll("_", " ")}</b></header>
      <p>{gap.reason}</p>
      {request ? <dl><div><dt>Hypothesis impact</dt><dd>{request.hypothesis_impact}</dd></div>
        <div><dt>Assigned to</dt><dd>{request.expected_responder}</dd></div>
        <div><dt>Due</dt><dd>{new Date(request.due_at).toLocaleString()}</dd></div>
        <div><dt>Jira</dt><dd>{request.jira_url ? <a href={request.jira_url} target="_blank" rel="noreferrer">{request.jira_issue_key} · {request.jira_status || "pending"}</a> : request.jira_issue_key || "Issue creation pending"}</dd></div></dl> : null}
      {request?.evidence_already_checked.length ? <p><strong>Sources already checked:</strong> {request.evidence_already_checked.join(", ")}</p> : null}
      <ContextEnrichmentProgress gap={gap} />
      {gap.response_history.length ? <details><summary>Immutable response history ({gap.response_history.length})</summary><ol>{gap.response_history.map((item) => <li key={item.response_id}><strong>v{item.response_version} · {item.responder_display || "Responder"}</strong><span>{new Date(item.received_at).toLocaleString()} · {item.source_type}</span><p>{item.response_text}</p><code>{item.evidence_id}</code></li>)}</ol></details> : null}
      {request ? <HumanEvidenceResponseForm disabled={stale || terminal || !authorized} disabledReason={disabledReason}
        correction={answered} onSubmit={(response, correction) => onRespond(gap, response, correction)} /> : null}
    </article>;
  })}</div>;
}
