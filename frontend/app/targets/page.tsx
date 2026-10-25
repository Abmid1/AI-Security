"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Project, ProjectKind } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";

export default function TargetsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [kind, setKind] = useState<ProjectKind>("web");
  const [name, setName] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [authNote, setAuthNote] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = () => api.listProjects().then(setProjects).catch(() => {});
  useEffect(() => { load(); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setOk(null);
    if (!authorized) {
      setError("You must confirm you are authorized to test this target.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await api.createProject({
        name,
        kind,
        target_url: kind === "web" ? targetUrl : null,
        repo_url: kind === "repo" ? repoUrl : null,
        authorization_confirmed: authorized,
        authorization_note: authNote || null,
      });
      setOk(`Added "${created.name}".`);
      setName(""); setTargetUrl(""); setRepoUrl(""); setAuthNote(""); setAuthorized(false);
      load();
    } catch (e) {
      const msg = e instanceof ApiError
        ? (Array.isArray(e.detail) ? e.detail.map((d: any) => d.msg).join("; ") : String(e.message))
        : String(e);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Targets</h1>
          <div className="sub">Add an authorized web target or connect a repository</div>
        </div>
      </div>
      <div className="content">
        <MockBanner />

        <div className="grid cols-2">
          <div className="card">
            <h3>New target</h3>
            <form className="form" onSubmit={submit} style={{ marginTop: 14 }}>
              <div className="field">
                <label>Type</label>
                <select value={kind} onChange={(e) => setKind(e.target.value as ProjectKind)}>
                  <option value="web">Web application</option>
                  <option value="repo">Code repository</option>
                </select>
              </div>

              <div className="field">
                <label>Name</label>
                <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Staging storefront" required />
              </div>

              {kind === "web" ? (
                <div className="field">
                  <label>Target URL</label>
                  <input type="url" value={targetUrl} onChange={(e) => setTargetUrl(e.target.value)}
                    placeholder="https://staging.example.com" required />
                  <span className="hint">Only targets you own or are explicitly permitted to test.</span>
                </div>
              ) : (
                <div className="field">
                  <label>Repository URL</label>
                  <input type="url" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/your-org/your-repo.git" required />
                  <span className="hint">A repository you control.</span>
                </div>
              )}

              <div className="field">
                <label>Authorization note (optional)</label>
                <input type="text" value={authNote} onChange={(e) => setAuthNote(e.target.value)}
                  placeholder="e.g. I own this system / written permission on file" />
              </div>

              <div className="checkbox">
                <input id="auth" type="checkbox" checked={authorized}
                  onChange={(e) => setAuthorized(e.target.checked)} />
                <label htmlFor="auth" style={{ fontWeight: 500 }}>
                  I confirm I am authorized to test this target. Scanning systems
                  without permission may be illegal.
                </label>
              </div>

              {error && <div className="notice error">{error}</div>}
              {ok && <div className="notice ok">{ok}</div>}

              <div>
                <button className="btn" type="submit" disabled={submitting}>
                  {submitting ? "Adding…" : "Add target"}
                </button>
              </div>
            </form>
          </div>

          <div className="card">
            <h3>Existing targets ({projects.length})</h3>
            {projects.length === 0 ? (
              <div className="muted" style={{ marginTop: 10 }}>No targets yet.</div>
            ) : (
              <table className="table" style={{ marginTop: 10 }}>
                <thead>
                  <tr><th>Name</th><th>Type</th><th>Location</th></tr>
                </thead>
                <tbody>
                  {projects.map((p) => (
                    <tr key={p.id}>
                      <td>{p.name}</td>
                      <td><span className="tag">{p.kind}</span></td>
                      <td className="mono muted">{p.target_url || p.repo_url}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div style={{ marginTop: 14 }}>
              <button className="btn secondary" onClick={() => router.push("/scans")}>
                Go to scans →
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
