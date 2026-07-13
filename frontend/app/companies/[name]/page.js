"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const STEPS = ["reading", "scraping", "news", "rag", "generating"];

const UPLOAD_DOCS = [
  { key: "Financial Statements",          label: "Financial Statements (FS)" },
  { key: "MD&A",                          label: "MD&A" },
  { key: "Management Information Circular", label: "Management Information Circular" },
  { key: "Annual Information Form",       label: "Annual Information Form (AIF)" },
  { key: "NI 43-101 Technical Report",    label: "NI 43-101 Technical Report" },
  { key: "Corporate Presentation",        label: "Corporate Presentation" },
];
const STEP_LABELS = {
  reading: "Reading documents",
  scraping: "Scraping company website",
  news: "Fetching recent news",
  rag: "Searching expert knowledge",
  generating: "Generating overview",
};

export default function CompanyPage() {
  const { name } = useParams();
  const searchParams = useSearchParams();
  const companyName = decodeURIComponent(name);
  const existingJobId = searchParams.get("job");

  const [pdfs, setPdfs] = useState([]);
  const [selectedPdfs, setSelectedPdfs] = useState([]);
  const [pdfUrls, setPdfUrls] = useState({});
  const [job, setJob] = useState(null);
  const [overview, setOverview] = useState(null);
  const [status, setStatus] = useState("starting"); // starting | upload | running | done | error | cached
  const [uploadUrls, setUploadUrls] = useState(() =>
    Object.fromEntries(UPLOAD_DOCS.map((d) => [d.key, ""]))
  );
  const [companyWebsiteUrl, setCompanyWebsiteUrl] = useState("");
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [finalTime, setFinalTime] = useState(null);
  const pollRef = useRef(null);
  const timerRef = useRef(null);
  const startTimeRef = useRef(null);
  const jobIdRef = useRef(null);

  useEffect(() => {
    if (companyName) document.title = `${companyName} — Mining AI Analyst`;
  }, [companyName]);

  useEffect(() => {
    if (!companyName) return;

    if (existingJobId) {
      // Job already started from chat — poll it directly
      jobIdRef.current = existingJobId;
      setStatus("running");
      const savedStart = sessionStorage.getItem(`job_start_${companyName}`);
      startTimeRef.current = savedStart ? parseInt(savedStart) : Date.now();
      if (!savedStart) sessionStorage.setItem(`job_start_${companyName}`, startTimeRef.current);
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
      pollRef.current = setInterval(() => pollJob(existingJobId), 1000);
    } else {
      // Check if there's already a running job for this company
      fetch(`${API}/companies/${encodeURIComponent(companyName)}/active-job`)
        .then((r) => r.ok ? r.json() : null)
        .then((active) => {
          if (active?.job_id) {
            jobIdRef.current = active.job_id;
            setStatus("running");
            const savedStart = sessionStorage.getItem(`job_start_${companyName}`);
            startTimeRef.current = savedStart ? parseInt(savedStart) : Date.now();
            if (!savedStart) sessionStorage.setItem(`job_start_${companyName}`, startTimeRef.current);
            timerRef.current = setInterval(() => {
              setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
            }, 1000);
            pollRef.current = setInterval(() => pollJob(active.job_id), 1000);
          } else {
            checkCacheOrStart();
          }
        })
        .catch(() => checkCacheOrStart());
    }

    return () => { clearInterval(pollRef.current); clearInterval(timerRef.current); };
  }, [companyName, existingJobId]);

  function checkCacheOrStart() {
      // First check if a cached report exists — show it immediately
      fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview`)
        .then((r) => r.ok ? r.json() : null)
        .then((cached) => {
          if (cached) {
            setOverview(cached.overview_markdown);
            if (cached.source_urls) {
              const map = {};
              cached.source_urls.forEach((url) => {
                const label = decodeURIComponent(url.split("/").pop().replace(/\.pdf$/i, ""));
                map[label] = url;
              });
              setPdfUrls(map);
              setPdfs(Object.keys(map));
              if (cached.selected_urls && cached.selected_urls.length > 0) {
                const selectedLabels = cached.selected_urls.map(
                  (url) => decodeURIComponent(url.split("/").pop().replace(/\.pdf$/i, ""))
                );
                setSelectedPdfs(selectedLabels);
              } else {
                setSelectedPdfs(Object.keys(map));
              }
            }
            setStatus("cached");
          } else {
            setStatus("upload");
          }
        })
        .catch(() => setStatus("upload"));
  }

  function startAnalysis() {
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/start?force=true`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        setPdfs(data.pdfs || []);
        setSelectedPdfs(data.selected_pdfs || []);
        if (data.pdf_urls) setPdfUrls(data.pdf_urls);
        jobIdRef.current = data.job_id;
        setStatus("running");
        startTimeRef.current = Date.now();
        sessionStorage.setItem(`job_start_${companyName}`, startTimeRef.current);
        timerRef.current = setInterval(() => {
          setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
        }, 1000);
        pollRef.current = setInterval(() => pollJob(data.job_id), 1000);
      })
      .catch((e) => { setError(e.message); setStatus("error"); });
  }

  function startManualAnalysis() {
    const docs = Object.fromEntries(
      Object.entries(uploadUrls).filter(([, url]) => url.trim())
    );
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/start-manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ docs, company_url: companyWebsiteUrl.trim() || null }),
    })
      .then((r) => r.json())
      .then((data) => {
        setPdfs(data.pdfs || []);
        setSelectedPdfs(data.selected_pdfs || []);
        if (data.pdf_urls) setPdfUrls(data.pdf_urls);
        jobIdRef.current = data.job_id;
        setStatus("running");
        startTimeRef.current = Date.now();
        sessionStorage.setItem(`job_start_${companyName}`, startTimeRef.current);
        timerRef.current = setInterval(() => {
          setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
        }, 1000);
        pollRef.current = setInterval(() => pollJob(data.job_id), 1000);
      })
      .catch((e) => { setError(e.message); setStatus("error"); });
  }

  function pollJob(jobId) {
    fetch(`${API}/overview-jobs/${jobId}`)
      .then((r) => {
        if (!r.ok) {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setStatus("error");
          setError("Analysis not found. The server may have restarted — please try again.");
          return Promise.reject(r.status);
        }
        return r.json();
      })
      .then((data) => {
        setJob(data);
        // Populate pdfs from job data when navigating from chat
        if (data.pdfs) setPdfs((prev) => prev.length === 0 ? data.pdfs : prev);
        if (data.selected_pdfs) setSelectedPdfs((prev) => prev.length === 0 ? data.selected_pdfs : prev);
        if (data.pdf_urls) setPdfUrls((prev) => Object.keys(prev).length === 0 ? data.pdf_urls : prev);
        if (data.status === "done") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          sessionStorage.removeItem(`job_start_${companyName}`);
          setFinalTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
          setOverview(data.overview_markdown);
          setStatus("done");
        } else if (data.status === "error") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          sessionStorage.removeItem(`job_start_${companyName}`);
          setError(data.error);
          setStatus("error");
        } else if (data.status === "cancelled") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          sessionStorage.removeItem(`job_start_${companyName}`);
          setStatus("error");
          setError("Analysis stopped.");
        }
      })
      .catch(() => {});
  }

  const currentStepIndex = job ? STEPS.indexOf(job.step) : 0;

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{companyName}</h1>
        <div className="flex gap-2">
          {status === "running" && (
            <button
              onClick={() => {
                const id = jobIdRef.current;
                if (!id) return;
                fetch(`${API}/overview-jobs/${id}/cancel`, { method: "POST" }).catch(() => {});
                clearInterval(pollRef.current);
                clearInterval(timerRef.current);
                setStatus("error");
                setError("Analysis stopped.");
              }}
              className="text-sm px-4 py-2 border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
            >
              ⏹ Stop
            </button>
          )}
          {status === "cached" && (
            <button
              onClick={startAnalysis}
              className="text-sm px-4 py-2 border border-gray-300 rounded-lg text-gray-500 hover:bg-gray-50 transition-colors"
            >
              ↻ Regenerate
            </button>
          )}
          {(status === "cached" || status === "done") && (
            <button
              onClick={() => {
                if (!confirm(`Archive report for ${companyName}?`)) return;
                fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/archive`, { method: "POST" })
                  .then(r => r.json())
                  .then(d => alert(`Archived as: ${d.archived_as}`))
                  .catch(() => alert("Archive failed"));
              }}
              className="text-sm px-4 py-2 border border-gray-300 rounded-lg text-gray-500 hover:bg-gray-50 transition-colors"
            >
              📦 Archive
            </button>
          )}
          {status !== "running" && status !== "starting" && (
            <button
              onClick={() => {
                if (!confirm(`Delete report for ${companyName}?`)) return;
                fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview`, { method: "DELETE" })
                  .then(() => window.location.href = "/");
              }}
              className="text-sm px-4 py-2 border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
            >
              🗑 Delete
            </button>
          )}
          <Link
            href={`/companies/${encodeURIComponent(companyName)}/charts`}
            className="text-sm px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
          >
            📊 Charts
          </Link>
          <Link
            href="/"
            className="text-sm px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
          >
            ← Back to Chat
          </Link>
        </div>
      </div>

      {status === "error" && (
        <div className="bg-red-50 text-red-700 rounded-lg p-4 text-sm mb-6">{error}</div>
      )}

      {/* PDF list */}
      {pdfs.length > 0 && (
        <div className="mb-8">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Documents found ({pdfs.length})
            {selectedPdfs.length > 0 && (
              <span className="ml-2 text-green-600 normal-case font-normal">
                · {selectedPdfs.length} used for analysis
              </span>
            )}
          </p>
          <ul className="space-y-1">
            {pdfs.map((label, i) => {
              const isSelected = selectedPdfs.includes(label);
              return (
                <li key={i} className={`text-sm flex items-center gap-2 ${isSelected ? "text-gray-800" : "text-gray-400"}`}>
                  <span className={isSelected ? "text-green-500 font-bold" : "text-gray-300"}>
                    {isSelected ? "✓" : "—"}
                  </span>
                  {pdfUrls[label] ? (
                    <a href={pdfUrls[label]} target="_blank" rel="noopener noreferrer"
                      className={`hover:underline ${isSelected ? "font-medium" : ""}`}>
                      {label} ↗
                    </a>
                  ) : (
                    <span className={isSelected ? "font-medium" : ""}>{label}</span>
                  )}
                  {isSelected && (
                    <span className="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">used</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Progress */}
      {status === "running" && job && (
        <div className="mb-8 space-y-4">
          {STEPS.map((step, i) => {
            const done = i < currentStepIndex;
            const active = i === currentStepIndex;
            const isPdfStep = step === "reading";

            return (
              <div key={step} className="flex items-start gap-3">
                <div className={`mt-0.5 w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center text-xs ${
                  done ? "bg-green-500" : active ? "bg-blue-500 animate-pulse" : "bg-gray-200"
                }`}>
                  {done && <span className="text-white">✓</span>}
                </div>
                <div className="flex-1">
                  <p className={`text-sm font-medium ${active ? "text-gray-900" : done ? "text-gray-400" : "text-gray-300"}`}>
                    {STEP_LABELS[step]}
                    {isPdfStep && active && ` — ${job.current}/${job.total}`}
                  </p>
                  {isPdfStep && active && (
                    <div className="mt-1.5 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all duration-300"
                        style={{ width: `${(job.current / job.total) * 100}%` }}
                      />
                    </div>
                  )}
                  {active && !isPdfStep && (
                    <p className="text-xs text-gray-400 mt-0.5">{job.label}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {status === "starting" && (
        <p className="text-sm text-gray-400 mb-8">Finding documents...</p>
      )}

      {/* Manual document upload panel */}
      {status === "upload" && (
        <div className="mb-8">
          <p className="text-sm text-gray-600 mb-1 font-medium">
            Paste PDF links from {companyName}&apos;s investor relations page.
          </p>
          <p className="text-xs text-gray-400 mb-5">
            All fields are optional — leave blank to skip. News and website info are fetched automatically.
          </p>
          <div className="space-y-3 mb-6">
            <div className="flex items-center gap-3 pb-3 mb-1 border-b border-gray-100">
              <label className="text-sm text-gray-500 w-56 flex-shrink-0">Company website URL</label>
              <input
                type="url"
                placeholder="https://sunpeakmetals.com (optional — for news & about page)"
                value={companyWebsiteUrl}
                onChange={(e) => setCompanyWebsiteUrl(e.target.value)}
                className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200"
              />
            </div>
            {UPLOAD_DOCS.map(({ key, label }) => (
              <div key={key} className="flex items-center gap-3">
                <label className="text-sm text-gray-600 w-56 flex-shrink-0">{label}</label>
                <input
                  type="url"
                  placeholder="https://..."
                  value={uploadUrls[key]}
                  onChange={(e) =>
                    setUploadUrls((prev) => ({ ...prev, [key]: e.target.value }))
                  }
                  className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button
              onClick={startManualAnalysis}
              className="text-sm px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Generate Report
            </button>
            <button
              onClick={startAnalysis}
              className="text-sm px-5 py-2 border border-gray-300 rounded-lg text-gray-500 hover:bg-gray-50 transition-colors"
            >
              Skip — auto-scan instead
            </button>
          </div>
        </div>
      )}

      {status === "running" && (
        <p className="text-xs text-gray-400 mb-2 font-mono">{formatTime(elapsed)}</p>
      )}

      {/* Overview */}
      {(status === "done" || status === "cached") && overview && (
        <>
          {status === "cached" && (
            <p className="text-xs text-gray-400 mb-4">Loaded from cache — regenerates automatically when new documents are found.</p>
          )}
          {status === "done" && finalTime !== null && (
            <p className="text-xs text-gray-400 mb-4">Generated in {formatTime(finalTime)}</p>
          )}
          <OverviewRenderer markdown={overview} />
        </>
      )}
    </main>
  );
}

function OverviewRenderer({ markdown }) {
  const sections = markdown.split(/\n(?=## )/).filter(Boolean);

  return (
    <div className="space-y-6">
      {sections.map((section, i) => {
        const lines = section.trim().split("\n");
        const title = lines[0].replace(/^##\s*/, "").trim();
        const isRedFlags = title.toLowerCase().includes("red flag");

        const bullets = lines
          .slice(1)
          .filter((l) => l.trim().startsWith("-"))
          .map((l) => l.replace(/^-\s*/, "").trim());

        const prose = lines
          .slice(1)
          .filter((l) => l.trim() && !l.trim().startsWith("-"))
          .map((l) => l.trim());

        return (
          <div key={i} className={`border-l-2 pl-4 ${isRedFlags ? "border-red-300" : "border-gray-200"}`}>
            <h2 className={`font-semibold mb-2 ${isRedFlags ? "text-red-700" : "text-gray-900"}`}>
              {title}
            </h2>
            {prose.map((line, j) => (
              <p key={j} className="text-sm text-gray-600 mb-1">{line}</p>
            ))}
            {bullets.length > 0 && (
              <ul className="space-y-1">
                {bullets.map((b, j) => (
                  <li key={j} className="flex gap-2 text-sm">
                    <span className={`flex-shrink-0 ${isRedFlags ? "text-red-400" : "text-gray-400"}`}>•</span>
                    <span className={isRedFlags ? "text-red-800" : "text-gray-700"}>{b}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
