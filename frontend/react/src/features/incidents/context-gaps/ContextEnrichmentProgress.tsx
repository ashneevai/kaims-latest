import { CheckCircle2, Clock3, RefreshCw, ShieldAlert } from "lucide-react";
import type { ContextGap } from "./contextGapSchemas";

export default function ContextEnrichmentProgress({ gap }: { gap: ContextGap }) {
  if (!gap.jobs.length) return null;
  return <div className="context-gap-jobs" aria-label="Automatic enrichment progress">
    {gap.jobs.map((job) => {
      const complete = job.status === "completed";
      const blocked = ["blocked", "failed"].includes(job.status);
      const Icon = complete ? CheckCircle2 : blocked ? ShieldAlert : job.status === "collecting" ? RefreshCw : Clock3;
      return <div key={job.job_id} className={`context-gap-job is-${job.status}`}>
        <Icon size={16} aria-hidden="true" className={job.status === "collecting" ? "is-spinning" : ""} />
        <span><strong>{job.connector_id}</strong><small>{job.status.replaceAll("_", " ")} · attempt {job.attempt_count}</small></span>
        {job.last_error ? <em>{job.last_error}</em> : null}
      </div>;
    })}
  </div>;
}

