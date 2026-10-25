import type { Confidence, EvidenceBasis, FindingStatus, Severity } from "@/lib/types";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`badge sev-${severity}`}>{severity}</span>;
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return <span className={`badge conf-${confidence}`}>confidence: {confidence}</span>;
}

export function StatusBadge({ status }: { status: FindingStatus }) {
  const label = status.replace(/_/g, " ");
  return <span className={`badge status-${status}`}>{label}</span>;
}

// The important honesty signal: was this reproduced by a technical test, or
// only reviewed by AI?
export function EvidenceBadge({ basis }: { basis: EvidenceBasis }) {
  const reproduced = basis !== "AI_REVIEWED";
  return (
    <span className={`badge ${reproduced ? "ev-reproduced" : "ev-ai"}`}>
      {reproduced ? "reproduced" : "AI-reviewed"} · {basis}
    </span>
  );
}
