import { contextGapInventoryResponseSchema, type ContextGapInventory } from "./contextGapSchemas";

async function apiRequest(path: string, accessToken: string, init?: RequestInit) {
  const response = await fetch(`/api-gateway${path}`, {
    ...init,
    headers: {
      Accept: "application/json", "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...init?.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload?.detail === "string"
      ? payload.detail : payload?.error?.message || `HTTP ${response.status}`;
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return payload;
}

export async function fetchContextGaps(
  incidentId: string, accessToken: string,
): Promise<ContextGapInventory> {
  return contextGapInventoryResponseSchema.parse(
    await apiRequest(`/incidents/${encodeURIComponent(incidentId)}/context-gaps`, accessToken),
  );
}

export async function submitContextGapResponse(
  incidentId: string, requirementId: string, response: string,
  accessToken: string, correction = false,
) {
  return apiRequest(
    `/incidents/${encodeURIComponent(incidentId)}/context-gaps/${encodeURIComponent(requirementId)}/responses`,
    accessToken,
    { method: "POST", body: JSON.stringify({ response, correction }) },
  );
}
