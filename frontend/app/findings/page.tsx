"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Finding, Project, Severity } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";
import {
  ConfidenceBadge,
  EvidenceBadge,
  SeverityBadge,
  StatusBadge,
} from "@/components/Badges";
import { IconWrench } from "@/components/Icons";

const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

function FindingsInner() {
  const params = useSearchParams();
  const scanId = params.get("scan") || undefined;

  const [findings, setFindings] = useState<Finding[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fixMsg, setFixMsg] = useState<Record<string, string>>({});
  const [busyFix, setBusyFix] = useState<string | null>(null);
  const [sevFilter, setSevFilter] = useState<"all" | Severity>("all");

  useEffect(() => {
    Promise.all([api.listFindings({ scanId }), api.listProjects()])
      .then(([f, p]) => {
        f.sort((a, b) => (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9));
        setFindings(f);
        setProjects(p);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [scanId]);

  const counts = useMemo(
    () =>
      Object.fromEntries(
        SEV_ORDER.map((s) => [s, findings.filter((f) => f.severity === s).length]),
      ) as Record<Severity, number>,
    [findings],
  );

  const visible = sevFilter === "all" ? findings : findings.filter((f) => f.severity === sevFilter);

  async function onGenerateFix(id: string) {
    setBusyFix(id);
    try {
      const res = await api.generateFix(id);
      setFixMsg((m) => ({ ...m, [id]: res.message }));
    } catch (e) {
      setFixMsg((m) => ({ ...m, [id]: e instanceof ApiError ? e.message : String(e) }));
    } finally {
      setBusyFix(null);
    }
  }

  const projName = (pid: string) => projects.find((p) => p.id === pid)?.name ?? pid;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Findings</h1>
          <div className="sub">
            {scanId ? "Filtered to a single scan" : "Every finding across all targets"}
          </div>
        </div>
        <div className="topbar-actions">
          <select
            value={sevFilter}
            onChange={(e) => setSevFilter(e.target.value as "all" | Severity)}
            style={{ width: 170 }}
            aria-label="Filter by severity"
          >
            <option value="all">All severities</option>
            {SEV_ORDER.map((s) => (
              <option key={s} value={s}>
                {s[0].toUpperCase() + s.slice(1)} ({counts[s]})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="content">
        <MockBanner />

        <div className="notice banner">
          <div>
            <strong>Reading the evidence column.</strong> An{" "}
            <span className="badge ev-reproduced">Evidence</span> finding was observed by a
            technical test — a scanner matched it, or it was reproduced against a live target. An{" "}
            <span className="badge ev-ai">AI-reviewed</span> finding is a hypothesis that has{" "}
            <em>not</em> been technically reproduced, and is never sufficient on its own to
            confirm a vulnerability.
          </div>
        </div>

        {error && (
          <div className="notice error">
            <div>
              <strong>Could not load findings.</strong> {error}
            </div>
          </div>
        )}

        {loading ? (
          <div className="skeleton" style={{ height: 320, borderRadius: 14 }} />
        ) : visible.length === 0 ? (
          <div className="empty">
            <strong>No findings to show</strong>
            {findings.length === 0
              ? "Run a scan from the Scans page to populate this view."
              : "No findings match the selected severity."}
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: "46%" }}>Finding</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Evidence</th>
                  <th>Remediation</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((f) => (
                  <tr key={f.id}>
                    <td>
                      <div className="cell-title">{f.title}</div>
                      <div className="cell-meta">
                        <span>{projName(f.project_id)}</span>
                        {f.location && (
                          <>
                            <span className="dim">·</span>
                            <span className="mono">{f.location}</span>
                          </>
                        )}
                        {f.scanner && <span className="tag">{f.scanner}</span>}
                        {f.is_mock && <span className="tag">sample</span>}
                      </div>
                      {f.description && <div className="cell-desc">{f.description}</div>}
                      {f.evidence && (
                        <details className="evidence">
                          <summary>Evidence detail</summary>
                          <pre>{JSON.stringify(f.evidence, null, 2)}</pre>
                        </details>
                      )}
                    </td>
                    <td>
                      <SeverityBadge severity={f.severity} />
                      <div style={{ marginTop: 7 }} className="dim">
                        {f.vuln_class}
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={f.status} />
                      <div style={{ marginTop: 7 }}>
                        <ConfidenceBadge confidence={f.confidence} />
                      </div>
                    </td>
                    <td>
                      <EvidenceBadge basis={f.evidence_basis} />
                      <div className="dim mono" style={{ marginTop: 7 }}>
                        {f.evidence_basis}
                      </div>
                    </td>
                    <td>
                      <button
                        className="btn small secondary"
                        disabled={busyFix === f.id}
                        onClick={() => onGenerateFix(f.id)}
                      >
                        <IconWrench size={13} />
                        {busyFix === f.id ? "Working…" : "Generate Fix"}
                      </button>
                      {fixMsg[f.id] && (
                        <div className="notice" style={{ marginTop: 9, maxWidth: 240 }}>
                          {fixMsg[f.id]}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

export default function FindingsPage() {
  return (
    <Suspense fallback={<div className="content muted">Loading…</div>}>
      <FindingsInner />
    </Suspense>
  );
}
