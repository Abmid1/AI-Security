// Typed client for the FastAPI backend. All calls go from the browser to the
// backend base URL. No secrets are ever held here.

import type { Finding, NewProject, Project, ScanJob } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is it running on " + API_BASE + "?");
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, body?.detail ?? body ?? res.statusText);
  }
  return body as T;
}

export const api = {
  base: API_BASE,

  health: () => request<{ status: string; version: string; mock_mode: boolean }>("/api/health"),

  listProjects: () => request<Project[]>("/api/projects"),
  createProject: (p: NewProject) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify(p) }),

  listScans: (projectId?: string) =>
    request<ScanJob[]>(`/api/scans${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
  startScan: (projectId: string, mode: "mock" | "real" = "mock") =>
    request<ScanJob>("/api/scans", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, mode }),
    }),

  listFindings: (opts?: { scanId?: string; projectId?: string }) => {
    const qs = new URLSearchParams();
    if (opts?.scanId) qs.set("scan_id", opts.scanId);
    if (opts?.projectId) qs.set("project_id", opts.projectId);
    const q = qs.toString();
    return request<Finding[]>(`/api/findings${q ? `?${q}` : ""}`);
  },
  generateFix: (findingId: string) =>
    request<{ status: string; message: string; finding_id: string }>(
      `/api/findings/${encodeURIComponent(findingId)}/fix`,
      { method: "POST" },
    ),
};
