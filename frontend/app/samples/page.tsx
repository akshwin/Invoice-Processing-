"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listSamples, sampleDownloadUrl, type SampleInvoice } from "@/lib/api";
import { STATUS } from "@/lib/theme";

export default function SamplesPage() {
  const router = useRouter();
  const [samples, setSamples] = useState<SampleInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    listSamples()
      .then(setSamples)
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h2>Sample Invoices</h2>
        <p>
          Thirteen canonical test invoices covering the happy path, scanned/photographed invoices, rule-violation
          edge cases, and a completely different layout — use these to explore the pipeline without needing your
          own PDF.
        </p>
      </div>

      {loading && <div className="card">Loading sample invoices…</div>}
      {loadError && <div className="card error-box">Could not load samples: {loadError}</div>}

      {!loading && !loadError && (
        <div className="samples-grid">
          {samples.map((s) => {
            const status = STATUS[s.expected_outcome];
            return (
              <div key={s.filename} className="sample-card">
                <div className="sample-top">
                  <div>
                    <div className="sample-label">{s.label}</div>
                    <div className="sample-vendor">{s.vendor_name}</div>
                  </div>
                  <span
                    className="outcome-badge"
                    style={{ background: status.bg, borderColor: status.border, color: status.text }}
                  >
                    {status.icon} {status.label}
                  </span>
                </div>
                <p className="sample-description">{s.description}</p>
                <div className="sample-actions">
                  <button className="btn-secondary" onClick={() => router.push(`/?sample=${encodeURIComponent(s.filename)}`)}>
                    Try this sample
                  </button>
                  <a className="btn-secondary" href={sampleDownloadUrl(s.filename)} download>
                    Download
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
