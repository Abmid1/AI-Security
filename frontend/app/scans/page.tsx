"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Project, ScanJob } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";

export default function ScansPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [selected, setSelected] = useState("");
  const [mode, setMode] = useState<"mock" | "real">("real");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = async () => {
    try {
      const [p, s] = await Promise.all([api.listProjects(), api.listScans()]);
      setProjects(p);
      setScans(s);
      setSelected((cur) => cur || (p.length ? p[0].id : ""));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  // Poll while any scan is still queued/running (real scans run async).
  const anyActive = scans.some((s) => s.status === "queued" || s.status === "running");
  useEffect(() => {
    if (anyActive && !pollRef.current) {
      pollRef.current = setInterval(load, 2500);
    } else if (!anyActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
    // eslint-disable-next-line
  }, [anyActive]);

  async function startScan() {
    if (!selected) return;
    setStarting(true);
    setError(null);
    try {
      await api.startScan(selected, mode);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  }

  const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : "—");

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Scan History</h1>
          <div className="sub">Real scans run in an isolated worker; mock scans return samples</div>
        </div>
      </div>
      <div className="content">
        <MockBanner />

        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row-between" style={{ flexWrap: "wrap", gap: 14 }}>
            <div className="field" style={{ flex: 1, minWidth: 260 }}>
              <label>Target</label>
              <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                {projects.length === 0 && <option value="">No targets — add one first</option>}
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.kind})</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ width: 160 }}>
              <label>Mode</label>
              <select value={mode} onChange={(e) => setMode(e.target.value as "mock" | "real")}>
                <option value="real">Real scan</option>
                <option value="mock">Mock (sample)</option>
              </select>
            </div>
            <div style={{ alignSelf: "flex-end" }}>
              <button className="btn" onClick={startScan} disabled={!selected || starting}>
                {starting ? "Starting…" : mode === "real" ? "▶ Run real scan" : "▶ Run mock scan"}
              </button>
            </div>
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>
            {mode === "real"
              ? "Runs Bandit (code), detect-secrets, pip-audit (dependencies) for repositories, and safe passive header checks for authorized web targets. Dynamic checks require confirmed authorization and stay on the authorized origin."
              : "Returns fixed sample findings for demonstration. Nothing is scanned."}
          </div>
        </div>

        {error && <div className="notice error">{error}</div>}
        {loading ? (
          <div className="muted">Loading…</div>
        ) : scans.length === 0 ? (
          <div className="empty">No scans yet.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Target</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Findings</th>
                <th>Finished</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s) => {
                const proj = projects.find((p) => p.id === s.project_id);
                const active = s.status === "queued" || s.status === "running";
                return (
                  <Fragment key={s.id}>
                    <tr>
                      <td>{proj?.name ?? s.project_id}</td>
                      <td><span className="tag">{s.mode}</span></td>
                      <td>
                        <span className={`tag`}>{s.status}</span>
                        {active && <span className="muted" style={{ marginLeft: 6 }}>…</span>}
                      </td>
                      <td>{s.findings_count}</td>
                      <td className="muted">{fmt(s.finished_at)}</td>
                      <td style={{ display: "flex", gap: 6 }}>
                        <button className="btn small secondary"
                          onClick={() => router.push(`/findings?scan=${s.id}`)}>
                          Findings
                        </button>
                        {(s.coverage || s.error) && (
                          <button className="btn small secondary"
                            onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
                            {expanded === s.id ? "Hide" : "Coverage"}
                          </button>
                        )}
                      </td>
                    </tr>
                    {expanded === s.id && (
                      <tr>
                        <td colSpan={6} style={{ background: "var(--panel-2)" }}>
                          {s.error && <div className="notice error">{s.error}</div>}
                          {s.coverage && <CoverageView scan={s} />}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function CoverageView({ scan }: { scan: ScanJob }) {
  const c = scan.coverage!;
  return (
    <div style={{ padding: "6px 2px" }}>
      <div className="muted" style={{ marginBottom: 8 }}>{scan.coverage_note}</div>
      <table className="table" style={{ marginBottom: 10 }}>
        <thead>
          <tr><th>Scanner</th><th>Category</th><th>Status</th><th>Findings</th><th>Note</th></tr>
        </thead>
        <tbody>
          {c.scanners.map((sc) => (
            <tr key={sc.name}>
              <td>{sc.name}</td>
              <td className="muted">{sc.category}</td>
              <td>
                <span className={`badge ${sc.status === "completed" ? "status-confirmed"
                  : sc.status === "error" ? "sev-high" : "status-untested"}`}>
                  {sc.status}
                </span>
              </td>
              <td>{sc.findings ?? 0}</td>
              <td className="muted" style={{ fontSize: 12 }}>{sc.reason || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="muted" style={{ fontSize: 12 }}>
        Deduplicated: {c.duplicates_removed} · Unsafe paths rejected: {c.findings_rejected_unsafe_path}
        {c.workspace_note ? ` · ${c.workspace_note}` : ""}
      </div>
      {c.skipped_areas.length > 0 && (
        <details className="evidence">
          <summary>Skipped areas ({c.skipped_areas.length})</summary>
          <pre>{c.skipped_areas.join("\n")}</pre>
        </details>
      )}
      {c.errors.length > 0 && (
        <details className="evidence">
          <summary>Errors ({c.errors.length})</summary>
          <pre>{c.errors.join("\n")}</pre>
        </details>
      )}
    </div>
  );
}
