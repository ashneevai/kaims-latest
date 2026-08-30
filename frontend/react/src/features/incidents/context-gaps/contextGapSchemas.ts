import { z } from "zod";

export const contextGapJobSchema = z.object({
  job_id: z.string(), connector_id: z.string(), status: z.string(),
  attempt_count: z.number().default(0), available_at: z.string().nullish(),
  last_error: z.string().nullish(), updated_at: z.string().nullish(),
});

export const humanRequestSchema = z.object({
  request_id: z.string(), status: z.string(), expected_responder: z.string(),
  due_at: z.string(), acceptable_format: z.string(), investigation_can_continue: z.boolean(),
  evidence_already_checked: z.array(z.string()).default([]), hypothesis_impact: z.string(),
  version: z.number(), jira_issue_key: z.string().nullish(), jira_status: z.string().nullish(),
  jira_url: z.string().url().nullish(), ownership: z.string().nullish(),
  closure_authority: z.string().nullish(), binding_rca_version: z.number().nullish(),
});

export const contextGapResponseSchema = z.object({
  response_id: z.string(), response_version: z.number(), responder_display: z.string().nullish(),
  source_type: z.string(), source_reference: z.string().nullish(), response_text: z.string(),
  evidence_id: z.string(), received_at: z.string(),
});

export const contextGapSchema = z.object({
  requirement_id: z.string(), tenant_id: z.string(), incident_id: z.string(), rca_version: z.number(),
  category: z.string(), question: z.string(), reason: z.string(), priority: z.string(),
  collection_mode: z.string(), candidate_connectors: z.array(z.string()).default([]),
  status: z.string(), retry_count: z.number(), retry_after: z.string().nullish(),
  assigned_to: z.string().nullish(), jira_issue_key: z.string().nullish(),
  evidence_ids: z.array(z.string()).default([]), version: z.number(),
  created_at: z.string(), updated_at: z.string(), jobs: z.array(contextGapJobSchema).default([]),
  human_request: humanRequestSchema.nullish(),
  response_history: z.array(contextGapResponseSchema).default([]),
});

export const contextGapInventorySchema = z.object({
  incident_id: z.string(), tenant_id: z.string(), requirements: z.array(contextGapSchema), count: z.number(),
});

export type ContextGap = z.infer<typeof contextGapSchema>;
export type ContextGapInventory = z.infer<typeof contextGapInventorySchema>;

