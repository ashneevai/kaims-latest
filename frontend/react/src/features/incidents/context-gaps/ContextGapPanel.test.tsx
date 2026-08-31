// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ContextGapPanel from "./ContextGapPanel";

const inventory = {
  incident_id: "incident-1", tenant_id: "tenant-a", count: 1,
  requirements: [{
    requirement_id: "requirement-1", tenant_id: "tenant-a", incident_id: "incident-1",
    rca_version: 3, category: "traces", question: "Which downstream call became slow?",
    reason: "The causal path is incomplete", priority: "high", collection_mode: "human_required",
    candidate_connectors: ["jaeger"], status: "human_requested", retry_count: 1,
    retry_after: null, assigned_to: "operator", jira_issue_key: "OPS-42", evidence_ids: [],
    version: 2, created_at: "2026-08-31T08:00:00Z", updated_at: "2026-08-31T08:02:00Z",
    jobs: [{ job_id: "job-1", connector_id: "jaeger", status: "retrying", attempt_count: 1,
      available_at: "2026-08-31T08:05:00Z", last_error: "timeout", updated_at: "2026-08-31T08:02:00Z" }],
    human_request: { request_id: "request-1", status: "pending", expected_responder: "operator",
      due_at: "2026-08-31T10:00:00Z", acceptable_format: "trace identifier", investigation_can_continue: true,
      evidence_already_checked: ["logs"], hypothesis_impact: "Confirms the downstream dependency",
      version: 1, jira_issue_key: "OPS-42", jira_status: "In Progress",
      jira_url: "https://example.atlassian.net/browse/OPS-42", ownership: "human",
      closure_authority: "jira", binding_rca_version: 3 }, response_history: [],
  }],
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("ContextGapPanel", () => {
  it("renders automatic progress, Jira HITL state, and submits evidence", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        trace_id: "trace-1", gateway: { path: "/incidents/incident-1/context-gaps" }, data: inventory,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ evidence_id: "HUMAN-1" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(inventory), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const refresh = vi.fn().mockResolvedValue(undefined);
    render(<ContextGapPanel incidentId="incident-1" accessToken="token" username="operator"
      roleName="l2_engineer" currentRcaVersion={3} onEvidenceChanged={refresh} />);

    expect(await screen.findByText("Which downstream call became slow?")).toBeInTheDocument();
    expect(screen.queryByText(/invalid_type/)).not.toBeInTheDocument();
    expect(screen.getByText(/KaiMS continues collecting other evidence/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /OPS-42/ })).toHaveAttribute("href", "https://example.atlassian.net/browse/OPS-42");
    expect(screen.getByText(/retrying · attempt 1/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Evidence response"), { target: { value: "Trace abc confirms inventory latency." } });
    fireEvent.click(screen.getByRole("button", { name: "Submit evidence" }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      response: "Trace abc confirms inventory latency.", correction: false,
    });
  });

  it("shows a visible stale-version conflict and disables submission", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(inventory), { status: 200 }),
    ));
    render(<ContextGapPanel incidentId="incident-1" accessToken="token" username="operator"
      roleName="l2_engineer" currentRcaVersion={4} onEvidenceChanged={vi.fn()} />);
    expect(await screen.findByText(/older RCA version/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit evidence" })).toBeDisabled();
  });
});
