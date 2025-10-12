import React, { useState } from "react";

export default function App() {
  // ---- Config ----
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8000");
  const [activeTab, setActiveTab] = useState("agent"); // "agent" | "nlu"

  // ---- Query State ----
  const [text, setText] = useState(
    "Which park had the highest total mowing labor cost in March 2025?"
  );
  const [imageUri, setImageUri] = useState("");

  // ---- UI State ----
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState(null);
  const [error, setError] = useState("");

  // ---- Only two presets ----
  const presets = [
    {
      label: "Mowing Cost (Mar 2025)",
      text: "Which park had the highest total mowing labor cost in March 2025?",
    },
    {
      label: "Mowing Steps & Safety",
      text: "What are the mowing steps and safety requirements?",
    },
  ];

  async function callEndpoint(path) {
    setLoading(true);
    setError("");
    setResp(null);
    try {
      const body = { text: text.trim() };
      if (imageUri) body.image_uri = imageUri;

      const r = await fetch(`${baseUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = await r.json();
      setResp(data);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  function renderMarkdown(md) {
    if (!md) return null;
    const html = md
      .replace(/^### (.*$)/gim, '<h3 class="md-h3">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 class="md-h2">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 class="md-h1">$1</h1>')
      .replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>")
      .replace(/^- (.*$)/gim, "<li>$1</li>")
      .replace(/^(\d+)\. (.*$)/gim, "<li>$1. $2</li>")
      .replace(/\n\n/g, "<br/><br/>");
    return <div className="prose" dangerouslySetInnerHTML={{ __html: html }} />;
  }

  function TablesView({ tables }) {
    if (!tables || !tables.length) return null;
    return (
      <div className="space-y">
        {tables.map((t, idx) => (
          <div key={idx} className="card">
            <div className="card-title">{t.name || `table_${idx}`}</div>
            <div className="table-wrap">
              <table className="grid-table">
                <thead>
                  <tr>
                    {(t.columns || Object.keys((t.rows && t.rows[0]) || {})).map(
                      (c) => (
                        <th key={c}>{c}</th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {(t.rows || []).map((row, rIdx) => (
                    <tr key={rIdx}>
                      {(
                        t.columns && t.columns.length ? t.columns : Object.keys(row)
                      ).map((c) => (
                        <td key={c}>{String(row[c])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    );
  }

  function CitationsView({ citations }) {
    if (!citations || !citations.length) return null;
    return (
      <div className="mt">
        <div className="label">Citations</div>
        <ul className="bullets">
          {citations.map((c, i) => (
            <li key={i}>
              {c.title || "source"} — <span className="muted">{c.source}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  function LogsView({ logs }) {
    if (!logs || !logs.length) return null;
    return (
      <div className="mt">
        <div className="label">Logs</div>
        <div className="logs">
          {logs.map((l, i) => (
            <div key={i} className="log-row">
              <span className={`pill ${l.ok ? "ok" : "err"}`}>
                {l.ok ? "ok" : "err"}
              </span>
              <span className="mono">{l.tool}</span>
              <span>({l.elapsed_ms} ms)</span>
              <span className="muted">
                args: {Array.isArray(l.args_redacted) ? l.args_redacted.join(", ") : "-"}
              </span>
              {l.err && <span className="err-text">{l.err}</span>}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="shell">
        <header className="header">
          <h1>Parks Prototype UI</h1>
          <div className="row">
            <span className="muted small">Base URL</span>
            <input
              className="input"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
            />
          </div>
        </header>

        <div className="grid">
          {/* Left: query + controls */}
          <div className="col-main">
            <div className="card">
              <div className="row wrap gap">
                {presets.map((p) => (
                  <button
                    key={p.label}
                    className="btn ghost"
                    onClick={() => setText(p.text)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              <textarea
                className="textarea"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />

              <div className="row gap">
                <div className="spacer" />

                <div className="tabs">
                  <button
                    className={`tab ${activeTab === "agent" ? "active" : ""}`}
                    onClick={() => setActiveTab("agent")}
                  >
                    Agent /agent/answer
                  </button>
                  <button
                    className={`tab ${activeTab === "nlu" ? "active" : ""}`}
                    onClick={() => setActiveTab("nlu")}
                  >
                    NLU /nlu/parse
                  </button>
                </div>

                <button
                  className="btn primary"
                  disabled={loading}
                  onClick={() =>
                    callEndpoint(activeTab === "agent" ? "/agent/answer" : "/nlu/parse")
                  }
                >
                  {loading ? "Running..." : "Send"}
                </button>
              </div>

              {error && <div className="error">{error}</div>}
            </div>
          </div>

          {/* Right: tips */}
          <aside className="col-side">
            <div className="card">
              <div className="label">Try these</div>
              <ul className="bullets">
                <li>
                  <em>Which park had the highest total mowing labor cost in March 2025?</em>
                </li>
                <li>
                  <em>What are the mowing steps and safety requirements?</em>
                </li>
              </ul>
            </div>
          </aside>
        </div>

        {/* Response */}
        <section className="card">
          <div className="label">Response</div>
          {!resp && <div className="muted">No response yet.</div>}
          {resp && (
            <div className="stack">
              {resp.answer_md && <div>{renderMarkdown(resp.answer_md)}</div>}
              {activeTab === "agent" && <TablesView tables={resp.tables} />}
              {activeTab === "agent" && <CitationsView citations={resp.citations} />}
              {activeTab === "agent" && <LogsView logs={resp.logs} />}
              {activeTab === "nlu" && (
                <pre className="json">
                  {JSON.stringify(resp, null, 2)}
                </pre>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}