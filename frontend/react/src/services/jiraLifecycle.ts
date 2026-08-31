import { queryOptions } from "@tanstack/react-query";
import { JiraLifecycleStatusSchema } from "../schemas/jiraLifecycle";
import { getValidated } from "./apiClient";

export const jiraLifecycleKeys = { status: ["integrations", "jira", "status"] as const };

export function jiraLifecycleStatusQueryOptions(token: string) {
  return queryOptions({
    queryKey: [...jiraLifecycleKeys.status, Boolean(token)],
    queryFn: ({ signal }) => getValidated("/api-gateway/monitoring/jira/status", JiraLifecycleStatusSchema, {
      signal,
      headers: { Authorization: `Bearer ${token}` },
      timeoutMs: 15_000,
    }),
    enabled: Boolean(token),
    refetchInterval: 30_000,
    refetchOnMount: "always",
  });
}
