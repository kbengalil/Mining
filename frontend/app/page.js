"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";


const INITIAL_MESSAGE = { role: "bot", text: "Hello! I'm the Mining AI Analyst. Ask me anything about mining stocks, or paste a company's investor relations URL to run a full analysis." };

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [analyzedCompanies, setAnalyzedCompanies] = useState([]);

  // Load persisted chat from sessionStorage after mount (client-only)
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("chat_messages");
      if (saved) setMessages(JSON.parse(saved));
      const savedSession = sessionStorage.getItem("chat_session_id");
      if (savedSession) setSessionId(savedSession);
    } catch {}
  }, []);

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
      .then((data) => { if (Array.isArray(data)) setAnalyzedCompanies([...data].sort()); })
      .catch(() => {});
  }, []);

  function clearChat() {
    setMessages([INITIAL_MESSAGE]);
    setSessionId(null);
    try { sessionStorage.removeItem("chat_messages"); sessionStorage.removeItem("chat_session_id"); } catch {}
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
      } else if (data.upload && data.company) {
        // No cache — send user to upload panel
        setAnalyzedCompanies((prev) => prev.includes(data.company) ? prev : [data.company, ...prev].sort());
        setMessages((m) => [...m, { role: "bot", text: data.reply }]);
        router.push(`/companies/${encodeURIComponent(data.company)}`);
      } else if (data.job_id && data.company) {
        // Legacy auto-scan path (kept for backward compatibility)
        setAnalyzedCompanies((prev) => prev.includes(data.company) ? prev : [data.company, ...prev].sort());
        router.push(`/companies/${encodeURIComponent(data.company)}?job=${data.job_id}`);
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

  return (
    <div className="flex h-screen">

      {/* CHAT PANEL */}
      <main className="flex flex-col flex-1 max-w-2xl mx-auto p-4 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 py-3 border-b border-gray-100 mb-4">
          <h1 className="font-semibold text-gray-800">Mining AI Analyst</h1>
          <button
            onClick={clearChat}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            Clear chat
          </button>
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

      {/* RIGHT SIDEBAR — analyzed companies */}
      {analyzedCompanies.length > 0 && (
        <div className="flex-shrink-0 w-44 p-4 pt-6 flex flex-col gap-2 border-l border-gray-100">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Reports</p>
          {analyzedCompanies.filter(n => !n.startsWith("_")).sort().map((name) => (
            <Link
              key={name}
              href={`/companies/${encodeURIComponent(name)}`}
              className="text-xs px-3 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors text-left"
            >
              {name} →
            </Link>
          ))}
          {analyzedCompanies.some(n => n.startsWith("_")) && (
            <>
              <p className="text-xs font-semibold text-gray-300 uppercase tracking-wide mt-3 mb-1">Archived</p>
              {analyzedCompanies.filter(n => n.startsWith("_")).sort().map((name) => (
                <Link
                  key={name}
                  href={`/companies/${encodeURIComponent(name)}`}
                  className="text-xs px-3 py-2 bg-gray-100 text-gray-500 rounded-lg hover:bg-gray-200 transition-colors text-left"
                >
                  {name.replace(/^_/, "")} →
                </Link>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
