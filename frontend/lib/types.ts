// Types mirroring the backend API responses (see backend/app/schemas.py).

export type ProjectKind = "web" | "repo";
export type ScanStatus = "queued" | "running" | "completed" | "failed";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type Confidence = "high" | "medium" | "low";
export type FindingStatus =
  | "candidate"
  | "confirmed"
  | "disproven"
  | "inconclusive"
  | "untested"
  | "verification_failed";
export type EvidenceBasis =
  | "AI_REVIEWED"
  | "DYNAMIC_REPRODUCED"
  | "STATIC_CONFIRMED"
  | "DEPENDENCY_MATCH"
  | "CONFIG_OBSERVED"
  | "SECRET_MATCH";

export interface Project {
  id: string;
  name: string;
  kind: ProjectKind;
  target_url: string | null;
  repo_url: string | null;
  authorization_confirmed: boolean;
  authorization_note: string | null;
  created_at: string;
}

export interface ScannerReport {
  name: string;
  category: string;
  status: "completed" | "skipped" | "error";
  reason: string | null;
  findings?: number;
  errors?: string[];
  skipped_areas?: string[];
}

export interface ScanCoverage {
  scanners: ScannerReport[];
  errors: string[];
  skipped_areas: string[];
  duplicates_removed: number;
  findings_rejected_unsafe_path: number;
  total_findings: number;
  workspace_note: string | null;
}

export interface ScanJob {
  id: string;
  project_id: string;
  status: ScanStatus;
  mode: "mock" | "real";
  is_mock: boolean;
  coverage_note: string | null;
  coverage: ScanCoverage | null;
  error: string | null;
  requested_scanners: string[] | null;
  findings_count: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Finding {
  id: string;
  scan_job_id: string;
  project_id: string;
  title: string;
  vuln_class: string;
  severity: Severity;
  confidence: Confidence;
  status: FindingStatus;
  evidence_basis: EvidenceBasis;
  location: string | null;
  description: string | null;
  evidence: Record<string, unknown> | null;
  scanner: string | null;
  is_mock: boolean;
  created_at: string;
}

export interface NewProject {
  name: string;
  kind: ProjectKind;
  target_url?: string | null;
  repo_url?: string | null;
  authorization_confirmed: boolean;
  authorization_note?: string | null;
}
