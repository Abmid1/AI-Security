"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Project, ProjectKind } from "@/lib/types";
import { MockBanner } from "@/components/MockBanner";
import { IconArrowRight, IconPlus } from "@/components/Icons";

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
      setOk(`Target "${created.name}" added.`);
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
          <div className="sub">Authorized web applications and connected repositories</div>
        </div>
        <div className="topbar-actions">
          <button className="btn secondary" onClick={() => router.push("/scans")}>
            Go to scans <IconArrowRight size={13} />
          </button>
        </div>
      </div>

      <div className="content">
        <MockBanner />

        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 420px) minmax(0, 1fr)" }}>
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: 16 }}>
              Add a target
            </h3>

            <form className="form" onSubmit={submit}>
              <div className="field">
                <label htmlFor="kind">Type</label>
                <select id="kind" value={kind} onChange={(e) => setKind(e.target.value as ProjectKind)}>
                  <option value="web">Web application</option>
                  <option value="repo">Code repository</option>
                </select>
              </div>

              <div className="field">
                <label htmlFor="name">Name</label>
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Staging storefront"
                  required
                />
              </div>

              {kind === "web" ? (
                <div className="field">
                  <label htmlFor="url">Target URL</label>
                  <input
                    id="url"
                    type="url"
                    value={targetUrl}
                    onChange={(e) => setTargetUrl(e.target.value)}
                    placeholder="https://staging.example.com"
                    required
                  />
                  <span className="hint">
                    Scanning stays on this exact origin. Only add systems you own or are
                    explicitly permitted to test.
                  </span>
                </div>
              ) : (
                <div className="field">
                  <label htmlFor="repo">Repository</label>
                  <input
                    id="repo"
                    type="text"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/your-org/your-repo.git"
                    required
                  />
                  <span className="hint">
                    A git URL, or a local folder path such as <span className="mono">D:\code\my-app</span>.
                  </span>
                </div>
              )}

              <div className="field">
                <label htmlFor="note">
                  Authorization note <span className="dim">(optional)</span>
                </label>
                <input
                  id="note"
                  type="text"
                  value={authNote}
                  onChange={(e) => setAuthNote(e.target.value)}
                  placeholder="I own this system / written permission on file"
                />
              </div>

              <div className="checkbox">
                <input
                  id="auth"
                  type="checkbox"
                  checked={authorized}
                  onChange={(e) => setAuthorized(e.target.checked)}
                />
                <label htmlFor="auth">
                  I confirm I am authorized to test this target. Scanning systems without
                  permission may be illegal.
                </label>
              </div>

              {error && (
                <div className="notice error">
                  <div>{error}</div>
                </div>
              )}
              {ok && (
                <div className="notice ok">
                  <div>{ok}</div>
                </div>
              )}

              <div>
                <button className="btn" type="submit" disabled={submitting}>
                  <IconPlus size={15} />
                  {submitting ? "Adding…" : "Add target"}
                </button>
              </div>
            </form>
          </div>

          <div className="card flush">
            <div className="card-head">
              <h3 className="card-title">Connected targets</h3>
              <span className="tag">{projects.length}</span>
            </div>
            {projects.length === 0 ? (
              <div className="empty" style={{ border: "none" }}>
                <strong>Nothing connected yet</strong>
                Add your first target using the form.
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Location</th>
                    <th>Authorized</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((p) => (
                    <tr key={p.id}>
                      <td className="cell-title">{p.name}</td>
                      <td>
                        <span className="tag">{p.kind}</span>
                      </td>
                      <td className="mono muted" style={{ maxWidth: 320, wordBreak: "break-all" }}>
                        {p.target_url || p.repo_url}
                      </td>
                      <td>
                        {p.authorization_confirmed ? (
                          <span className="badge status-confirmed">confirmed</span>
                        ) : (
                          <span className="badge sev-high">missing</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
