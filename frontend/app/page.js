"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

const STEPS = ["reading", "scraping", "news", "rag", "generating"];
const STEP_LABELS = {
  reading: "Reading documents",
  scraping: "Scraping website",
  news: "Fetching news",
  rag: "Searching expert knowledge",
  generating: "Generating report",
};

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const INITIAL_MESSAGE = { role: "bot", text: "Hello! I'm the Mining AI Analyst. Ask me anything about mining stocks, or paste a company's investor relations URL to run a full analysis." };

export default function ChatPage() {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem("chat_messages");
      return saved ? JSON.parse(saved) : [INITIAL_MESSAGE];
    } catch { return [INITIAL_MESSAGE]; }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => {
    try { return sessionStorage.getItem("chat_session_id") || null; } catch { return null; }
  });
  const [analyzedCompanies, setAnalyzedCompanies] = useState([]);

  // Persist messages and sessionId to sessionStorage on every change
  useEffect(() => {
    try { sessionStorage.setItem("chat_messages", JSON.stringify(messages)); } catch {}
  }, [messages]);

  useEffect(() => {
    try {
      if (sessionId) sessionStorage.setItem("chat_session_id", sessionId);
    } catch {}
  }, [sessionId]);

  useEffect(() => {
    fetch(`${API}/analyzed-companies`)
      .then((r) => r.json())
      .then((data) => { if (Array.isArray(data)) setAnalyzedCompanies(data); })
      .catch(() => {});
  }, []);

  function clearChat() {
    setMessages([INITIAL_MESSAGE]);
    setSessionId(null);
    setActiveJob(null);
    setPdfs([]);
    setSelectedPdfs([]);
    setJobData(null);
    setJobStatus(null);
    clearInterval(pollRef.current);
    clearInterval(timerRef.current);
    try { sessionStorage.removeItem("chat_messages"); sessionStorage.removeItem("chat_session_id"); } catch {}
  }

  // Analysis panel state
  const [activeJob, setActiveJob] = useState(null); // { jobId, companyName }
  const [pdfs, setPdfs] = useState([]);
  const [selectedPdfs, setSelectedPdfs] = useState([]);
  const [jobData, setJobData] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // "running" | "done" | "error"
  const [elapsed, setElapsed] = useState(0);
  const [finalTime, setFinalTime] = useState(null);
  const pollRef = useRef(null);
  const timerRef = useRef(null);
  const startTimeRef = useRef(null);

  // Cleanup on unmount
  useEffect(() => () => { clearInterval(pollRef.current); clearInterval(timerRef.current); }, []);

  function startPolling(jobId) {
    clearInterval(pollRef.current);
    clearInterval(timerRef.current);
    setElapsed(0);
    setFinalTime(null);
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    pollRef.current = setInterval(() => {
      fetch(`${API}/overview-jobs/${jobId}`)
        .then((r) => r.json())
        .then((data) => {
          setJobData(data);
          if (data.pdfs) setPdfs((p) => p.length === 0 ? data.pdfs : p);
          if (data.selected_pdfs) setSelectedPdfs((p) => p.length === 0 ? data.selected_pdfs : p);
          if (data.status === "done") {
            clearInterval(pollRef.current);
            clearInterval(timerRef.current);
            setFinalTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
            setJobStatus("done");
          } else if (data.status === "error") {
            clearInterval(pollRef.current);
            clearInterval(timerRef.current);
            setJobStatus("error");
          }
        })
        .catch(() => {});
    }, 1000);
  }

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, documents: {}, session_id: sessionId }),
      });
      const data = await res.json();

      if (data.cached && data.company) {
        // Cached report exists — answer came from it, show link to full report
        setSessionId(data.session_id);
        setMessages((m) => [...m, {
          role: "bot",
          text: data.reply,
          reportUrl: data.report_url,
          reportLabel: data.company,
          generatedAt: data.generated_at,
        }]);
      } else if (data.job_id && data.company) {
        // No cache — analysis started, show left panel and start polling
        setActiveJob({ jobId: data.job_id, companyName: data.company });
        setPdfs([]);
        setSelectedPdfs([]);
        setJobData(null);
        setJobStatus("running");
        startPolling(data.job_id);
        setMessages((m) => [...m, { role: "bot", text: `Starting analysis of **${data.company}**. Progress is shown on the left.` }]);
      } else {
        setSessionId(data.session_id);
        setMessages((m) => [...m, { role: "bot", text: data.reply }]);
      }
    } catch {
      setMessages((m) => [...m, { role: "bot", text: "Something went wrong. Please try again." }]);
    } finally {
      setLoading(false);
    }
  }

  const currentStepIndex = jobData ? STEPS.indexOf(jobData.step) : 0;

  return (
    <div className="flex h-screen">

      {/* LEFT PANEL — analysis */}
      <div className={`flex-shrink-0 border-r border-gray-100 overflow-y-auto transition-all duration-300 ${activeJob ? "w-80 p-6" : "w-0 overflow-hidden"}`}>
        {activeJob && (
          <>
            <h2 className="font-semibold text-gray-800 mb-4 text-sm">{activeJob.companyName}</h2>

            {/* PDF list */}
            {pdfs.length > 0 && (
              <div className="mb-6">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                  Documents ({pdfs.length})
                  {selectedPdfs.length > 0 && (
                    <span className="ml-1 text-green-600 normal-case font-normal">· {selectedPdfs.length} used</span>
                  )}
                </p>
                <ul className="space-y-1">
                  {pdfs.map((label, i) => {
                    const isSelected = selectedPdfs.includes(label);
                    return (
                      <li key={i} className={`text-xs flex items-center gap-1.5 ${isSelected ? "text-gray-700" : "text-gray-400"}`}>
                        <span className={isSelected ? "text-green-500 font-bold" : "text-gray-300"}>
                          {isSelected ? "✓" : "—"}
                        </span>
                        {label}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {/* Progress steps */}
            {jobStatus === "running" && jobData && (
              <div className="space-y-3 mb-4">
                {STEPS.map((step, i) => {
                  const done = i < currentStepIndex;
                  const active = i === currentStepIndex;
                  return (
                    <div key={step} className="flex items-start gap-2">
                      <div className={`mt-0.5 w-3.5 h-3.5 rounded-full flex-shrink-0 flex items-center justify-center text-xs ${
                        done ? "bg-green-500" : active ? "bg-blue-500 animate-pulse" : "bg-gray-200"
                      }`}>
                        {done && <span className="text-white text-xs">✓</span>}
                      </div>
                      <div className="flex-1">
                        <p className={`text-xs font-medium ${active ? "text-gray-900" : done ? "text-gray-400" : "text-gray-300"}`}>
                          {STEP_LABELS[step]}
                          {step === "reading" && active && jobData && ` ${jobData.current}/${jobData.total}`}
                        </p>
                        {step === "reading" && active && jobData && (
                          <div className="mt-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full transition-all duration-300"
                              style={{ width: `${(jobData.current / jobData.total) * 100}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {jobStatus === "running" && (
              <p className="text-xs text-gray-400 font-mono">{formatTime(elapsed)}</p>
            )}

            {jobStatus === "done" && (
              <div className="mt-2 space-y-2">
                <p className="text-xs text-green-600 font-medium">✓ Done in {formatTime(finalTime)}</p>
                <Link
                  href={`/companies/${encodeURIComponent(activeJob.companyName)}`}
                  className="block text-center text-sm px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors"
                >
                  View Report →
                </Link>
              </div>
            )}

            {jobStatus === "error" && (
              <p className="text-xs text-red-600">Error: {jobData?.error || "Something went wrong"}</p>
            )}
          </>
        )}
      </div>

      {/* RIGHT PANEL — chat */}
      <main className="flex flex-col flex-1 max-w-2xl mx-auto p-4">
        {/* Header */}
        <div className="flex items-center justify-between py-3 border-b border-gray-100 mb-4">
          <div className="flex items-center gap-3">
            <h1 className="font-semibold text-gray-800">Mining AI Analyst</h1>
            <button
              onClick={clearChat}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
            >
              Clear chat
            </button>
          </div>
          <div className="flex gap-2 flex-wrap justify-end">
            {analyzedCompanies.map((name) => (
              <Link
                key={name}
                href={`/companies/${encodeURIComponent(name)}`}
                className="text-sm px-3 py-1.5 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                {name} →
              </Link>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 pb-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className="max-w-[85%] flex flex-col gap-2">
                <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-gray-900 text-white rounded-br-sm"
                    : "bg-gray-100 text-gray-800 rounded-bl-sm"
                }`}>
                  {m.text}
                </div>
                {m.reportUrl && (
                  <div className="flex items-center gap-2">
                    <Link
                      href={m.reportUrl}
                      className="text-sm px-3 py-1.5 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors"
                    >
                      View Full Report →
                    </Link>
                    {m.generatedAt && (
                      <span className="text-xs text-gray-400">generated {m.generatedAt}</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-400 px-4 py-2.5 rounded-2xl rounded-bl-sm text-sm">
                Thinking...
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="flex gap-2 pt-2 border-t border-gray-100">
          <input
            className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-gray-400"
            placeholder="Ask a question or paste a company URL..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-gray-900 text-white text-sm rounded-xl hover:bg-gray-700 disabled:opacity-40 transition-colors"
          >
            Send
          </button>
        </div>
      </main>
    </div>
  );
}
