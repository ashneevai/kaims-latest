ALTER TABLE jira_incident_bindings
  ADD COLUMN jira_connection_id CHAR(32) NULL AFTER tenant_id,
  ADD COLUMN jira_issue_id VARCHAR(64) NULL AFTER jira_issue_key,
  ADD COLUMN jira_status_id VARCHAR(64) NULL AFTER jira_status,
  ADD COLUMN jira_status_category VARCHAR(64) NULL AFTER jira_status_id,
  ADD COLUMN jira_assignee_account_id VARCHAR(255) NULL AFTER assignee_id,
  ADD COLUMN jira_updated_at DATETIME(6) NULL AFTER last_jira_updated_at,
  ADD COLUMN closure_authority VARCHAR(16) NOT NULL DEFAULT 'jira' AFTER ownership,
  ADD COLUMN binding_purpose VARCHAR(32) NOT NULL DEFAULT 'human_evidence' AFTER closure_authority,
  ADD COLUMN hitl_request_id CHAR(36) NULL AFTER binding_purpose,
  ADD COLUMN webhook_version INT NOT NULL DEFAULT 1 AFTER binding_version,
  DROP INDEX uq_jira_binding_issue,
  ADD UNIQUE KEY uq_jira_binding_connection_issue
    (tenant_id, jira_connection_id, jira_issue_key),
  ADD KEY idx_jira_binding_connection (tenant_id, jira_connection_id);

ALTER TABLE jira_sync_cursors
  ADD COLUMN jira_connection_id CHAR(32) NULL AFTER tenant_id,
  DROP INDEX uq_jira_sync_cursor,
  ADD UNIQUE KEY uq_jira_sync_cursor_connection
    (tenant_id, jira_connection_id, jira_project_key),
  ADD KEY idx_jira_cursor_connection (tenant_id, jira_connection_id);

CREATE TABLE human_evidence_response_versions (
  response_id CHAR(36) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(128) NOT NULL,
  incident_id CHAR(36) NOT NULL,
  requirement_id CHAR(36) NOT NULL,
  request_id CHAR(36) NOT NULL,
  response_version INT NOT NULL,
  responder_id VARCHAR(255) NOT NULL,
  responder_display VARCHAR(255) NULL,
  source_type VARCHAR(32) NOT NULL,
  source_reference VARCHAR(1536) NULL,
  response_text TEXT NOT NULL,
  evidence_id VARCHAR(128) NOT NULL,
  content_checksum VARCHAR(71) NOT NULL,
  supersedes_response_id CHAR(36) NULL,
  received_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_human_response_version (tenant_id, request_id, response_version),
  UNIQUE KEY uq_human_response_evidence (tenant_id, evidence_id),
  KEY idx_human_response_incident (tenant_id, incident_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE jira_action_outbox (
  action_id CHAR(36) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(128) NOT NULL,
  jira_connection_id CHAR(32) NOT NULL,
  incident_id CHAR(36) NOT NULL,
  binding_id CHAR(36) NULL,
  action_type VARCHAR(32) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  payload JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  attempt_count INT NOT NULL DEFAULT 0,
  available_at DATETIME(6) NOT NULL,
  lease_owner VARCHAR(255) NULL,
  lease_expires_at DATETIME(6) NULL,
  last_error TEXT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_jira_action_idempotency (tenant_id, jira_connection_id, idempotency_key),
  KEY idx_jira_action_claim (status, available_at, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE jira_webhook_receipts (
  receipt_id CHAR(36) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(128) NOT NULL,
  jira_connection_id CHAR(32) NOT NULL,
  jira_issue_id VARCHAR(64) NOT NULL,
  jira_updated_at DATETIME(6) NOT NULL,
  event_id VARCHAR(255) NOT NULL,
  webhook_version INT NOT NULL DEFAULT 1,
  payload_checksum VARCHAR(71) NOT NULL,
  processing_status VARCHAR(32) NOT NULL DEFAULT 'received',
  processing_error TEXT NULL,
  received_at DATETIME(6) NOT NULL,
  processed_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_jira_webhook_event (jira_connection_id, event_id),
  UNIQUE KEY uq_jira_webhook_issue_update
    (jira_connection_id, jira_issue_id, jira_updated_at, event_id),
  KEY idx_jira_webhook_processing (processing_status, received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
