import { useEffect, useRef, useState } from "react";
import { Activity, AlertTriangle, ArrowDownToLine, ArrowUpRight, Check, ChevronDown, CircleHelp, FileText, LoaderCircle, MessageCircle, Paperclip, Send, ShieldCheck, Sparkles, UploadCloud, X } from "lucide-react";
import type { Action, Analysis, Evidence, Message } from "./types";
import Timeline from "./Timeline";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [provider, setProvider] = useState("checking");
  const [sizeLimit, setSizeLimit] = useState(10);
  const [filename, setFilename] = useState("");
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [outcomes, setOutcomes] = useState<Record<string, string>>({});
  const [expandedEvidence, setExpandedEvidence] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${API}/api/health`).then((response) => response.json()).then((body) => { if (active) { setProvider(body.ai_provider); setSizeLimit(body.max_upload_mb ?? 10); } }).catch(() => { if (active) setProvider("offline"); });
    return () => { active = false; };
  }, []);

  async function upload(file?: File) {
    if (!file) return;
    setError(""); setAnalysis(null); setFilename(file.name); setMessages([]); setOutcomes({}); setLoading(true);
    const form = new FormData(); form.append("file", file);
    try {
      const response = await fetch(`${API}/api/incidents`, { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Upload could not be processed.");
      setAnalysis(body);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to reach the analysis service. Check that the backend is running.");
    } finally { setLoading(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function ask(question = draft) {
    if (!analysis || !question.trim() || chatBusy) return;
    const userMessage: Message = { role: "user", content: question.trim(), created_at: new Date().toISOString() };
    setMessages((current) => [...current, userMessage]); setDraft(""); setChatBusy(true);
    try {
      const response = await fetch(`${API}/api/incidents/${analysis.incident_id}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: question.trim() }) });
      const body = await response.json(); if (!response.ok) throw new Error(body.detail ?? "Chat request failed.");
      setMessages(body.history);
    } catch (cause) {
      setMessages((current) => [...current, { role: "assistant", content: cause instanceof Error ? cause.message : "Chat is unavailable.", created_at: new Date().toISOString() }]);
    } finally { setChatBusy(false); }
  }

  async function reportOutcome(action: Action, outcome: "resolved" | "partially_resolved" | "unsuccessful" | "inconclusive") {
    if (!analysis || outcomes[action.action_id]) return;
    try {
      const response = await fetch(`${API}/api/incidents/${analysis.incident_id}/actions/${action.action_id}/outcome`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ performed: outcome !== "inconclusive", outcome, explanation: "Reported in dashboard" }) });
      if (!response.ok) throw new Error("Could not record this outcome.");
      setOutcomes((current) => ({ ...current, [action.action_id]: outcome }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not record outcome."); }
  }

  function evidenceFor(ids: string[]): Evidence[] { return analysis?.evidence.filter((item) => ids.includes(item.evidence_id)) ?? []; }
  const dropProps = {
    onDragOver: (event: React.DragEvent) => { event.preventDefault(); setDragging(true); },
    onDragLeave: () => setDragging(false),
    onDrop: (event: React.DragEvent) => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files[0]); },
  };

  return <main className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top" aria-label="InfraGuide AI home"><span className="brand-mark"><Activity size={19} strokeWidth={2.4} /></span><span>InfraGuide<span className="brand-ai"> AI</span></span></a>
      <div className="topbar-right"><span className={`status-dot ${provider === "offline" ? "offline" : ""}`} /> <span>{provider === "local_api_ready" ? "LM STUDIO MODEL READY" : provider === "local_model_not_loaded" ? "LOAD MODEL IN LM STUDIO" : provider === "local_api_offline" ? "LM STUDIO OFFLINE" : provider === "local_config_invalid" ? "LOCAL API CONFIG INVALID" : provider === "deterministic" ? "DETERMINISTIC MODE" : provider === "offline" ? "BACKEND OFFLINE" : "CONNECTING"}</span><span className="top-divider" /><a href="#privacy">Privacy & safety <ArrowUpRight size={13} /></a></div>
    </header>
    <div className="workspace" id="top">
      <aside className="rail">
        <div className="rail-heading">WORKSPACE</div>
        <div className="rail-item active"><Activity size={16} />Incident analysis</div>
        <div className="rail-caption">CURRENT INCIDENT</div>
        {analysis ? <button className="incident-chip" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}><span className="incident-chip-mark"><FileText size={14} /></span><span className="incident-name">{filename}</span><span className="incident-severity" /></button> : <p className="rail-empty">No incident loaded</p>}
        <div className="rail-spacer" />
        <div className="rail-note"><ShieldCheck size={16} /><span>Read-only by design</span></div>
      </aside>

      <section className="main-column">
        <div className="page-heading">
          <div><div className="eyebrow"><span>INFRASTRUCTURE INTELLIGENCE</span><span className="eyebrow-line" /></div><h1>Log analysis</h1><p className="page-intro">Turn system signals into evidence-led next steps.</p></div>
          {analysis && <button className="quiet-button" onClick={() => inputRef.current?.click()}><ArrowDownToLine size={15} /> New analysis</button>}
        </div>

        {!analysis && <section className={`upload-zone ${dragging ? "dragging" : ""}`} {...dropProps} aria-label="Upload a log file">
          <input ref={inputRef} className="visually-hidden" type="file" accept=".log,.txt,.csv,.json,.zip" onChange={(event) => void upload(event.target.files?.[0])} />
          <div className="upload-icon"><UploadCloud size={22} /></div>
          <h2>{loading ? "Reading log evidence" : "Start with a log file"}</h2>
          <p>{loading ? "Parsing records and preparing a traceable analysis." : "Drop a log here, or choose a file from your device."}</p>
          {loading ? <div className="loading-line"><LoaderCircle size={16} className="spin" /> Processing uploaded evidence</div> : <button className="primary-button" onClick={() => inputRef.current?.click()}><Paperclip size={15} /> Select log file</button>}
          <div className="upload-formats"><span>LOG</span><span>TXT</span><span>CSV</span><span>JSON</span><span>ZIP</span><i />Up to {sizeLimit} MB</div>
          <p className="format-note">EVTX parsing is not installed. ZIP entries are validated before processing.</p>
        </section>}
        {error && <div className="error-banner" role="alert"><AlertTriangle size={17} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError("")}><X size={16} /></button></div>}

        {analysis && <div className="report">
          <section className="summary-panel">
            <div className="summary-top"><div className="summary-label"><Sparkles size={15} /> INCIDENT BRIEF</div><div className={`severity-pill ${analysis.severity}`}>{analysis.severity === "unknown" ? "UNCLASSIFIED" : `${analysis.severity.toUpperCase()} SIGNAL`}</div></div>
            <h2>{analysis.summary}</h2>
            <div className="summary-meta"><span><span className="meta-key">SOURCE</span>{filename}</span><span><span className="meta-key">DETECTED FORMAT</span>{analysis.detected_log_type.replaceAll("_", " ")}</span><span><span className="meta-key">RECORDS</span>{analysis.evidence.length}</span></div>
          </section>

          <div className="section-heading"><div><span className="section-index">01</span><h2>Event timeline</h2></div><span className="section-count">{analysis.evidence.filter((event) => event.timestamp).length} TIMESTAMPED RECORDS</span></div>
          <Timeline evidence={analysis.evidence} />
          <div className="section-heading"><div><span className="section-index">02</span><h2>Signal & evidence</h2></div><span className="section-count">{analysis.findings.length} FINDINGS</span></div>
          {analysis.findings.length === 0 ? <div className="empty-section"><CircleHelp size={17} /><span>No explicit errors or repeated messages were found in the parsed records.</span></div> : <div className="finding-list">{analysis.findings.map((finding) => <article className="finding-row" key={finding.finding_id}><div className={`finding-marker ${finding.severity}`}><AlertTriangle size={15} /></div><div className="finding-content"><div className="finding-title-row"><h3>{finding.title}</h3><span>{finding.severity.toUpperCase()}</span></div><p>{finding.detail}</p><EvidenceDisclosure ids={finding.evidence_ids} records={evidenceFor(finding.evidence_ids)} expandedEvidence={expandedEvidence} setExpandedEvidence={setExpandedEvidence} /></div></article>)}</div>}

          <div className="section-heading"><div><span className="section-index">03</span><h2>Diagnostic hypotheses</h2></div><span className="section-count">NOT CONFIRMED</span></div>
          <div className="hypothesis-list">{analysis.hypotheses.map((hypothesis, index) => <article className="hypothesis-row" key={hypothesis.hypothesis_id}><div className="hypothesis-number">0{index + 1}</div><div className="hypothesis-copy"><div className="hypothesis-title-row"><h3>{hypothesis.title}</h3><span className={`confidence ${hypothesis.confidence}`}>{hypothesis.confidence} confidence</span></div><p>{hypothesis.explanation}</p>{hypothesis.alternatives.length > 0 && <p className="alternatives"><b>Also possible:</b> {hypothesis.alternatives.join("; ")}</p>}<EvidenceDisclosure ids={hypothesis.evidence_ids} records={evidenceFor(hypothesis.evidence_ids)} expandedEvidence={expandedEvidence} setExpandedEvidence={setExpandedEvidence} /></div></article>)}</div>

          <div className="section-heading"><div><span className="section-index">04</span><h2>Recommended next steps</h2></div><span className="section-count">ADVISORY ONLY</span></div>
          <div className="action-list">{analysis.actions.map((action, index) => <ActionRow key={action.action_id} action={action} index={index} evidence={evidenceFor(action.evidence_ids)} sources={analysis.sources.filter((source) => action.source_ids.includes(source.source_id))} outcome={outcomes[action.action_id]} onOutcome={(value) => void reportOutcome(action, value)} expandedEvidence={expandedEvidence} setExpandedEvidence={setExpandedEvidence} />)}</div>

          <div className="notice-stack">{analysis.safety_notes.map((note) => <div className="notice safety" key={note}><ShieldCheck size={16} /><p>{note}</p></div>)}{analysis.limitations.map((note) => <div className="notice limitation" key={note}><CircleHelp size={16} /><p>{note}</p></div>)}{analysis.missing_information.length > 0 && <div className="missing-info"><span>MISSING CONTEXT</span>{analysis.missing_information.join("  /  ")}</div>}</div>
        </div>}
        <footer id="privacy"><div><ShieldCheck size={15} /><span>Inference uses the local model configured on this PC; no hosted AI model is called.</span></div><span>Do not submit confidential production logs until deployment controls are approved.</span></footer>
      </section>

      <aside className="chat-panel">
        <div className="chat-header"><div className="chat-icon"><MessageCircle size={16} /></div><div><h2>Guided troubleshooting</h2><p>{analysis ? "Context linked to this incident" : "Waiting for an incident"}</p></div><button className="icon-button" title="Chat uses incident context" aria-label="Chat information"><CircleHelp size={16} /></button></div>
        <div className="chat-body">
          {!analysis ? <div className="chat-empty"><div className="chat-empty-icon"><MessageCircle size={20} /></div><h3>Start a conversation</h3><p>Upload a log to ask about findings, evidence, and the suggested next steps.</p></div> : <>
            <div className="chat-context"><span className="context-pulse" /> CONTEXT: {filename}</div>
            {messages.length === 0 && <div className="assistant-intro"><div className="assistant-avatar"><Sparkles size={15} /></div><div><span className="assistant-label">INFRAGUIDE</span><p>I’ve linked this conversation to the parsed evidence. I’ll distinguish observations from hypotheses and call out missing context.</p></div></div>}
            {messages.map((message, index) => <div className={`chat-message ${message.role}`} key={`${message.created_at}-${index}`}>{message.role === "assistant" && <div className="assistant-avatar small"><Sparkles size={13} /></div>}<p>{message.content}</p></div>)}
            {chatBusy && <div className="chat-typing"><LoaderCircle size={14} className="spin" /> Reviewing incident context</div>}
          </>}
        </div>
        {analysis && <div className="suggestions"><span>QUICK QUESTIONS</span><button onClick={() => void ask("Why is the first recommendation ranked first?")}>Why is this the first step?</button><button onClick={() => void ask("What additional context would help narrow the cause?")}>What context is missing?</button></div>}
        <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); void ask(); }}><textarea aria-label="Ask about this incident" disabled={!analysis || chatBusy} placeholder={analysis ? "Ask about this incident..." : "Upload a log to begin"} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void ask(); } }} rows={2} /><button className="send-button" type="submit" title="Send message" aria-label="Send message" disabled={!analysis || !draft.trim() || chatBusy}><Send size={16} /></button><span>Enter to send · Shift+Enter for a new line</span></form>
        <div className="chat-footnote"><ShieldCheck size={14} /> No commands are executed. Chat responses are advisory.</div>
      </aside>
    </div>
  </main>;
}

function EvidenceDisclosure({ ids, records, expandedEvidence, setExpandedEvidence }: { ids: string[]; records: Evidence[]; expandedEvidence: string | null; setExpandedEvidence: (id: string | null) => void }) {
  if (!ids.length) return <div className="evidence-none">No supporting records were available.</div>;
  const open = expandedEvidence === ids[0];
  return <div className="evidence-disclosure"><button className="evidence-toggle" onClick={() => setExpandedEvidence(open ? null : ids[0])}><FileText size={13} /> {ids.length} evidence record{ids.length === 1 ? "" : "s"}<ChevronDown size={13} className={open ? "rotated" : ""} /></button>{open && <div className="evidence-records">{records.map((record) => <div className="evidence-record" key={record.evidence_id}><div><span>{record.source_file}{record.line_number ? `:${record.line_number}` : ""}</span><span>{record.timestamp ?? "Timestamp not present"}</span></div><code>{record.message}</code></div>)}</div>}</div>;
}

function ActionRow({ action, index, evidence, sources, outcome, onOutcome, expandedEvidence, setExpandedEvidence }: { action: Action; index: number; evidence: Evidence[]; sources: Analysis["sources"]; outcome?: string; onOutcome: (outcome: "resolved" | "partially_resolved" | "unsuccessful" | "inconclusive") => void; expandedEvidence: string | null; setExpandedEvidence: (id: string | null) => void }) {
  return <article className="action-row"><div className="action-index">{String(index + 1).padStart(2, "0")}</div><div className="action-main"><div className="action-title-line"><h3>{action.title}</h3><div className="action-badges"><span className="score">{Math.round(action.score * 100)} heuristic</span><span className={`priority ${action.priority}`}>{action.priority} priority</span><span className="risk"><ShieldCheck size={12} /> {action.risk_category.replaceAll("_", " ")}</span></div></div><p>{action.description}</p><div className="action-reason"><b>Why:</b> {action.reason}</div><p className="action-detail"><b>Score factors</b> {Object.entries(action.score_factors).map(([name, value]) => `${name.replaceAll("_", " ")} ${Math.round(value * 100)}%`).join(" · ")}</p>{action.prerequisites.length > 0 && <p className="action-detail"><b>Prerequisites</b> {action.prerequisites.join(" · ")}</p>}{action.expected_observations.length > 0 && <p className="action-detail"><b>Look for</b> {action.expected_observations.join(" · ")}</p>}<p className="action-detail"><b>Then</b> {action.suggested_follow_up}</p><EvidenceDisclosure ids={action.evidence_ids} records={evidence} expandedEvidence={expandedEvidence} setExpandedEvidence={setExpandedEvidence} />{sources.length > 0 && <div className="source-list">{sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" key={source.source_id}>{source.title} <ArrowUpRight size={12} /><span>{source.publisher}</span></a>)}</div>}<div className="outcome-row"><span>{outcome ? `Reported: ${outcome.replaceAll("_", " ")}` : "Record an outcome"}</span><div><button disabled={!!outcome} onClick={() => onOutcome("resolved")}><Check size={13} /> Resolved</button><button disabled={!!outcome} onClick={() => onOutcome("partially_resolved")}>Partially resolved</button><button disabled={!!outcome} onClick={() => onOutcome("unsuccessful")}>Unsuccessful</button><button disabled={!!outcome} onClick={() => onOutcome("inconclusive")}>Inconclusive</button></div></div></div></article>;
}