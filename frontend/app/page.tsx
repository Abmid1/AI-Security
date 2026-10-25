"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Finding, Project, ScanJob, Severity } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";
import { SevCounts, SeverityBadge, StatusBadge, SEV_COLORS } from "@/components/Badges";
import { Donut, Sparkline } from "@/components/Charts";
import { IconArrowRight, IconPlus } from "@/components/Icons";

const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

// Deterministic posture score: each open finding deducts weight by severity.
// Shown with its formula so the number is never mistaken for a judgement.
const SEV_WEIGHT: Record<Severity, number> = {
  critical: 18,
  high: 10,
  medium: 4,
  low: 1.5,
  info: 0.5,
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

  const stats = useMemo(() => {
    const bySev = (sev: Severity) => findings.filter((f) => f.severity === sev).length;
    const counts = Object.fromEntries(SEV_ORDER.map((s) => [s, bySev(s)])) as Record<Severity, number>;

    const deduction = SEV_ORDER.reduce((sum, s) => sum + counts[s] * SEV_WEIGHT[s], 0);
    const score = Math.max(0, Math.round((100 - deduction) * 10) / 10);

    const open = findings.filter((f) => f.status !== "disproven").length;
    const reproduced = findings.filter((f) => f.evidence_basis !== "AI_REVIEWED").length;

    // Per-project severity rollup, worst first.
    const assets = projects
      .map((p) => {
        const own = findings.filter((f) => f.project_id === p.id);
        const c = Object.fromEntries(
          SEV_ORDER.map((s) => [s, own.filter((f) => f.severity === s).length]),
        ) as Record<Severity, number>;
        const weight = SEV_ORDER.reduce((sum, s) => sum + c[s] * SEV_WEIGHT[s], 0);
        return { project: p, counts: c, weight, total: own.length };
      })
      .filter((a) => a.total > 0)
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 5);

    // Cumulative findings discovered across the scan timeline.
    const ordered = [...scans].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    let running = 0;
    const trend = ordered.map((s) => (running += s.findings_count));

    return { counts, score, open, reproduced, assets, trend };
  }, [findings, projects, scans]);

  const topIssues = useMemo(
    () =>
      [...findings]
        .sort(
          (a, b) =>
            SEV_WEIGHT[b.severity] - SEV_WEIGHT[a.severity] ||
            a.title.localeCompare(b.title),
        )
        .slice(0, 5),
    [findings],
  );

  const slices = SEV_ORDER.filter((s) => stats.counts[s] > 0).map((s) => ({
    label: s,
    value: stats.counts[s],
    color: SEV_COLORS[s],
  }));

  const criticalCount = stats.counts.critical + stats.counts.high;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Security Dashboard</h1>
          <div className="sub">Posture across every connected target</div>
        </div>
        <div className="topbar-actions">
          <Link href="/scans" className="btn secondary">
            Run a scan
          </Link>
          <Link href="/targets" className="btn">
            <IconPlus size={15} />
            New target
          </Link>
        </div>
      </div>

      <div className="content">
        <MockBanner />

        {error && (
          <div className="notice error">
            <div>
              <strong>Could not load data.</strong> {error}
            </div>
          </div>
        )}

        {loading ? (
          <LoadingState />
        ) : (
          <>
            <div className="metrics">
              <div className="metric">
                <div className="metric-label">Posture Score</div>
                <div className="metric-value">
                  {stats.score}
                  <span className="metric-unit">/ 100</span>
                </div>
                <div className="metric-note" title="100 minus weighted severity of all findings">
                  Weighted by severity
                </div>
              </div>
              <div className="metric">
                <div className="metric-label">Findings</div>
                <div className="metric-value">{findings.length}</div>
                <div className={`metric-note ${criticalCount > 0 ? "crit" : ""}`}>
                  {criticalCount} critical &amp; high
                </div>
              </div>
              <div className="metric">
                <div className="metric-label">With Evidence</div>
                <div className="metric-value">{stats.reproduced}</div>
                <div className="metric-note">
                  {findings.length - stats.reproduced} AI-reviewed only
                </div>
              </div>
              <div className="metric">
                <div className="metric-label">Scans</div>
                <div className="metric-value">{scans.length}</div>
                <div className="metric-note">
                  {scans.filter((s) => s.mode === "real").length} real ·{" "}
                  {scans.filter((s) => s.mode === "mock").length} mock
                </div>
              </div>
              <div className="metric">
                <div className="metric-label">Targets</div>
                <div className="metric-value">{projects.length}</div>
                <div className="metric-note">
                  {projects.filter((p) => p.kind === "web").length} web ·{" "}
                  {projects.filter((p) => p.kind === "repo").length} repo
                </div>
              </div>
            </div>

            <div className="grid cols-3" style={{ marginTop: 16 }}>
              <div className="card flush">
                <div className="card-head">
                  <h3 className="card-title">Top Issues</h3>
                  <Link href="/findings" className="card-link">
                    View all <IconArrowRight size={13} />
                  </Link>
                </div>
                {topIssues.length === 0 ? (
                  <div className="empty" style={{ border: "none", padding: "38px 20px" }}>
                    No findings recorded.
                  </div>
                ) : (
                  <div className="list">
                    {topIssues.map((f) => (
                      <Link href="/findings" className="list-row" key={f.id}>
                        <span className="list-text" title={f.title}>
                          {f.title}
                        </span>
                        <span className={`score-pill ${f.severity === "critical" ? "crit" : f.severity === "high" ? "high" : ""}`}>
                          {f.severity}
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              <div className="card flush">
                <div className="card-head">
                  <h3 className="card-title">Top Affected Targets</h3>
                  <Link href="/targets" className="card-link">
                    View all <IconArrowRight size={13} />
                  </Link>
                </div>
                {stats.assets.length === 0 ? (
                  <div className="empty" style={{ border: "none", padding: "38px 20px" }}>
                    No affected targets.
                  </div>
                ) : (
                  <div className="list">
                    {stats.assets.map((a) => (
                      <div className="list-row" key={a.project.id}>
                        <span className="list-text mono" title={a.project.name}>
                          {a.project.name}
                        </span>
                        <SevCounts counts={a.counts} />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="card flush">
                <div className="card-head">
                  <h3 className="card-title">Severity Breakdown</h3>
                </div>
                <div style={{ padding: "20px 18px 22px" }}>
                  <Donut slices={slices} centerLabel="Total" />
                  <div className="legend">
                    {SEV_ORDER.filter((s) => stats.counts[s] > 0).map((s) => (
                      <span className="legend-item" key={s}>
                        <span className={`sev-dot d-${s}`} />
                        <span style={{ textTransform: "capitalize" }}>{s}</span>
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid cols-3" style={{ marginTop: 16 }}>
              <div className="card">
                <div className="metric-label">Cumulative Findings</div>
                <div className="metric-value" style={{ marginBottom: 10 }}>
                  {findings.length}
                </div>
                <Sparkline values={stats.trend.length > 1 ? stats.trend : [0, findings.length]} color="#ef4444" />
              </div>
              <div className="card">
                <div className="metric-label">Evidence Coverage</div>
                <div className="metric-value" style={{ marginBottom: 10 }}>
                  {findings.length === 0
                    ? "—"
                    : `${Math.round((stats.reproduced / findings.length) * 100)}%`}
                </div>
                <div className="dim" style={{ fontSize: 12, lineHeight: 1.6 }}>
                  Share of findings backed by a technical test rather than AI review
                  alone. AI review is never sufficient to confirm a finding.
                </div>
              </div>
              <div className="card">
                <div className="metric-label">Scan Activity</div>
                <div className="metric-value" style={{ marginBottom: 10 }}>
                  {scans.filter((s) => s.status === "completed").length}
                  <span className="metric-unit">completed</span>
                </div>
                <Sparkline
                  values={scans.length > 1 ? scans.map((s) => s.findings_count).reverse() : [0, scans[0]?.findings_count ?? 0]}
                  color="#3b82f6"
                />
              </div>
            </div>

            <div className="section-head">
              <h2 className="section-title">Latest Findings</h2>
              <Link href="/findings" className="card-link">
                View all <IconArrowRight size={13} />
              </Link>
            </div>

            {findings.length === 0 ? (
              <div className="empty">
                <strong>No findings yet</strong>
                Add a target, then run a scan to populate this view.
              </div>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Finding</th>
                      <th>Severity</th>
                      <th>Status</th>
                      <th>Class</th>
                      <th>Scanner</th>
                    </tr>
                  </thead>
                  <tbody>
                    {findings.slice(0, 8).map((f) => (
                      <tr key={f.id}>
                        <td>
                          <Link href="/findings" className="cell-title">
                            {f.title}
                          </Link>
                          {f.location && (
                            <div className="cell-meta">
                              <span className="mono">{f.location}</span>
                            </div>
                          )}
                        </td>
                        <td>
                          <SeverityBadge severity={f.severity} />
                        </td>
                        <td>
                          <StatusBadge status={f.status} />
                        </td>
                        <td className="muted">{f.vuln_class}</td>
                        <td>
                          {f.scanner ? <span className="tag">{f.scanner}</span> : <span className="dim">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

function LoadingState() {
  return (
    <>
      <div className="skeleton" style={{ height: 92, borderRadius: 14 }} />
      <div className="grid cols-3" style={{ marginTop: 16 }}>
        {[0, 1, 2].map((i) => (
          <div key={i} className="skeleton" style={{ height: 250, borderRadius: 14 }} />
        ))}
      </div>
    </>
  );
}
