import { z } from "zod";

const WorkerSchema = z.object({ state: z.string(), enabled: z.boolean() });

export const JiraLifecycleStatusSchema = z.object({
  status: z.enum(["ready", "configuration_required"]),
  tenant_id: z.string(),
  configured: z.object({
    base_url: z.boolean(), service_account_email: z.boolean(), api_token: z.boolean(),
    project_key: z.boolean(), issue_type: z.boolean(), webhook_secret: z.boolean(),
  }),
  missing_outbound_settings: z.array(z.string()),
  outbound_ready: z.boolean(),
  webhook_ready: z.boolean(),
  durable_connection: z.object({
    id: z.string(), tenant_id: z.string(), project_key: z.string(), active: z.boolean(),
    endpoint_url: z.string().nullable(),
  }).nullable(),
  poll_cursor: z.object({
    status: z.string().nullable(), last_issue_key: z.string().nullable(),
    last_jira_updated_at: z.string().nullable(), last_polled_at: z.string().nullable(), version: z.number(),
  }).nullable(),
  workers: z.object({ poll: WorkerSchema, actions: WorkerSchema }),
});

export type JiraLifecycleStatus = z.infer<typeof JiraLifecycleStatusSchema>;
