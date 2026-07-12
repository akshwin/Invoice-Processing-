import { STATUS, type Decision } from "@/lib/theme";

export default function StatusBadge({ decision }: { decision: Decision }) {
  const s = STATUS[decision];
  return (
    <div className="status-badge" style={{ background: s.bg, borderColor: s.border, color: s.text }}>
      <span className="badge-icon" style={{ background: s.dot }}>
        {s.icon}
      </span>
      {s.label}
    </div>
  );
}
