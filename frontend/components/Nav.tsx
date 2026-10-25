"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard", icon: "▦" },
  { href: "/targets", label: "Targets", icon: "◎" },
  { href: "/scans", label: "Scan History", icon: "↻" },
  { href: "/findings", label: "Findings", icon: "⚑" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sidebar">
      <div className="brand">
        <div className="brand-mark">AI</div>
        <div>
          <div className="brand-name">PentestAI</div>
          <div className="brand-sub">Milestone 2</div>
        </div>
      </div>
      <ul className="nav-list">
        {LINKS.map((l) => {
          const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
          return (
            <li key={l.href}>
              <Link href={l.href} className={`nav-item ${active ? "active" : ""}`}>
                <span className="nav-icon">{l.icon}</span>
                {l.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="sidebar-foot">
        <span className="dot" /> Mock mode
      </div>
    </nav>
  );
}
