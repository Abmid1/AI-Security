"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconAlert,
  IconDashboard,
  IconLayers,
  IconScan,
  IconTarget,
} from "@/components/Icons";

const SECTIONS = [
  {
    label: "Overview",
    links: [{ href: "/", label: "Dashboard", Icon: IconDashboard }],
  },
  {
    label: "Testing",
    links: [
      { href: "/targets", label: "Targets", Icon: IconTarget },
      { href: "/scans", label: "Scans", Icon: IconScan },
      { href: "/findings", label: "Findings", Icon: IconAlert },
    ],
  },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="sidebar">
      <div className="workspace">
        <div className="workspace-mark">AP</div>
        <div className="workspace-meta">
          <div className="workspace-name">AI Pentest</div>
          <div className="workspace-plan">Milestone 2</div>
        </div>
      </div>

      {SECTIONS.map((section) => (
        <div key={section.label}>
          <div className="nav-label">{section.label}</div>
          <div className="nav-group">
            {section.links.map(({ href, label, Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link key={href} href={href} className={`nav-item ${active ? "active" : ""}`}>
                  <Icon size={16} />
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}

      <div className="nav-label">Resources</div>
      <div className="nav-group">
        <span className="nav-item" style={{ opacity: 0.45, cursor: "default" }}>
          <IconLayers size={16} />
          Remediation
          <span className="tag" style={{ marginLeft: "auto", fontSize: 10 }}>
            Soon
          </span>
        </span>
      </div>

      <div className="sidebar-foot">
        <span className="status-dot" />
        Scanners operational
      </div>
    </nav>
  );
}
