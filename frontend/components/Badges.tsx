import type { Confidence, EvidenceBasis, FindingStatus, Severity } from "@/lib/types";

export const SEV_COLORS: Record<Severity, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
  info: "#71717a",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`badge sev-${severity}`}>
      <span className={`sev-dot d-${severity}`} />
      {severity}
    </span>
  );
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return <span className="tag">{confidence} confidence</span>;
}

export function StatusBadge({ status }: { status: FindingStatus }) {
  return <span className={`badge status-${status}`}>{status.replace(/_/g, " ")}</span>;
}

// The honesty signal: was this reproduced by a technical test, or only
// reviewed by AI? AI-reviewed alone is never sufficient to confirm.
export function EvidenceBadge({ basis }: { basis: EvidenceBasis }) {
  const reproduced = basis !== "AI_REVIEWED";
  return (
    <span className={`badge ${reproduced ? "ev-reproduced" : "ev-ai"}`} title={basis}>
      {reproduced ? "Evidence" : "AI-reviewed"}
    </span>
  );
}

export function SevCounts({ counts }: { counts: Partial<Record<Severity, number>> }) {
  const order: Severity[] = ["critical", "high", "medium", "low", "info"];
  const shown = order.filter((s) => (counts[s] ?? 0) > 0);
  if (shown.length === 0) return <span className="dim" style={{ fontSize: 12 }}>—</span>;
  return (
    <span className="sev-counts">
      {shown.map((s) => (
        <span className="sev-count" key={s} title={s}>
          <span className={`sev-dot d-${s}`} />
          {counts[s]}
        </span>
      ))}
    </span>
  );
}
