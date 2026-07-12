"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Run Pipeline", icon: "▶" },
  { href: "/samples", label: "Sample Invoices", icon: "🗎" },
  { href: "/dashboard", label: "Dashboard", icon: "▦" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">IP</div>
        <div className="brand-text">
          <h1>Invoice Processing</h1>
          <span>AI-assisted AP automation</span>
        </div>
      </div>

      <div className="sidebar-section-label">Workspace</div>
      <nav className="sidebar-nav">
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} className={pathname === link.href ? "active" : ""}>
            <span className="nav-icon">{link.icon}</span>
            {link.label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer">
        Extraction → PO Matching → Validation → Decision, backed by LangGraph and rule-based checks
        BR-1–BR-5.
      </div>
    </aside>
  );
}
