import { useState } from "react";

interface Props {
  disabled: boolean;
  disabledReason?: string;
  correction: boolean;
  onSubmit: (response: string, correction: boolean) => Promise<void>;
}

export default function HumanEvidenceResponseForm({ disabled, disabledReason, correction, onSubmit }: Props) {
  const [response, setResponse] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!response.trim() || disabled) return;
    setPending(true); setError("");
    try { await onSubmit(response.trim(), correction); setResponse(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Response could not be saved."); }
    finally { setPending(false); }
  }
  return <form className="context-gap-response" onSubmit={submit}>
    <label>Evidence response<textarea rows={3} value={response} disabled={disabled || pending}
      onChange={(event) => setResponse(event.target.value)}
      placeholder="Record the observation, source, and time window used to verify it." /></label>
    {disabledReason ? <p role="status">{disabledReason}</p> : null}
    {error ? <p className="error" role="alert">{error}</p> : null}
    <button className="button-primary" type="submit" disabled={disabled || pending || !response.trim()}>
      {pending ? "Saving immutable evidence…" : correction ? "Submit correction" : "Submit evidence"}
    </button>
  </form>;
}

