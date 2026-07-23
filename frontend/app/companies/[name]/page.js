"use client";

import Link from "next/link";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { Fragment, useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const STEPS = ["reading", "scraping", "news", "rag", "generating"];

const UPLOAD_DOCS = [
  { key: "Corporate Presentation",          label: "Corporate Presentation",          sedar: false, edgar: false, tip: "Investor pitch deck. Usually under Investors → Corporate Presentation on the company website. Click the download icon (↓) in the PDF viewer to get the direct link." },
  { key: "Management Information Circular", label: "Management Information Circular", sedar: true,  edgar: false, tip: "Annual proxy circular with executive compensation, board details, and AGM voting matters. Usually under Investors → AGM Materials or on SEDAR+." },
  { key: "Financial Statements",            label: "Financial Statements (FS)",       sedar: true,  edgar: true,  tip: "Quarterly or annual financial statements (balance sheet, income statement, cash flows). Found under Investors → Financials — use the most recent quarter's FS link." },
  { key: "MD&A",                            label: "MD&A",                            sedar: true,  edgar: true,  tip: "Management's Discussion & Analysis — accompanies the financial statements. Found in the same Financials section, next to the FS link for the most recent quarter." },
  { key: "Annual Information Form",         label: "Annual Information Form (AIF)",   sedar: true,  edgar: false, tip: "Comprehensive annual regulatory filing covering properties, risks, and company structure. Filed on SEDAR+ — search the company name and filter by Annual information form." },
  { key: "NI 43-101 Technical Report",      label: "NI 43-101 Technical Report",      sedar: true,  edgar: false, tip: "Mineral resource estimate by a Qualified Person. Only exists once a company has enough drill data. Check the Projects or Technical Reports section on their website, or SEDAR+. Early-stage explorers may not have one — leave blank." },
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
  const router = useRouter();
  const companyName = decodeURIComponent(name);
  const isArchive = companyName.startsWith('_') && companyName.includes('[archived');
  const baseCompanyName = isArchive
    ? companyName.replace(/^_/, '').replace(/\s*\[archived[^\]]*\]\s*$/, '').trim()
    : companyName;
  const existingJobId = searchParams.get("job");

  const [pdfs, setPdfs] = useState([]);
  const [selectedPdfs, setSelectedPdfs] = useState([]);
  const [pdfUrls, setPdfUrls] = useState({});
  const [job, setJob] = useState(null);
  const [overview, setOverview] = useState(null);
  const [status, setStatus] = useState("starting"); // starting | upload | running | done | error | cached
  const [uploadedDocs, setUploadedDocs] = useState({});
  const [pendingFiles, setPendingFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [activeReportTab, setActiveReportTab] = useState(0);
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
          // No cached report — load any previously uploaded docs
          fetch(`${API}/companies/${encodeURIComponent(companyName)}/documents/uploaded`)
            .then((r) => r.json())
            .then((data) => { setUploadedDocs(data.documents || {}); setStatus("upload"); })
            .catch(() => setStatus("upload"));
        }
      })
      .catch(() => setStatus("upload"));
  }

  function _startTimer() {
    clearInterval(timerRef.current);
    startTimeRef.current = Date.now();
    sessionStorage.setItem(`job_start_${companyName}`, startTimeRef.current);
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
  }

  function startAnalysis() {
    _startTimer();
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/start?force=true`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        setPdfs(data.pdfs || []);
        setSelectedPdfs(data.selected_pdfs || []);
        if (data.pdf_urls) setPdfUrls(data.pdf_urls);
        jobIdRef.current = data.job_id;
        setStatus("running");
        pollRef.current = setInterval(() => pollJob(data.job_id), 1000);
      })
      .catch((e) => { setError(e.message); setStatus("error"); });
  }

  function regenerate(docsOverride = null) {
    const docs = docsOverride || pdfUrls;
    if (docs && Object.keys(docs).length > 0) {
      if (!startTimeRef.current) _startTimer();
      fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/start-manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ docs, company_url: null }),
      })
        .then((r) => r.json())
        .then((data) => {
          setPdfs(data.pdfs || []);
          setSelectedPdfs(data.selected_pdfs || []);
          if (data.pdf_urls) setPdfUrls(data.pdf_urls);
          jobIdRef.current = data.job_id;
          setStatus("running");
          pollRef.current = setInterval(() => pollJob(data.job_id), 1000);
        })
        .catch((e) => { setError(e.message); setStatus("error"); });
    } else {
      startAnalysis();
    }
  }

  function startManualAnalysis() {
    const docs = Object.fromEntries(
      Object.entries(uploadUrls).filter(([, url]) => url.trim())
    );
    _startTimer();
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/start-manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ docs, company_url: null }),
    })
      .then((r) => r.json())
      .then((data) => {
        setPdfs(data.pdfs || []);
        setSelectedPdfs(data.selected_pdfs || []);
        if (data.pdf_urls) setPdfUrls(data.pdf_urls);
        jobIdRef.current = data.job_id;
        setStatus("running");
        pollRef.current = setInterval(() => pollJob(data.job_id), 1000);
      })
      .catch((e) => { setError(e.message); setStatus("error"); });
  }

  async function uploadAndGenerate(files) {
    _startTimer();
    setStatus("running");
    setUploading(true);
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      const res = await fetch(`${API}/companies/${encodeURIComponent(companyName)}/documents/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setUploadedDocs(data.documents || {});
      regenerate(data.documents);
    } catch (e) {
      setError(e.message);
      setStatus("error");
    } finally {
      setUploading(false);
    }
  }

  async function regenerateFromUploaded() {
    if (isArchive) {
      // On an archive page: use the already-loaded pdfUrls (from source_urls) — no re-upload needed
      const docs = pdfUrls;
      if (Object.keys(docs).length === 0) {
        router.push(`/companies/${encodeURIComponent(baseCompanyName)}`);
        return;
      }
      fetch(`${API}/companies/${encodeURIComponent(baseCompanyName)}/overview/start-manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ docs, company_url: null }),
      })
        .then((r) => r.json())
        .then((d) => router.push(`/companies/${encodeURIComponent(baseCompanyName)}?job=${d.job_id}`))
        .catch((e) => alert("Failed to start regeneration"));
      return;
    }
    // Auto-archive existing report before regenerating (ignore 404 if none exists)
    await fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/archive`, { method: "POST" }).catch(() => {});
    // Use already-loaded pdfUrls so we regenerate with the exact same docs
    if (Object.keys(pdfUrls).length > 0) regenerate(pdfUrls);
    else startAnalysis();
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
          startTimeRef.current = null;
          setOverview(data.overview_markdown);
          setStatus("done");
        } else if (data.status === "error") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          sessionStorage.removeItem(`job_start_${companyName}`);
          startTimeRef.current = null;
          setError(data.error);
          setStatus("error");
        } else if (data.status === "cancelled") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          sessionStorage.removeItem(`job_start_${companyName}`);
          startTimeRef.current = null;
          setStatus("error");
          setError("Analysis stopped.");
        }
      })
      .catch(() => {});
  }

  const currentStepIndex = job ? STEPS.indexOf(job.step) : 0;

  return (
    <>
      {/* Valuation vs Peers — sits in the right gutter on wide screens */}
      <div className="hidden xl:flex flex-col gap-2 fixed right-8 top-8 w-40">
        <button
          onClick={() => setActiveReportTab(REPORT_TABS.findIndex((t) => t.label === "Valuation vs Peers"))}
          className={`text-sm px-4 py-2 rounded-lg border transition-colors text-center ${
            activeReportTab === REPORT_TABS.findIndex((t) => t.label === "Valuation vs Peers")
              ? "bg-blue-600 text-white border-black"
              : "border-black text-gray-600 hover:bg-gray-50"
          }`}
        >
          Valuation vs Peers
        </button>
      </div>
      {/* Home + Delete + Documents list — sits in the left gutter on wide screens */}
      <div className="hidden xl:block fixed left-8 top-8 w-64">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/" className="text-sm text-gray-500 hover:text-gray-800 transition-colors">
            ← Home
          </Link>
          {status !== "running" && status !== "starting" && (
            <button
              onClick={() => {
                if (!confirm(`Delete report for ${companyName}?`)) return;
                fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview`, { method: "DELETE" })
                  .then((r) => { if (r.ok) window.location.href = "/"; else alert("Delete failed"); })
                  .catch(() => alert("Delete failed"));
              }}
              className="text-sm px-2 py-1 border border-black rounded-lg text-red-500 hover:bg-red-50 transition-colors"
            >
              🗑
            </button>
          )}
        </div>
        {pdfs.length > 0 && (status === "done" || status === "cached") && (
          <>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              Documents found ({pdfs.length})
              {selectedPdfs.length > 0 && (
                <span className="block mt-1 text-green-600 normal-case font-normal">
                  {selectedPdfs.length} used for analysis
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
                        className={`hover:underline break-all ${isSelected ? "font-medium" : ""}`}>
                        {label} ↗
                      </a>
                    ) : (
                      <span className={`break-all ${isSelected ? "font-medium" : ""}`}>{label}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
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
              className="text-sm px-4 py-2 border border-black rounded-lg text-red-500 hover:bg-red-50 transition-colors"
            >
              ⏹ Stop
            </button>
          )}
        </div>
      </div>

      {status === "error" && (
        <div className="bg-red-50 text-red-700 rounded-lg p-4 text-sm mb-6">{error}</div>
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

      {/* Document upload panel */}
      {status === "upload" && (
        <div className="mb-8">
          {Object.keys(uploadedDocs).length > 0 ? (
            <>
              <p className="text-sm text-gray-600 mb-1 font-medium">
                Documents on file ({Object.keys(uploadedDocs).length})
              </p>
              <p className="text-xs text-gray-400 mb-4">
                News and website info are fetched automatically.
              </p>
              <ul className="space-y-1 mb-6">
                {Object.keys(uploadedDocs).map((label) => (
                  <li key={label} className="text-sm text-gray-700 flex items-center gap-2">
                    <span className="text-green-500">✓</span> {label}
                  </li>
                ))}
              </ul>
              <div className="flex gap-3 items-center">
                <button
                  onClick={() => regenerate(uploadedDocs)}
                  className="text-sm px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Generate Report
                </button>
                <label className="text-sm text-gray-400 cursor-pointer hover:text-gray-600 transition-colors">
                  Replace files
                  <input
                    type="file"
                    webkitdirectory=""
                    multiple
                    className="hidden"
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []).filter(f => f.name.toLowerCase().endsWith(".pdf"));
                      if (files.length > 0) uploadAndGenerate(files);
                    }}
                  />
                </label>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-600 mb-1 font-medium">
                Upload documents for {companyName}
              </p>
              <p className="text-xs text-gray-400 mb-5">
                Select up to 6 PDF files. News and website info are fetched automatically.
              </p>
              <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-200 rounded-xl cursor-pointer hover:border-blue-300 hover:bg-blue-50 transition-colors mb-4">
                <span className="text-2xl mb-1">📄</span>
                <span className="text-sm text-gray-500">Click to select folder</span>
                <span className="text-xs text-gray-400 mt-0.5">all PDFs in the folder will be uploaded</span>
                <input
                  type="file"
                  webkitdirectory=""
                  multiple
                  className="hidden"
                  onChange={(e) => setPendingFiles(Array.from(e.target.files || []).filter(f => f.name.toLowerCase().endsWith(".pdf")))}
                />
              </label>
              {pendingFiles.length > 0 && (
                <ul className="space-y-1 mb-4">
                  {pendingFiles.map((f) => (
                    <li key={f.name} className="text-sm text-gray-700 flex items-center gap-2">
                      <span className="text-blue-400">📄</span> {f.name}
                    </li>
                  ))}
                </ul>
              )}
              <button
                onClick={() => uploadAndGenerate(pendingFiles)}
                disabled={pendingFiles.length === 0 || uploading}
                className="text-sm px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {uploading ? "Uploading..." : "Generate Report"}
              </button>
            </>
          )}
        </div>
      )}

      {status === "running" && (
        <p className="text-xs text-gray-400 mb-2 font-mono">{formatTime(elapsed)}</p>
      )}

      {/* Overview */}
      {(status === "done" || status === "cached") && overview && (
        <>
          {status === "done" && finalTime !== null && (
            <p className="text-xs text-gray-400 mb-4">Generated in {formatTime(finalTime)}</p>
          )}
          <OverviewRenderer markdown={overview} pdfUrls={pdfUrls} companyName={companyName} activeTab={activeReportTab} setActiveTab={setActiveReportTab} />
        </>
      )}
      </main>
    </>
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

const REPORT_TABS = [
  { label: "Overview & Strategy", sections: ["Company Snapshot", "Strategic Outlook"] },
  { label: "The people behind", sections: ["The Team"] },
  { label: "Financials", sections: ["Financials"] },
  { label: "Recent Developments", sections: ["Recent Developments"] },
  { label: "Red Flags", sections: ["Red Flags"] },
  { label: "Key Project Metrics", sections: ["Key Project Metrics"] },
  { label: "Valuation vs Peers", sections: ["Valuation vs Peers"] },
];

function OverviewRenderer({ markdown, pdfUrls, companyName, activeTab, setActiveTab }) {
  const parseInline = makeParseInline(pdfUrls);
  const allSections = markdown.split(/\n(?=## )/).filter(Boolean);

  const sectionTitle = (section) => section.trim().split("\n")[0].replace(/^##\s*/, "").trim();
  const activeTitles = REPORT_TABS[activeTab].sections;
  const sections = allSections.filter((s) => activeTitles.some((t) => sectionTitle(s).startsWith(t)));

  const [fsSourceOpen, setFsSourceOpen] = useState(false);
  const fsUrl = Object.entries(pdfUrls || {}).find(([k]) => /(^|[-_])fs([-_]|$)/i.test(k))?.[1];

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-6">
        {REPORT_TABS.map((tab, i) => (
          tab.label === "Valuation vs Peers" ? null :
          <Fragment key={tab.label}>
            <button
              onClick={() => setActiveTab(i)}
              className={`text-sm px-4 py-2 rounded-lg border transition-colors ${
                i === activeTab
                  ? "bg-blue-600 text-white border-black"
                  : "border-black text-gray-600 hover:bg-gray-50"
              }`}
            >
              {tab.label}
            </button>
            {tab.label === "The people behind" && (
              <Link
                href={`/companies/${encodeURIComponent(companyName)}/insider-ownership`}
                className="text-sm px-4 py-2 rounded-lg border border-black text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Insiders Ownership
              </Link>
            )}
            {tab.label === "Key Project Metrics" && (
              <div className="relative group">
                <button
                  className="text-sm px-4 py-2 rounded-lg border border-black text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  Dashboard
                </button>
                <div className="hidden group-hover:block absolute left-0 pt-1 w-40 z-10">
                  <div className="bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
                    <Link
                      href={`/companies/${encodeURIComponent(companyName)}/charts`}
                      className="block px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                    >
                      📊 Charts
                    </Link>
                    <Link
                      href={`/companies/${encodeURIComponent(companyName)}/timeline`}
                      className="block px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                    >
                      📈 Time Series
                    </Link>
                  </div>
                </div>
              </div>
            )}
          </Fragment>
        ))}
      </div>
      <div className="space-y-6">
      {sections.map((section, i) => {
        const lines = section.trim().split("\n");
        const title = lines[0].replace(/^##\s*/, "").trim();
        const isRedFlags = title.toLowerCase().includes("red flag");
        const contentLines = lines.slice(1);

        const isSep = (l) => /^\|[-: |]+\|/.test(l.trim());
        const isTableRow = (l) => l.trim().startsWith("|");

        const isBlockTitle = (l) => {
          const t = l.trim();
          const bold = /^\*\*([^*]+)\*\*$/.exec(t);
          if (bold) return bold;
          const heading = /^#{2,6}\s+(.+)$/.exec(t);
          if (heading) return [t, heading[1].replace(/\*\*/g, "").trim()];
          return null;
        };

        const parseRow = (l) =>
          l.trim().split("|").filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map((c) => c.trim());

        // A section can contain multiple sub-tables (e.g. Financials: Balance Sheet,
        // Cash Flow & Capital, Project Economics, Share Structure) each preceded by a
        // standalone **Bold Title** line — split into blocks so each renders separately
        // instead of merging into one table with orphaned titles.
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

        return (
          <div key={i} className={`border-l-2 pl-4 ${isRedFlags ? "border-red-300" : "border-gray-200"}`}>
            <h2 className={`font-semibold mb-2 ${isRedFlags ? "text-red-700" : "text-gray-900"}`}>
              {title}
            </h2>
            {title.startsWith("Financials") && fsUrl && (
              <>
                <button
                  onClick={() => setFsSourceOpen((v) => !v)}
                  className="text-xs text-blue-600 hover:underline mb-3 inline-block"
                >
                  📄 View source page
                </button>
                {fsSourceOpen && (
                  <div
                    className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-6"
                    onClick={() => setFsSourceOpen(false)}
                  >
                    <div
                      className="bg-white rounded-lg shadow-2xl w-full h-full max-w-6xl relative"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => setFsSourceOpen(false)}
                        className="absolute -top-4 -right-4 bg-white border border-black rounded-full w-9 h-9 flex items-center justify-center text-gray-700 hover:bg-gray-100 shadow-lg text-lg"
                      >
                        ✕
                      </button>
                      <embed src={fsUrl} type="application/pdf" className="w-full h-full rounded-lg" />
                    </div>
                  </div>
                )}
              </>
            )}
            {blocks.map((block, bi) => {
              const tableRows = block.lines.filter((l) => isTableRow(l) && !isSep(l));
              const hasTable = tableRows.length > 0;
              const bullets = block.lines.filter((l) => l.trim().startsWith("-")).map((l) => l.replace(/^-\s*/, "").trim());
              const prose = block.lines.filter((l) => l.trim() && !isTableRow(l) && !isSep(l) && !l.trim().startsWith("-")).map((l) => l.trim());

              return (
                <div key={bi} className={bi > 0 ? "mt-8" : ""}>
                  {block.title && (
                    <h3 className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-2">{block.title}</h3>
                  )}
                  {prose.map((line, j) => (
                    <p key={j} className="text-sm text-gray-600 mb-1">{parseInline(line)}</p>
                  ))}
                  {hasTable && (
                    <div className="overflow-x-auto mt-2 mb-2">
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
                  {bullets.length > 0 && (
                    <ul className="space-y-1">
                      {bullets.map((b, j) => (
                        <li key={j} className="flex gap-2 text-sm">
                          <span className={`flex-shrink-0 ${isRedFlags ? "text-red-400" : "text-gray-400"}`}>•</span>
                          <span className={isRedFlags ? "text-red-800" : "text-gray-700"}>{parseInline(b)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}
      </div>
    </div>
  );
}
