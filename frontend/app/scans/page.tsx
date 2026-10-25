"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Project, ScanJob } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";

export default function ScansPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [p, s] = await Promise.all([api.listProjects(), api.listScans()]);
      setProjects(p);
      setScans(s);
      if (!selected && p.length) setSelected(p[0].id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function startScan() {
    if (!selected) return;
    setStarting(true);
    setError(null);
    try {
      await api.startScan(selected);
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
          <div className="sub">Mock scans run instantly and return sample findings</div>
        </div>
      </div>
      <div className="content">
        <MockBanner />

        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row-between">
            <div className="field" style={{ flex: 1, maxWidth: 420 }}>
              <label>Run a mock scan on</label>
              <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                {projects.length === 0 && <option value="">No targets — add one first</option>}
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <button className="btn" onClick={startScan} disabled={!selected || starting}>
              {starting ? "Running…" : "▶ Run mock scan"}
            </button>
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
                <th>Status</th>
                <th>Findings</th>
                <th>Started</th>
                <th>Finished</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s) => {
                const proj = projects.find((p) => p.id === s.project_id);
                return (
                  <tr key={s.id}>
                    <td>
                      {proj?.name ?? s.project_id}
                      {s.is_mock && <span className="tag" style={{ marginLeft: 8 }}>mock</span>}
                    </td>
                    <td><span className="tag">{s.status}</span></td>
                    <td>{s.findings_count}</td>
                    <td className="muted">{fmt(s.started_at)}</td>
                    <td className="muted">{fmt(s.finished_at)}</td>
                    <td>
                      <button className="btn small secondary"
                        onClick={() => router.push(`/findings?scan=${s.id}`)}>
                        View findings
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
