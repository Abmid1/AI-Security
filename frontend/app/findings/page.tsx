"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Finding, Project } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";
import { ConfidenceBadge, EvidenceBadge, SeverityBadge, StatusBadge } from "@/components/Badges";

const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

function FindingsInner() {
  const params = useSearchParams();
  const scanId = params.get("scan") || undefined;

  const [findings, setFindings] = useState<Finding[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fixMsg, setFixMsg] = useState<Record<string, string>>({});
  const [busyFix, setBusyFix] = useState<string | null>(null);

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
            {scanId ? "Filtered to one scan" : "All findings"} · severity, confidence, evidence &amp; status
          </div>
        </div>
      </div>
      <div className="content">
        <MockBanner />

        <div className="notice info">
          <strong>Reading the evidence basis:</strong> a{" "}
          <span className="badge ev-reproduced">reproduced</span> finding was observed by a
          technical test; an <span className="badge ev-ai">AI-reviewed</span> finding is a
          hypothesis that has <em>not</em> been technically reproduced. In this milestone all
          values are sample data.
        </div>

        {error && <div className="notice error">{error}</div>}
        {loading ? (
          <div className="muted">Loading…</div>
        ) : findings.length === 0 ? (
          <div className="empty">No findings. Run a mock scan from the Scans page.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Finding</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Evidence</th>
                <th>Fix</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id}>
                  <td style={{ maxWidth: 420 }}>
                    <div style={{ fontWeight: 600 }}>{f.title}</div>
                    <div className="muted" style={{ marginTop: 2 }}>
                      {projName(f.project_id)} · <span className="mono">{f.location}</span>
                      {f.scanner && <span className="tag" style={{ marginLeft: 8 }}>{f.scanner}</span>}
                    </div>
                    {f.description && (
                      <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>{f.description}</div>
                    )}
                    {f.evidence && (
                      <details className="evidence">
                        <summary>Evidence</summary>
                        <pre>{JSON.stringify(f.evidence, null, 2)}</pre>
                      </details>
                    )}
                  </td>
                  <td><SeverityBadge severity={f.severity} /></td>
                  <td>
                    <StatusBadge status={f.status} />
                    <div style={{ marginTop: 6 }}><ConfidenceBadge confidence={f.confidence} /></div>
                  </td>
                  <td><EvidenceBadge basis={f.evidence_basis} /></td>
                  <td>
                    <button className="btn small secondary" disabled={busyFix === f.id}
                      onClick={() => onGenerateFix(f.id)}>
                      {busyFix === f.id ? "…" : "Generate Fix"}
                    </button>
                    {fixMsg[f.id] && (
                      <div className="notice info" style={{ marginTop: 8, maxWidth: 260 }}>
                        {fixMsg[f.id]}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
