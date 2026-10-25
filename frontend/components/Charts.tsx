export type Slice = { label: string; value: number; color: string };

export function Donut({
  slices,
  size = 168,
  thickness = 16,
  centerLabel = "Total",
}: {
  slices: Slice[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
}) {
  const total = slices.reduce((s, x) => s + x.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const gap = total > 0 && slices.filter((s) => s.value > 0).length > 1 ? 1.6 : 0;

  let offset = 0;

  return (
    <div style={{ display: "grid", placeItems: "center", position: "relative" }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }} aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.07)"
          strokeWidth={thickness}
        />
        {total > 0 &&
          slices.map((s) => {
            if (s.value <= 0) return null;
            const len = (s.value / total) * c;
            const dash = Math.max(len - gap, 0.6);
            const el = (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={thickness}
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={-offset}
                strokeLinecap="round"
              />
            );
            offset += len;
            return el;
          })}
      </svg>
      <div
        style={{
          position: "absolute",
          textAlign: "center",
          pointerEvents: "none",
        }}
      >
        <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 500 }}>{centerLabel}</div>
        <div
          style={{
            fontSize: 27,
            fontWeight: 600,
            letterSpacing: "-0.035em",
            lineHeight: 1.15,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {total}
        </div>
      </div>
    </div>
  );
}

export function Sparkline({
  values,
  color = "#22c55e",
  height = 56,
  width = 260,
}: {
  values: number[];
  color?: string;
  height?: number;
  width?: number;
}) {
  if (values.length === 0) return null;

  const pad = 4;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const stepX = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;

  const pt = (v: number, i: number) => {
    const x = pad + i * stepX;
    const y = pad + (1 - (v - min) / span) * (height - pad * 2);
    return [x, y] as const;
  };

  const line = values.map((v, i) => pt(v, i).join(",")).join(" ");
  const id = `sg-${color.replace(/[^a-z0-9]/gi, "")}`;
  const last = pt(values[values.length - 1], values.length - 1);

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pad},${height - pad} ${line} ${width - pad},${height - pad}`} fill={`url(#${id})`} />
      <polyline points={line} fill="none" stroke={color} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r="2.75" fill={color} />
    </svg>
  );
}

export function MiniBars({
  slices,
  total,
}: {
  slices: Slice[];
  total: number;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
      {slices.map((s) => (
        <div
          key={s.label}
          style={{
            display: "grid",
            gridTemplateColumns: "72px 1fr 28px",
            alignItems: "center",
            gap: 12,
            fontSize: 12,
          }}
        >
          <span style={{ color: "var(--text-2)", textTransform: "capitalize" }}>{s.label}</span>
          <span
            style={{
              background: "rgba(255,255,255,0.06)",
              borderRadius: 99,
              height: 6,
              overflow: "hidden",
            }}
          >
            <span
              style={{
                display: "block",
                height: "100%",
                borderRadius: 99,
                width: `${total > 0 ? (s.value / total) * 100 : 0}%`,
                background: s.color,
                transition: "width .4s ease",
              }}
            />
          </span>
          <span
            style={{
              textAlign: "right",
              color: "var(--text-2)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {s.value}
          </span>
        </div>
      ))}
    </div>
  );
}
