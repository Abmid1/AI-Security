// Honest context note. Real scanning now exists (Bandit, detect-secrets,
// pip-audit, safe passive dynamic checks); mock sample scans remain available
// and are always labelled.
export function MockBanner() {
  return (
    <div className="mock-banner" role="note">
      <strong>Two scan modes.</strong> <em>Real</em> scans run actual security
      tools in an isolated worker. <em>Mock</em> scans show labelled sample data
      for demonstration. Findings from each are clearly marked. No automated code
      modification is performed.
    </div>
  );
}
