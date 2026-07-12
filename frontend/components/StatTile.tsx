export default function StatTile({ label, value, dotColor }: { label: string; value: number; dotColor: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-label">
        <span className="stat-dot" style={{ background: dotColor }} />
        {label}
      </div>
      <div className="stat-value">{value}</div>
    </div>
  );
}
