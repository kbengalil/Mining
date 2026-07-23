"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

function LineChart({ data, valueKey, label, color, currency }) {
  const values = data.map((d) => d[valueKey]).filter((v) => v != null);
  if (values.length === 0) return <p className="text-xs text-gray-400">No data</p>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 480, H = 140, PAD = 32;

  const points = data
    .filter((d) => d[valueKey] != null)
    .map((d, i, arr) => {
      const x = PAD + (i / (arr.length - 1 || 1)) * (W - PAD * 2);
      const y = H - PAD - ((d[valueKey] - min) / range) * (H - PAD * 2);
      return { x, y, d };
    });

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  return (
    <div className="mb-8">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{label}</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 160 }}>
        <path d={pathD} fill="none" stroke={color} strokeWidth="2" />
        {points.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="4" fill={color} />
            <text x={p.x} y={H - 6} textAnchor="middle" fontSize="9" fill="#9ca3af">
              {p.d.period}
            </text>
            <text x={p.x} y={p.y - 8} textAnchor="middle" fontSize="9" fill={color}>
              {p.d[valueKey]?.toFixed(1)}
            </text>
          </g>
        ))}
        <text x={PAD - 4} y={PAD} textAnchor="end" fontSize="9" fill="#9ca3af">{max.toFixed(0)}</text>
        <text x={PAD - 4} y={H - PAD} textAnchor="end" fontSize="9" fill="#9ca3af">{min.toFixed(0)}</text>
        <text x={4} y={H / 2} fontSize="9" fill="#9ca3af" transform={`rotate(-90, 4, ${H / 2})`}>
          {currency || "M"}
        </text>
      </svg>
    </div>
  );
}

function BarChart({ data, valueKey, label, color, currency }) {
  const values = data.map((d) => d[valueKey]).filter((v) => v != null);
  if (values.length === 0) return <p className="text-xs text-gray-400">No data</p>;

  const max = Math.max(...values) || 1;
  const W = 480, H = 140, PAD = 32;
  const n = data.filter((d) => d[valueKey] != null).length;
  const barW = Math.max(4, ((W - PAD * 2) / n) * 0.6);
  const gap = (W - PAD * 2) / n;

  const bars = data
    .filter((d) => d[valueKey] != null)
    .map((d, i) => {
      const x = PAD + i * gap + gap / 2;
      const barH = ((d[valueKey]) / max) * (H - PAD * 2);
      const y = H - PAD - barH;
      return { x, y, barH, d };
    });

  return (
    <div className="mb-8">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{label}</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 160 }}>
        {bars.map((b, i) => (
          <g key={i}>
            <rect x={b.x - barW / 2} y={b.y} width={barW} height={b.barH} fill={color} opacity="0.85" rx="2" />
            <text x={b.x} y={H - 6} textAnchor="middle" fontSize="9" fill="#9ca3af">
              {b.d.period}
            </text>
            <text x={b.x} y={b.y - 4} textAnchor="middle" fontSize="9" fill={color}>
              {b.d[valueKey]?.toFixed(1)}
            </text>
          </g>
        ))}
        <text x={PAD - 4} y={PAD} textAnchor="end" fontSize="9" fill="#9ca3af">{max.toFixed(0)}</text>
        <text x={4} y={H / 2} fontSize="9" fill="#9ca3af" transform={`rotate(-90, 4, ${H / 2})`}>
          {currency || "M"}
        </text>
      </svg>
    </div>
  );
}

export default function TimelinePage() {
  const { name } = useParams();
  const companyName = decodeURIComponent(name);

  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0, label: "" });
  const [timelineData, setTimelineData] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);
  const jobIdRef = useRef(null);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  useEffect(() => {
    if (!companyName) return;
    document.title = `${companyName} — Time Series`;
    // Load existing results and uploaded files
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/timeline/data`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setTimelineData(d.data); })
      .catch(() => {});
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/timeline/files`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setUploadedFiles(d.files || []); })
      .catch(() => {});
  }, [companyName]);

  async function handleFiles(files) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      Array.from(files).forEach((f) => formData.append("files", f));
      const res = await fetch(
        `${API}/companies/${encodeURIComponent(companyName)}/timeline/upload`,
        { method: "POST", body: formData }
      );
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      setUploadedFiles(Object.keys(data.documents));
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function analyze() {
    setAnalyzing(true);
    setError(null);
    setProgress({ current: 0, total: 0, label: "Starting..." });
    try {
      const res = await fetch(
        `${API}/companies/${encodeURIComponent(companyName)}/timeline/analyze`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Analysis failed to start");
      const { job_id, total } = await res.json();
      jobIdRef.current = job_id;
      setProgress({ current: 0, total, label: "Starting..." });

      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(
            `${API}/companies/${encodeURIComponent(companyName)}/timeline/jobs/${job_id}`
          );
          if (!r.ok) return;
          const job = await r.json();
          setProgress({ current: job.current, total: job.total, label: job.label });
          if (job.status === "done") {
            clearInterval(pollRef.current);
            setTimelineData(job.data);
            setAnalyzing(false);
          } else if (job.status === "cancelled" || job.status === "error") {
            clearInterval(pollRef.current);
            setAnalyzing(false);
            if (job.error) setError(job.error);
          }
        } catch {}
      }, 1000);
    } catch (e) {
      setError(e.message);
      setAnalyzing(false);
    }
  }

  function stopAnalysis() {
    clearInterval(pollRef.current);
    const jid = jobIdRef.current;
    if (jid) {
      fetch(
        `${API}/companies/${encodeURIComponent(companyName)}/timeline/jobs/${jid}/cancel`,
        { method: "POST" }
      );
      jobIdRef.current = null;
    }
    setAnalyzing(false);
  }

  async function deleteTimeline() {
    if (!confirm("Delete all timeline files and results for this company?")) return;
    setDeleting(true);
    try {
      await fetch(
        `${API}/companies/${encodeURIComponent(companyName)}/timeline`,
        { method: "DELETE" }
      );
      setUploadedFiles([]);
      setTimelineData(null);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setDeleting(false);
    }
  }

  const currency = timelineData?.[0]?.cash_currency || "C$";
  const hasData = timelineData && timelineData.length > 0;

  const dataWithRunway = hasData
    ? timelineData.map((d) => {
        const quarterly_burn = (d.quarterly_ga || 0) + (d.exploration_spend || 0);
        return {
          ...d,
          cash_runway:
            d.cash != null && quarterly_burn > 0
              ? parseFloat(((d.cash / quarterly_burn) * 3).toFixed(1))
              : null,
        };
      })
    : [];

  return (
    <>
      {/* Back link + Clear + Documents list — sits in the left gutter on wide screens */}
      <div className="hidden xl:block fixed left-8 top-8 w-64">
        <div className="flex items-center gap-3 mb-6">
          <Link
            href={`/companies/${encodeURIComponent(companyName)}`}
            className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            ← Back to Report
          </Link>
          {uploadedFiles.length > 0 && (
            <button
              onClick={deleteTimeline}
              disabled={deleting || analyzing}
              className="text-sm px-2 py-1 border border-red-200 rounded-lg text-red-500 hover:bg-red-50 disabled:opacity-40 transition-colors"
            >
              🗑
            </button>
          )}
        </div>
        {uploadedFiles.length > 0 && (
          <>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              {uploadedFiles.length} file{uploadedFiles.length > 1 ? "s" : ""} ready
            </p>
            <ul className="space-y-1">
              {uploadedFiles.map((label) => (
                <li key={label} className="flex items-center gap-2 text-sm text-gray-600">
                  <span className="text-green-500">✓</span>
                  <span className="break-all">{label.split("/").pop()}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    <main className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-1">{companyName}</h1>
      <p className="text-sm text-gray-500 mb-8">Time Series — Financial History</p>

      {/* Upload area — hidden once analysis results exist */}
      {!hasData && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors mb-4 border-gray-300 hover:border-gray-400"
        >
          <input
            ref={fileInputRef}
            type="file"
            webkitdirectory=""
            directory=""
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <p className="text-3xl mb-2">📂</p>
          <p className="text-sm font-medium text-gray-700">
            {uploading ? "Uploading..." : "Click to select your timeline folder"}
          </p>
          <p className="text-xs text-gray-400 mt-1">Include quarterly FS and MIC files — all PDFs will be uploaded</p>
        </div>
      )}

      {!hasData && uploadedFiles.length > 0 && (
        <div className="mb-6">
          {analyzing && progress.total > 0 && (
            <div className="mb-3">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span className="truncate max-w-xs">{progress.label}</span>
                <span className="ml-2 shrink-0">{progress.current}/{progress.total}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(progress.current / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={analyze}
              disabled={analyzing}
              className="px-5 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {analyzing ? "Analyzing..." : "⚡ Analyze"}
            </button>
            {analyzing && (
              <button
                onClick={stopAnalysis}
                className="px-4 py-2 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300 transition-colors"
              >
                ✕ Stop
              </button>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-700 rounded-lg p-3 text-sm mb-6">{error}</div>
      )}

      {/* Charts */}
      {hasData && (
        <div className="mt-8 border-t pt-8">
          <p className="text-sm font-semibold text-gray-700 mb-6">
            {timelineData.length} quarters analyzed
          </p>
          <LineChart data={timelineData} valueKey="cash" label={`Cash & Equivalents (${currency}M)`} color="#2563eb" currency={currency + "M"} />
          <LineChart data={dataWithRunway} valueKey="cash_runway" label="Cash Runway (months)" color="#059669" currency="months" />
          <LineChart data={timelineData} valueKey="financial_liabilities" label={`Financial Liabilities (${currency}M)`} color="#dc2626" currency={currency + "M"} />
          <LineChart data={timelineData} valueKey="shares_outstanding" label="Shares Outstanding (M)" color="#7c3aed" currency="M shares" />
          <BarChart data={timelineData} valueKey="exploration_spend" label={`Exploration Spend / Quarter (${currency}M)`} color="#d97706" currency={currency + "M"} />
        </div>
      )}
    </main>
    </>
  );
}
