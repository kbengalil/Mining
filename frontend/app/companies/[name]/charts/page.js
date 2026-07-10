"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

export default function ChartsPage() {
  const { name } = useParams();
  const companyName = decodeURIComponent(name);

  const [status, setStatus] = useState("starting"); // starting | running | done | error
  const [charts, setCharts] = useState([]);
  const [progress, setProgress] = useState({ current: 0, total: 0, label: "" });
  const [lightbox, setLightbox] = useState(null); // {image, document, page}
  const pollRef = useRef(null);

  useEffect(() => {
    if (!companyName) return;
    document.title = `${companyName} — Charts`;

    fetch(`${API}/companies/${encodeURIComponent(companyName)}/charts/start`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        if (data.cached) {
          setCharts(data.charts);
          setStatus("done");
        } else {
          setStatus("running");
          pollRef.current = setInterval(() => pollJob(data.job_id), 1500);
        }
      })
      .catch(() => setStatus("error"));

    return () => clearInterval(pollRef.current);
  }, [companyName]);

  function pollJob(jobId) {
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/charts/jobs/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        setProgress({ current: data.current, total: data.total, label: data.label });
        if (data.status === "done") {
          clearInterval(pollRef.current);
          setCharts(data.charts);
          setStatus("done");
        }
      })
      .catch(() => {});
  }

  // Group charts by document
  const byDocument = charts.reduce((acc, chart) => {
    if (!acc[chart.document]) acc[chart.document] = [];
    acc[chart.document].push(chart);
    return acc;
  }, {});

  return (
    <main className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{companyName} — Charts</h1>
        <Link
          href={`/companies/${encodeURIComponent(companyName)}`}
          className="text-sm px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
        >
          ← Back to Report
        </Link>
      </div>

      {status === "starting" && (
        <p className="text-sm text-gray-400">Starting extraction...</p>
      )}

      {status === "running" && (
        <div className="space-y-2">
          <p className="text-sm text-gray-600">
            Scanning documents for charts ({progress.current}/{progress.total})
          </p>
          {progress.label && (
            <p className="text-xs text-gray-400 font-mono truncate">{progress.label}</p>
          )}
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden w-full max-w-sm">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: progress.total ? `${(progress.current / progress.total) * 100}%` : "0%" }}
            />
          </div>
        </div>
      )}

      {status === "error" && (
        <p className="text-sm text-red-600">Something went wrong. Please go back and try again.</p>
      )}

      {status === "done" && charts.length === 0 && (
        <p className="text-sm text-gray-500">No chart pages found in the source documents.</p>
      )}

      {status === "done" && charts.length > 0 && (
        <div className="space-y-10">
          {Object.entries(byDocument).map(([doc, pages]) => (
            <div key={doc}>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                {doc.split("?")[0]}
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {pages.map((chart, idx) => (
                  <button
                    key={`${doc}-${chart.page}-${idx}`}
                    onClick={() => setLightbox(chart)}
                    className="border border-gray-200 rounded-lg overflow-hidden hover:border-blue-400 hover:shadow-md transition-all text-left"
                  >
                    <img
                      src={`data:image/png;base64,${chart.image}`}
                      alt={`${doc} page ${chart.page}`}
                      className="w-full object-contain bg-white"
                    />
                    <p className="text-xs text-gray-400 px-2 py-1">Page {chart.page}</p>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50 p-4"
          onClick={() => setLightbox(null)}
        >
          <div className="max-w-4xl max-h-full overflow-auto" onClick={(e) => e.stopPropagation()}>
            <img
              src={`data:image/png;base64,${lightbox.image}`}
              alt={`${lightbox.document} page ${lightbox.page}`}
              className="w-full rounded-lg"
            />
            <p className="text-white text-sm text-center mt-2 opacity-70">
              {lightbox.document} — Page {lightbox.page} · Click outside to close
            </p>
          </div>
        </div>
      )}
    </main>
  );
}
