import { IconInfo } from "@/components/Icons";

// Honest context note. Real scanning exists (Bandit, detect-secrets,
// pip-audit, safe passive dynamic checks); mock sample scans remain
// available and are always labelled.
export function MockBanner() {
  return (
    <div className="notice banner" role="note">
      <IconInfo size={15} />
      <div>
        <strong>Two scan modes.</strong> Real scans run actual security tools in an
        isolated worker and report honest coverage. Mock scans show labelled sample
        data. Automated code modification is not enabled — fixes stay under your control.
      </div>
    </div>
  );
}
