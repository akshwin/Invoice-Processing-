"use client";

import { useEffect, useMemo, useState } from "react";
import StatTile from "@/components/StatTile";
import StatusBadge from "@/components/StatusBadge";
import { listRuns, type RunRecord } from "@/lib/api";
import { STATUS, type Decision } from "@/lib/theme";

type SortKey = "timestamp" | "vendor_name" | "invoice_number" | "decision" | "matched_po";

export default function DashboardPage() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);
  const [selected, setSelected] = useState<RunRecord | null>(null);

  useEffect(() => {
    listRuns()
      .then((data) => setRuns(data))
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let rows = runs;
    if (filter) rows = rows.filter((r) => r.decision === filter);
    const sorted = [...rows].sort((a, b) => {
      const av = String(a[sortKey] ?? "");
      const bv = String(b[sortKey] ?? "");
      return av < bv ? -sortDir : av > bv ? sortDir : 0;
    });
    return sorted;
  }, [runs, filter, sortKey, sortDir]);

  const counts = useMemo(() => {
    const c = { total: runs.length, APPROVE: 0, FLAG_FOR_REVIEW: 0, REJECT: 0 };
    for (const r of runs) c[r.decision as Decision] += 1;
    return c;
  }, [runs]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === 1 ? -1 : 1);
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Every invoice processed so far, with the decision, matched PO, and full audit trail behind each call.</p>
      </div>

      {loading && <div className="card">Loading run history…</div>}
      {loadError && <div className="card error-box">Could not load run history: {loadError}</div>}
      {!loading && !loadError && runs.length === 0 && (
        <div className="card">No runs yet. Process an invoice in the Run Pipeline tab to see it here.</div>
      )}
      {!loading && !loadError && runs.length > 0 && (
        <>
          <div className="stat-row">
            <StatTile label="Total runs" value={counts.total} dotColor="#2952cc" />
            <StatTile label="Approved" value={counts.APPROVE} dotColor={STATUS.APPROVE.dot} />
            <StatTile label="Flagged for review" value={counts.FLAG_FOR_REVIEW} dotColor={STATUS.FLAG_FOR_REVIEW.dot} />
            <StatTile label="Rejected" value={counts.REJECT} dotColor={STATUS.REJECT.dot} />
          </div>

          <div className="card">
            <div className="section-label">Run history</div>
            <select className="filter" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">All decisions</option>
              <option value="APPROVE">Approved</option>
              <option value="FLAG_FOR_REVIEW">Flagged for review</option>
              <option value="REJECT">Rejected</option>
            </select>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th onClick={() => toggleSort("timestamp")}>Timestamp</th>
                    <th onClick={() => toggleSort("vendor_name")}>Vendor</th>
                    <th onClick={() => toggleSort("invoice_number")}>Invoice #</th>
                    <th onClick={() => toggleSort("decision")}>Decision</th>
                    <th onClick={() => toggleSort("matched_po")}>Matched PO</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr key={r.run_id} className="clickable" onClick={() => setSelected(r)}>
                      <td>{r.timestamp}</td>
                      <td>{r.vendor_name ?? "—"}</td>
                      <td>{r.invoice_number ?? "—"}</td>
                      <td>
                        {STATUS[r.decision].icon} {STATUS[r.decision].label}
                      </td>
                      <td>{r.matched_po ?? "None"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {selected && (
            <div className="card">
              <div className="section-label">Run detail — {selected.invoice_number ?? selected.run_id}</div>
              <StatusBadge decision={selected.decision} />
              <p style={{ marginTop: 14 }}>
                <span className="field-label">Reasoning</span>
                <br />
                {selected.reasoning}
              </p>
              <details className="json-details">
                <summary>Details — raw extracted data &amp; rule IDs</summary>
                <pre>
                  {JSON.stringify(
                    {
                      rules_triggered: selected.rules_triggered,
                      match_method: selected.match_method,
                      extraction_method: selected.extraction_method,
                      extracted_invoice: selected.extracted_invoice,
                    },
                    null,
                    2
                  )}
                </pre>
              </details>
            </div>
          )}
        </>
      )}
    </div>
  );
}
