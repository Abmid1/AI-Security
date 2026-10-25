// A persistent, honest reminder that nothing here is a real scan yet.
export function MockBanner() {
  return (
    <div className="mock-banner" role="note">
      <strong>Demonstration data.</strong> No real security scanning is performed
      in this milestone. All scans and findings shown are mock samples.
    </div>
  );
}
