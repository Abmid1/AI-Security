"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Project, ScanJob } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";
import { IconArrowRight, IconPlay } from "@/components/Icons";

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
          <h1>Scans</h1>
          <div className="sub">Real scans execute in an isolated worker process</div>
        </div>
      </div>

      <div className="content">
        <MockBanner />

        <div className="toolbar">
          <div className="field">
            <label>Target</label>
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              {projects.length === 0 && <option value="">No targets — add one first</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.kind}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "0 0 180px", minWidth: 180 }}>
            <label>Mode</label>
            <select value={mode} onChange={(e) => setMode(e.target.value as "mock" | "real")}>
              <option value="real">Real scan</option>
              <option value="mock">Mock (sample)</option>
            </select>
          </div>
          <button className="btn" onClick={startScan} disabled={!selected || starting}>
            <IconPlay size={13} />
            {starting ? "Starting…" : mode === "real" ? "Run real scan" : "Run mock scan"}
          </button>
          <div className="toolbar-note">
            {mode === "real"
              ? "Runs Bandit (Python source), detect-secrets, and pip-audit (dependencies) for repositories, plus safe passive header and cookie checks for authorized web targets. Dynamic checks require confirmed authorization and never leave the authorized origin."
              : "Returns a fixed set of sample findings for demonstration. Nothing is scanned and no requests are made."}
          </div>
        </div>

        {error && (
          <div className="notice error">
            <div>
              <strong>Scan request failed.</strong> {error}
            </div>
          </div>
        )}

        {loading ? (
          <div className="skeleton" style={{ height: 260, borderRadius: 14 }} />
        ) : scans.length === 0 ? (
          <div className="empty">
            <strong>No scans yet</strong>
            Choose a target above and run your first scan.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Target</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Findings</th>
                  <th>Finished</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => {
                  const proj = projects.find((p) => p.id === s.project_id);
                  const active = s.status === "queued" || s.status === "running";
                  return (
                    <Fragment key={s.id}>
                      <tr>
                        <td className="cell-title">{proj?.name ?? s.project_id}</td>
                        <td>
                          <span className={`tag mode-${s.mode}`}>{s.mode}</span>
                        </td>
                        <td>
                          <span className="row" style={{ gap: 7 }}>
                            {active && <span className="pulse" />}
                            <span className={s.status === "failed" ? "badge sev-critical" : "tag"}>
                              {s.status}
                            </span>
                          </span>
                        </td>
                        <td className="num">{s.findings_count}</td>
                        <td className="muted">{fmt(s.finished_at)}</td>
                        <td>
                          <div className="row" style={{ gap: 7, justifyContent: "flex-end" }}>
                            <button
                              className="btn small ghost"
                              onClick={() => router.push(`/findings?scan=${s.id}`)}
                            >
                              Findings <IconArrowRight size={12} />
                            </button>
                            {(s.coverage || s.error) && (
                              <button
                                className="btn small ghost"
                                onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                              >
                                {expanded === s.id ? "Hide" : "Coverage"}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {expanded === s.id && (
                        <tr>
                          <td colSpan={6} style={{ background: "var(--bg)", padding: "18px 18px 22px" }}>
                            {s.error && (
                              <div className="notice error" style={{ marginBottom: 14 }}>
                                <div>
                                  <strong>Scan error.</strong> {s.error}
                                </div>
                              </div>
                            )}
                            {s.coverage && <CoverageView scan={s} />}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function CoverageView({ scan }: { scan: ScanJob }) {
  const c = scan.coverage!;
  return (
    <div>
      {scan.coverage_note && (
        <div className="dim" style={{ fontSize: 12, marginBottom: 12, lineHeight: 1.6 }}>
          {scan.coverage_note}
        </div>
      )}

      <div className="table-wrap" style={{ marginBottom: 12 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Scanner</th>
              <th>Category</th>
              <th>Status</th>
              <th>Findings</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {c.scanners.map((sc) => (
              <tr key={sc.name}>
                <td className="cell-title mono">{sc.name}</td>
                <td className="muted">{sc.category}</td>
                <td>
                  <span
                    className={`badge ${
                      sc.status === "completed"
                        ? "status-confirmed"
                        : sc.status === "error"
                          ? "sev-critical"
                          : "status-untested"
                    }`}
                  >
                    {sc.status}
                  </span>
                </td>
                <td className="num">{sc.findings ?? 0}</td>
                <td className="muted" style={{ fontSize: 12, maxWidth: 420 }}>
                  {sc.reason || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="dim" style={{ fontSize: 12 }}>
        Duplicates merged: {c.duplicates_removed} · Unsafe paths rejected:{" "}
        {c.findings_rejected_unsafe_path}
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
