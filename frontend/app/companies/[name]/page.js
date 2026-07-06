"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const STEPS = ["reading", "scraping", "news", "rag", "generating"];
const STEP_LABELS = {
  reading: "Reading documents",
  scraping: "Scraping company website",
  news: "Fetching recent news",
  rag: "Searching expert knowledge",
  generating: "Generating overview",
};

export default function CompanyPage() {
  const { name } = useParams();
  const companyName = decodeURIComponent(name);

  const [pdfs, setPdfs] = useState([]);
  const [selectedPdfs, setSelectedPdfs] = useState([]);
  const [job, setJob] = useState(null);
  const [overview, setOverview] = useState(null);
  const [status, setStatus] = useState("starting"); // starting | running | done | error | cached
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [finalTime, setFinalTime] = useState(null);
  const pollRef = useRef(null);
  const timerRef = useRef(null);
  const startTimeRef = useRef(null);

  useEffect(() => {
    if (companyName) document.title = `${companyName} — Mining AI Analyst`;
  }, [companyName]);

  useEffect(() => {
    if (!companyName) return;

    const forceRegen = new URLSearchParams(window.location.search).get("force") === "true";
    fetch(`${API}/companies/${encodeURIComponent(companyName)}/overview/start?force=${forceRegen}`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        setPdfs(data.pdfs || []);
        setSelectedPdfs(data.selected_pdfs || []);
        if (data.cached) {
          setOverview(data.overview_markdown);
          setStatus("cached");
        } else {
          setStatus("running");
          startTimeRef.current = Date.now();
          timerRef.current = setInterval(() => {
            setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
          }, 1000);
          pollRef.current = setInterval(() => pollJob(data.job_id), 1000);
        }
      })
      .catch((e) => {
        setError(e.message);
        setStatus("error");
      });

    return () => { clearInterval(pollRef.current); clearInterval(timerRef.current); };
  }, [companyName]);

  function pollJob(jobId) {
    fetch(`${API}/overview-jobs/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        setJob(data);
        if (data.status === "done") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setFinalTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
          setOverview(data.overview_markdown);
          setStatus("done");
        } else if (data.status === "error") {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setError(data.error);
          setStatus("error");
        }
      })
      .catch(() => {});
  }

  const currentStepIndex = job ? STEPS.indexOf(job.step) : 0;

  return (
    <main className="max-w-2xl mx-auto p-8">
      <Link href="/" className="text-sm text-gray-400 hover:text-gray-700 mb-6 block">
        ← Chat
      </Link>

      <h1 className="text-2xl font-bold mb-6">{companyName}</h1>

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
                  <span className={isSelected ? "font-medium" : ""}>{label}</span>
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
