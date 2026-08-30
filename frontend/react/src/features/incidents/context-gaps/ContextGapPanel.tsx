import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { fetchContextGaps, submitContextGapResponse } from "./contextGapApi";
import ContextGapList from "./ContextGapList";
import type { ContextGap, ContextGapInventory } from "./contextGapSchemas";
import "./contextGaps.css";

interface Props {
  incidentId: string; accessToken: string; username: string; roleName: string;
  currentRcaVersion: number; refreshKey?: string | number; onEvidenceChanged: () => Promise<unknown>;
}

export default function ContextGapPanel(props: Props) {
  const [inventory, setInventory] = useState<ContextGapInventory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!props.incidentId || !props.accessToken) return;
    setLoading(true); setError("");
    try { setInventory(await fetchContextGaps(props.incidentId, props.accessToken)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Context gaps are unavailable."); }
    finally { setLoading(false); }
  }, [props.incidentId, props.accessToken]);
  useEffect(() => { void load(); }, [load, props.refreshKey]);
  async function respond(gap: ContextGap, response: string, correction: boolean) {
    try {
      await submitContextGapResponse(props.incidentId, gap.requirement_id, response, props.accessToken, correction);
      await Promise.all([load(), props.onEvidenceChanged()]);
    } catch (reason) {
      const conflict = (reason as Error & { status?: number })?.status === 409;
      throw new Error(conflict ? "This RCA or context version is stale. Refresh and review the current request." : reason instanceof Error ? reason.message : "Response could not be saved.");
    }
  }
  if (!loading && !error && !inventory?.requirements.length) return null;
  return <section className="context-gap-panel" aria-labelledby="context-gap-title">
    <header><div><span>Autonomous context enrichment</span><h3 id="context-gap-title">Evidence gaps and human requests</h3><p>KaiMS continues collecting other evidence while this request is open.</p></div>
      <button type="button" className="button-secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={15} className={loading ? "is-spinning" : ""} />Refresh</button></header>
    {loading && !inventory ? <p className="context-gap-empty"><Search size={18} />Loading investigation work…</p> : null}
    {error ? <p className="error" role="alert">{error}</p> : null}
    {inventory ? <ContextGapList gaps={inventory.requirements} username={props.username} roleName={props.roleName}
      currentRcaVersion={props.currentRcaVersion} onRespond={respond} /> : null}
  </section>;
}

