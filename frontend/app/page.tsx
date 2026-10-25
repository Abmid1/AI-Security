"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Finding, Project, ScanJob, Severity } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";
import { SeverityBadge, StatusBadge } from "@/components/Badges";

const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];
const SEV_COLORS: Record<Severity, string> = {
  critical: "#ff5c7a",
  high: "#ff9d4d",
  medium: "#ffd44d",
  low: "#5bc0de",
  info: "#8b96a5",
};

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listProjects(), api.listScans(), api.listFindings()])
      .then(([p, s, f]) => {
        setProjects(p);
        setScans(s);
        setFindings(f);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  const sevCounts = SEV_ORDER.map((sev) => ({
    sev,
    count: findings.filter((f) => f.severity === sev).length,
  }));
  const maxSev = Math.max(1, ...sevCounts.map((c) => c.count));
  const reproduced = findings.filter((f) => f.evidence_basis !== "AI_REVIEWED").length;
  const aiReviewed = findings.length - reproduced;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Dashboard</h1>
          <div className="sub">Overview of targets, scans and findings</div>
        </div>
        <Link href="/targets" className="btn">+ Add target</Link>
      </div>
      <div className="content">
        <MockBanner />

        {error && <div className="notice error">{error}</div>}
        {loading && <div className="muted">Loading…</div>}

        {!loading && !error && (
          <>
            <div className="grid cols-4">
              <div className="card">
                <h3>Targets</h3>
                <div className="stat">{projects.length}</div>
                <div className="stat-sub">{projects.filter((p) => p.kind === "web").length} web · {projects.filter((p) => p.kind === "repo").length} repo</div>
              </div>
              <div className="card">
                <h3>Scans</h3>
                <div className="stat">{scans.length}</div>
                <div className="stat-sub">{scans.filter((s) => s.status === "completed").length} completed</div>
              </div>
              <div className="card">
                <h3>Findings</h3>
                <div className="stat">{findings.length}</div>
                <div className="stat-sub">{findings.filter((f) => f.severity === "critical" || f.severity === "high").length} high/critical</div>
              </div>
              <div className="card">
                <h3>Evidence basis</h3>
                <div className="stat">{reproduced}<span className="muted" style={{ fontSize: 16 }}> / {aiReviewed}</span></div>
                <div className="stat-sub">reproduced / AI-reviewed only</div>
              </div>
            </div>

            <div className="grid cols-2" style={{ marginTop: 16 }}>
              <div className="card">
                <h3>Findings by severity</h3>
                <div className="bars" style={{ marginTop: 14 }}>
                  {sevCounts.map(({ sev, count }) => (
                    <div className="bar-row" key={sev}>
                      <span style={{ textTransform: "capitalize" }}>{sev}</span>
                      <span className="bar-track">
                        <span className="bar-fill" style={{ width: `${(count / maxSev) * 100}%`, background: SEV_COLORS[sev] }} />
                      </span>
                      <span className="muted" style={{ textAlign: "right" }}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <h3>Recent scans</h3>
                {scans.length === 0 ? (
                  <div className="muted" style={{ marginTop: 10 }}>No scans yet.</div>
                ) : (
                  <table className="table" style={{ marginTop: 10 }}>
                    <tbody>
                      {scans.slice(0, 5).map((s) => {
                        const proj = projects.find((p) => p.id === s.project_id);
                        return (
                          <tr key={s.id}>
                            <td>{proj?.name ?? s.project_id}</td>
                            <td><span className="tag">{s.status}</span></td>
                            <td style={{ textAlign: "right" }}>{s.findings_count} findings</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="section-title">Latest findings</div>
            {findings.length === 0 ? (
              <div className="empty">No findings yet. Add a target and run a (mock) scan.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Finding</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Class</th>
                  </tr>
                </thead>
                <tbody>
                  {findings.slice(0, 6).map((f) => (
                    <tr key={f.id}>
                      <td><Link href="/findings" style={{ color: "var(--accent)" }}>{f.title}</Link></td>
                      <td><SeverityBadge severity={f.severity} /></td>
                      <td><StatusBadge status={f.status} /></td>
                      <td className="muted">{f.vuln_class}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </>
  );
}
