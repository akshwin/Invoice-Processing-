import StatusBadge from "@/components/StatusBadge";
import type {
  DecisionStageData,
  ExtractionStageData,
  PoMatchingStageData,
  StageData,
  ValidationStageData,
} from "@/lib/api";
import type { Stage } from "@/lib/theme";

function money(v: number | null): string {
  return v === null ? "—" : v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ExtractionPanel({ data }: { data: ExtractionStageData }) {
  const inv = data.extracted_invoice;
  return (
    <>
      {data.extraction_method === "vision" && (
        <p style={{ fontSize: 13, color: "var(--ink-muted)", marginBottom: 14 }}>
          📷 This PDF had no machine-readable text layer (scanned/image-based) — fields were read directly from
          the page image via the vision model.
        </p>
      )}
      <table className="kv-table">
        <tbody>
          <tr>
            <th>Vendor</th>
            <td>{inv.vendor_name ?? "—"}</td>
          </tr>
          <tr>
            <th>Invoice number</th>
            <td>{inv.invoice_number ?? "—"}</td>
          </tr>
          <tr>
            <th>Invoice date</th>
            <td>{inv.invoice_date ?? "—"}</td>
          </tr>
          <tr>
            <th>PO reference</th>
            <td>{inv.po_reference ?? "—"}</td>
          </tr>
          <tr>
            <th>Subtotal</th>
            <td>{money(inv.subtotal)}</td>
          </tr>
          <tr>
            <th>Tax</th>
            <td>{money(inv.tax)}</td>
          </tr>
          <tr>
            <th>Total</th>
            <td>
              <strong>{money(inv.total)}</strong>
            </td>
          </tr>
          <tr>
            <th>Extraction method</th>
            <td>{data.extraction_method === "vision" ? "Vision (scanned image)" : "Text layer"}</td>
          </tr>
        </tbody>
      </table>

      {inv.line_items.length > 0 && (
        <>
          <div className="section-label" style={{ marginTop: 20 }}>
            Line items
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Description</th>
                  <th>Qty</th>
                  <th>Unit price</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {inv.line_items.map((li, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: "normal" }}>{li.description}</td>
                    <td>{li.quantity ?? "—"}</td>
                    <td>{money(li.unit_price)}</td>
                    <td>{money(li.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {inv.extraction_confidence_notes && (
        <>
          <div className="section-label" style={{ marginTop: 20 }}>
            Extraction notes
          </div>
          <p style={{ fontSize: 13.5, color: "var(--ink-secondary)" }}>{inv.extraction_confidence_notes}</p>
        </>
      )}
    </>
  );
}

function PoMatchingPanel({ data }: { data: PoMatchingStageData }) {
  const po = data.matched_po;
  return (
    <>
      <table className="kv-table">
        <tbody>
          <tr>
            <th>Match method</th>
            <td>
              {data.match_method === "po_number" && "Matched by explicit PO number"}
              {data.match_method === "vendor_and_amount" && "Matched by vendor name + amount proximity"}
              {data.match_method === "no_match" && "No match found"}
            </td>
          </tr>
          <tr>
            <th>Notes</th>
            <td>{data.notes}</td>
          </tr>
        </tbody>
      </table>

      <div className="section-label" style={{ marginTop: 20 }}>
        {po ? "Matched purchase order" : "Purchase order"}
      </div>
      {po ? (
        <table className="kv-table">
          <tbody>
            <tr>
              <th>PO number</th>
              <td>{po.po_number}</td>
            </tr>
            <tr>
              <th>Vendor</th>
              <td>{po.vendor_name}</td>
            </tr>
            <tr>
              <th>PO amount</th>
              <td>{money(po.po_amount)}</td>
            </tr>
            <tr>
              <th>PO date</th>
              <td>{po.po_date}</td>
            </tr>
            <tr>
              <th>Status</th>
              <td>{po.status}</td>
            </tr>
          </tbody>
        </table>
      ) : (
        <p className="empty-panel">No matching purchase order was found in the PO dataset.</p>
      )}
    </>
  );
}

function ValidationPanel({ data }: { data: ValidationStageData }) {
  return (
    <div>
      {data.rules_checked.map((rule) => (
        <div key={rule.rule_id} className={`rule-row ${!rule.passed ? "failed" : ""}`}>
          <span className="rule-icon" style={{ background: rule.passed ? "var(--good)" : "var(--bad)" }}>
            {rule.passed ? "✓" : "✕"}
          </span>
          <div>
            <div className="rule-id">
              {rule.rule_id} {!rule.passed && data.failed_rule === rule.rule_id ? "— failed" : rule.passed ? "— passed" : ""}
            </div>
            <div className="rule-message">{rule.message}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function DecisionPanel({ data }: { data: DecisionStageData }) {
  return (
    <>
      <StatusBadge decision={data.decision} />
      <div className="section-label" style={{ marginTop: 20 }}>
        Reasoning
      </div>
      <p>{data.reasoning}</p>
      {data.rules_triggered.length > 0 && (
        <>
          <div className="section-label" style={{ marginTop: 16 }}>
            Rules evaluated
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {data.rules_triggered.map((r) => (
              <span key={r} className="outcome-badge" style={{ borderColor: "var(--border)", color: "var(--ink-secondary)" }}>
                {r}
              </span>
            ))}
          </div>
        </>
      )}
    </>
  );
}

export default function StageDetailPanel({ stage, data }: { stage: Stage; data: StageData | undefined }) {
  if (!data) return <p className="empty-panel">This stage hasn&apos;t run yet.</p>;

  if (stage === "Extraction") return <ExtractionPanel data={data as ExtractionStageData} />;
  if (stage === "PO Matching") return <PoMatchingPanel data={data as PoMatchingStageData} />;
  if (stage === "Validation") return <ValidationPanel data={data as ValidationStageData} />;
  return <DecisionPanel data={data as DecisionStageData} />;
}
