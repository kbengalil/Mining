"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

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
          {currency || "%"}
        </text>
      </svg>
    </div>
  );
}

function makeParseInline(pdfUrls) {
  return function parseInline(text) {
    return text.split(/(\*\*[^*]+\*\*|\[src:[^\]]+\])/).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**"))
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      const m = part.match(/^\[src:(.+),\s*p\.(\d+)\]$/);
      if (m) {
        const label = m[1].trim();
        const page = m[2];
        const url = pdfUrls?.[label]
          || Object.entries(pdfUrls || {}).find(([k]) => k.toLowerCase() === label.toLowerCase())?.[1];
        return url ? (
          <a key={i} href={`${url}#page=${page}`} target="_blank" rel="noopener noreferrer"
             className="inline-flex text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 rounded px-1 ml-0.5 no-underline"
             style={{ verticalAlign: "super", lineHeight: 1 }}>
            p.{page}
          </a>
        ) : (
          <sup key={i} className="text-xs text-gray-400 ml-0.5">[p.{page}]</sup>
        );
      }
      return part;
    });
  };
}

function extractInsiderCompBlock(markdown) {
  const sections = markdown.split(/\n(?=## )/).filter(Boolean);
  const teamSection = sections.find((s) =>
    s.trim().split("\n")[0].replace(/^##\s*/, "").trim().startsWith("The Team")
  );
  if (!teamSection) return null;

  const isBlockTitle = (l) => {
    const t = l.trim();
    const bold = /^\*\*([^*]+)\*\*$/.exec(t);
    if (bold) return bold;
    const heading = /^#{2,6}\s+(.+)$/.exec(t);
    if (heading) return [t, heading[1].replace(/\*\*/g, "").trim()];
    return null;
  };

  const contentLines = teamSection.trim().split("\n").slice(1);
  const blocks = [];
  let current = { title: null, lines: [] };
  for (const line of contentLines) {
    const m = isBlockTitle(line);
    if (m) {
      if (current.lines.length > 0) blocks.push(current);
      current = { title: m[1].trim(), lines: [] };
    } else {
      current.lines.push(line);
    }
  }
  blocks.push(current);
  return blocks.find((b) => b.title === "Insider Ownership & Compensation") || null;
}

function InsiderCompBlock({ block, pdfUrls }) {
  const parseInline = makeParseInline(pdfUrls);
  const isSep = (l) => /^\|[-: |]+\|/.test(l.trim());
  const isTableRow = (l) => l.trim().startsWith("|");
  const isBullet = (l) => /^[-*]\s*/.test(l.trim());
  const parseRow = (l) =>
    l.trim().split("|").filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map((c) => c.trim());

  const tableRows = block.lines.filter((l) => isTableRow(l) && !isSep(l));
  const bullets = block.lines.filter((l) => isBullet(l)).map((l) => l.replace(/^[-*]\s*/, "").trim());
  const prose = block.lines.filter((l) => l.trim() && !isTableRow(l) && !isSep(l) && !isBullet(l)).map((l) => l.trim());

  return (
    <div className="mb-8 border-l-2 border-gray-200 pl-4">
      <h3 className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-2">Insider Ownership & Compensation</h3>
      {prose.map((line, j) => (
        <p key={j} className="text-sm text-gray-600 mb-1">{parseInline(line)}</p>
      ))}
      {bullets.length > 0 && (
        <ul className="space-y-1 mb-2">
          {bullets.map((b, j) => (
            <li key={j} className="flex gap-2 text-sm">
              <span className="flex-shrink-0 text-gray-400">•</span>
              <span className="text-gray-700">{parseInline(b)}</span>
            </li>
          ))}
        </ul>
      )}
      {tableRows.length > 0 && (
        <div className="overflow-x-auto mt-2">
          <table className="text-sm w-full border-collapse">
            <thead>
              <tr className="border-b border-gray-200">
                {parseRow(tableRows[0]).map((cell, j) => (
                  <th key={j} className="text-left py-1 pr-4 font-semibold text-gray-700">{parseInline(cell)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(1).map((row, j) => (
                <tr key={j} className="border-b border-gray-100">
                  {parseRow(row).map((cell, k) => (
                    <td key={k} className="py-1 pr-4 text-gray-600 align-top">{parseInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function InsiderOwnershipPage() {
  const { name } = useParams();
  const companyName = decodeURIComponent(name);

  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0, label: "" });
  const [ownershipData, setOwnershipData] = useState(null);
  const [insiderCompBlock, setInsiderCompBlock] = useState(null);
  const [pdfUrls, setPdfUrls] = useState({});
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);
  const jobIdRef = useRef(null);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  useEffect(() => {
    if (!companyName) return;
    document.title = `${companyName} — Insider Ownership`;
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/insider-ownership/data`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setOwnershipData(d.data); })
      .catch(() => {});
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/insider-ownership/files`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setUploadedFiles(d.files || []); })
      .catch(() => {});
    // Reconnect to a job still running server-side (e.g. navigated away and back)
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/insider-ownership/active-job`)
      .then((r) => r.ok ? r.json() : null)
      .then((active) => {
        if (active?.job_id) {
          jobIdRef.current = active.job_id;
          setAnalyzing(true);
          pollRef.current = setInterval(() => pollJob(active.job_id), 1000);
        }
      })
      .catch(() => {});
    // Pull the Insider Ownership & Compensation text from the main report
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (!d) return;
        if (d.source_urls) {
          const map = {};
          d.source_urls.forEach((url) => {
            const label = decodeURIComponent(url.split("/").pop().replace(/\.pdf$/i, ""));
            map[label] = url;
          });
          setPdfUrls(map);
        }
        setInsiderCompBlock(extractInsiderCompBlock(d.overview_markdown));
      })
      .catch(() => {});
  }, [companyName]);

  function pollJob(job_id) {
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/insider-ownership/jobs/${job_id}`)
      .then((r) => r.ok ? r.json() : null)
      .then((job) => {
        if (!job) return;
        setProgress({ current: job.current, total: job.total, label: job.label });
        if (job.status === "done") {
          clearInterval(pollRef.current);
          setOwnershipData(job.data);
          setAnalyzing(false);
        } else if (job.status === "cancelled" || job.status === "error") {
          clearInterval(pollRef.current);
          setAnalyzing(false);
          if (job.error) setError(job.error);
        }
      })
      .catch(() => {});
  }

  async function handleFiles(files) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      Array.from(files).forEach((f) => formData.append("files", f));
      const res = await fetch(
        `${API}/companies/${encodeURIComponent(companyName)}/insider-ownership/upload`,
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
        `${API}/companies/${encodeURIComponent(companyName)}/insider-ownership/analyze`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Analysis failed to start");
      const { job_id, total } = await res.json();
      jobIdRef.current = job_id;
      setProgress({ current: 0, total, label: "Starting..." });
      pollRef.current = setInterval(() => pollJob(job_id), 1000);
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
        `${API}/companies/${encodeURIComponent(companyName)}/insider-ownership/jobs/${jid}/cancel`,
        { method: "POST" }
      );
      jobIdRef.current = null;
    }
    setAnalyzing(false);
  }

  async function deleteAll() {
    if (!confirm("Delete all insider ownership files and results for this company?")) return;
    setDeleting(true);
    try {
      await fetch(
        `${API}/companies/${encodeURIComponent(companyName)}/insider-ownership`,
        { method: "DELETE" }
      );
      setUploadedFiles([]);
      setOwnershipData(null);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setDeleting(false);
    }
  }

  const hasData = ownershipData && ownershipData.length > 0;

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
              onClick={deleteAll}
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
      <p className="text-sm text-gray-500 mb-8">Insider Ownership & CEO Compensation — by Year</p>

      {insiderCompBlock && <InsiderCompBlock block={insiderCompBlock} pdfUrls={pdfUrls} />}

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
            {uploading ? "Uploading..." : "Click to select your AIF/MIC folder"}
          </p>
          <p className="text-xs text-gray-400 mt-1">Include AIF and MIC/proxy files — all PDFs will be uploaded</p>
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
            {ownershipData.length} document{ownershipData.length > 1 ? "s" : ""} analyzed
          </p>
          {ownershipData.some((d) => d.insider_ownership_pct != null) && (
            <BarChart
              data={ownershipData.filter((d) => d.insider_ownership_pct != null)}
              valueKey="insider_ownership_pct"
              label="Insider Ownership (%)"
              color="#0891b2"
              currency="%"
            />
          )}
          {ownershipData.some((d) => d.ceo_total_compensation != null) && (
            <BarChart
              data={ownershipData.filter((d) => d.ceo_total_compensation != null)}
              valueKey="ceo_total_compensation"
              label="CEO Total Compensation ($K)"
              color="#7c3aed"
              currency="$K"
            />
          )}
        </div>
      )}
    </main>
    </>
  );
}
