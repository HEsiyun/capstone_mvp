import React, { useState } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export default function App() {
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8000");
  const [activeTab, setActiveTab] = useState("agent");
  const [text, setText] = useState("");
  const [imageUri, setImageUri] = useState("");
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState(null);
  const [error, setError] = useState("");

  // Organized presets by category
  const presetCategories = [
    {
      category: "💰 Cost Analysis",
      queries: [
        "Which park had the highest total mowing labor cost in March 2025?",
        "Show mowing cost trend from January to June 2025",
        "Compare mowing costs across all parks in March 2025",
        "When was the last mowing at Cambridge Park?",
      ]
    },
    {
      category: "📋 Procedures & Standards",
      queries: [
        "What are the mowing steps and safety requirements?",
        "What are the dimensions for U15 soccer?",
        "Show me baseball field requirements for U13",
        "What's the pitching distance for female softball U17?",
      ]
    },
    {
      category: "🖼️ Image Analysis",
      queries: [
        "Assess this field condition (upload image)",
        "Does this field need mowing? (upload image)",
        "Is this field suitable for soccer? (upload image)",
      ]
    }
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

  function ChartsView({ charts }) {
    if (!charts || !charts.length) return null;

    return (
      <div style={{ marginTop: 16 }}>
        {charts.map((chart, idx) => (
          <div key={idx} className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">
              {chart.title || `Chart ${idx + 1}`}
            </div>
            <div style={{ width: "100%", height: 400 }}>
              {renderChart(chart)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  function renderChart(chart) {
    const chartType = chart.type;
    if (chartType === "line") return renderLineChart(chart);
    if (chartType === "bar") return renderBarChart(chart);
    if (chartType === "bar_stacked") return renderStackedBarChart(chart);
    if (chartType === "timeline") return renderTimeline(chart);
    return <div className="muted">Unsupported chart type: {chartType}</div>;
  }

  function renderLineChart(chart) {
    const allXValues = [
      ...new Set(chart.series.flatMap((s) => s.data.map((d) => d.x))),
    ].sort((a, b) => a - b);

    const chartData = allXValues.map((xVal) => {
      const dataPoint = { [chart.x_axis.field]: xVal };
      chart.series.forEach((series) => {
        const point = series.data.find((d) => d.x === xVal);
        dataPoint[series.name] = point ? point.y : null;
      });
      return dataPoint;
    });

    const colors = ["#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1"];

    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey={chart.x_axis.field}
            label={{ value: chart.x_axis.label, position: "insideBottom", offset: -5 }}
          />
          <YAxis label={{ value: chart.y_axis.label, angle: -90, position: "insideLeft" }} />
          <Tooltip />
          {chart.legend && <Legend />}
          {chart.series.map((series, idx) => (
            <Line
              key={series.name}
              type="monotone"
              dataKey={series.name}
              stroke={colors[idx % colors.length]}
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  function renderBarChart(chart) {
    const chartData = chart.series[0].data.map((d) => ({
      [chart.x_axis.field]: d.x,
      [chart.y_axis.field]: d.y,
    }));

    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey={chart.x_axis.field}
            label={{ value: chart.x_axis.label, position: "insideBottom", offset: -5 }}
            angle={-15}
            textAnchor="end"
            height={80}
          />
          <YAxis label={{ value: chart.y_axis.label, angle: -90, position: "insideLeft" }} />
          <Tooltip />
          <Bar dataKey={chart.y_axis.field} fill={chart.color || "#4CAF50"} radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  function renderStackedBarChart(chart) {
    const allXValues = [...new Set(chart.series.flatMap((s) => s.data.map((d) => d.x)))];
    const chartData = allXValues.map((xVal) => {
      const dataPoint = { [chart.x_axis.field]: xVal };
      chart.series.forEach((series) => {
        const point = series.data.find((d) => d.x === xVal);
        dataPoint[series.name] = point ? point.y : 0;
      });
      return dataPoint;
    });

    const colors = ["#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1"];

    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey={chart.x_axis.field}
            label={{ value: chart.x_axis.label, position: "insideBottom", offset: -5 }}
            angle={-15}
            textAnchor="end"
            height={80}
          />
          <YAxis label={{ value: chart.y_axis.label, angle: -90, position: "insideLeft" }} />
          <Tooltip />
          {chart.legend && <Legend />}
          {chart.series.map((series, idx) => (
            <Bar key={series.name} dataKey={series.name} stackId="a" fill={colors[idx % colors.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  function renderTimeline(chart) {
    const sortedData = [...chart.data].sort((a, b) => {
      if (chart.sort_order === "asc") return new Date(a.date) - new Date(b.date);
      return new Date(b.date) - new Date(a.date);
    });

    return (
      <div style={{ padding: "20px 0" }}>
        {sortedData.map((item, idx) => (
          <div
            key={idx}
            style={{
              display: "flex",
              gap: 16,
              marginBottom: 24,
              paddingBottom: 24,
              borderBottom: idx < sortedData.length - 1 ? "1px solid #e0e0e0" : "none",
            }}
          >
            <div style={{ fontSize: 24, flexShrink: 0 }}>📅</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>{item.park}</div>
              <div style={{ color: "#666", fontSize: 14, marginBottom: 8 }}>
                {new Date(item.date).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <span
                  style={{
                    display: "inline-block",
                    padding: "4px 8px",
                    background: "#e3f2fd",
                    color: "#1976d2",
                    borderRadius: 4,
                    fontSize: 12,
                    fontWeight: 500,
                  }}
                >
                  {item.sessions} session{item.sessions !== 1 ? "s" : ""}
                </span>
                <span
                  style={{
                    display: "inline-block",
                    padding: "4px 8px",
                    background: "#e3f2fd",
                    color: "#1976d2",
                    borderRadius: 4,
                    fontSize: 12,
                    fontWeight: 500,
                  }}
                >
                  ${item.cost?.toFixed(2) || "0.00"}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  function TablesView({ tables }) {
    if (!tables || !tables.length) return null;
    return (
      <div style={{ marginTop: 16 }}>
        {tables.map((t, idx) => (
          <div key={idx} className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">{t.name || `table_${idx}`}</div>
            <div className="table-wrap">
              <table className="grid-table">
                <thead>
                  <tr>
                    {(t.columns || Object.keys((t.rows && t.rows[0]) || {})).map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(t.rows || []).map((row, rIdx) => (
                    <tr key={rIdx}>
                      {(t.columns && t.columns.length ? t.columns : Object.keys(row)).map((c) => (
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
              <span className={`pill ${l.ok ? "ok" : "err"}`}>{l.ok ? "ok" : "err"}</span>
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
          <h1>Parks Maintenance Intelligence System</h1>
          <div className="row">
            <span className="muted small">API Endpoint</span>
            <input
              className="input"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
            />
          </div>
        </header>

        <div className="grid">
          <div className="col-main">
            <div className="card">
              {/* Category-based presets */}
              {presetCategories.map((cat, catIdx) => (
                <div key={catIdx} style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#64748b" }}>
                    {cat.category}
                  </div>
                  <div className="row wrap gap">
                    {cat.queries.map((query, qIdx) => (
                      <button
                        key={qIdx}
                        className="btn ghost"
                        onClick={() => {
                          setText(query.replace(" (upload image)", ""));
                          if (query.includes("upload image") && !imageUri) {
                            alert("💡 Don't forget to upload an image for this query!");
                          }
                        }}
                        style={{ fontSize: 12 }}
                      >
                        {query.length > 40 ? query.substring(0, 37) + "..." : query}
                      </button>
                    ))}
                  </div>
                </div>
              ))}

              <textarea
                className="textarea"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type your question or select a preset above..."
              />

              <div className="row gap">
                <label className="btn file" style={{ marginRight: 8 }}>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f) {
                        setImageUri("");
                        return;
                      }
                      const url = URL.createObjectURL(f);
                      setImageUri(url);
                    }}
                  />
                  📷 Upload Image
                </label>
                {imageUri && (
                  <>
                    <img src={imageUri} alt="preview" className="thumb" style={{ maxHeight: 60 }} />
                    <button
                      className="btn ghost"
                      onClick={() => setImageUri("")}
                      style={{ padding: "4px 8px", fontSize: 12 }}
                    >
                      ✕
                    </button>
                  </>
                )}

                <div className="spacer" />

                <div className="tabs">
                  <button
                    className={`tab ${activeTab === "agent" ? "active" : ""}`}
                    onClick={() => setActiveTab("agent")}
                  >
                    Agent Answer
                  </button>
                  <button
                    className={`tab ${activeTab === "nlu" ? "active" : ""}`}
                    onClick={() => setActiveTab("nlu")}
                  >
                    NLU Parse
                  </button>
                </div>

                <button
                  className="btn primary"
                  disabled={loading}
                  onClick={() =>
                    callEndpoint(activeTab === "agent" ? "/agent/answer" : "/nlu/parse")
                  }
                >
                  {loading ? "⏳ Processing..." : "🚀 Send"}
                </button>
              </div>

              {error && <div className="error">❌ {error}</div>}
            </div>
          </div>

          <aside className="col-side">
            <div className="card">
              <div className="label">✨ System Capabilities</div>
              
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                  💰 Cost Analysis
                </div>
                <ul className="bullets" style={{ fontSize: 13 }}>
                  <li>Highest cost by park/month</li>
                  <li>Cost trends over time</li>
                  <li>Park comparisons</li>
                  <li>Last activity tracking</li>
                </ul>
              </div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                  📋 Standards & Procedures
                </div>
                <ul className="bullets" style={{ fontSize: 13 }}>
                  <li>Mowing SOPs and safety</li>
                  <li>Field dimensions (all sports)</li>
                  <li>Age group requirements</li>
                  <li>Equipment specifications</li>
                </ul>
              </div>

              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                  🖼️ Image Analysis (VLM)
                </div>
                <ul className="bullets" style={{ fontSize: 13 }}>
                  <li>Field condition assessment</li>
                  <li>Maintenance needs detection</li>
                  <li>Turf health evaluation</li>
                  <li>AI-powered recommendations</li>
                </ul>
              </div>

              <div style={{ marginTop: 16, padding: 12, background: "#f8f9fc", borderRadius: 8, fontSize: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>💡 Tips</div>
                <div style={{ color: "#64748b", lineHeight: 1.5 }}>
                  • Upload images for visual analysis<br/>
                  • Ask about any sport or age group<br/>
                  • Combine data queries with standards
                </div>
              </div>
            </div>
          </aside>
        </div>

        <section className="card">
          <div className="label">Response</div>
          {!resp && <div className="muted">No response yet. Try a query above!</div>}
          {resp && (
            <div className="stack">
              {resp.answer_md && <div>{renderMarkdown(resp.answer_md)}</div>}
              {activeTab === "agent" && <ChartsView charts={resp.charts} />}
              {activeTab === "agent" && <TablesView tables={resp.tables} />}
              {activeTab === "agent" && <CitationsView citations={resp.citations} />}
              {activeTab === "agent" && <LogsView logs={resp.logs} />}

              {activeTab === "nlu" && (
                <div className="stack">
                  <div className="card">
                    <div className="label">Intent</div>
                    <pre className="json">{JSON.stringify(resp.intent || resp.intent?.intent, null, 2)}</pre>
                  </div>
                  <div className="card">
                    <div className="label">Slots</div>
                    <pre className="json">{JSON.stringify(resp.slots || resp?.slots, null, 2)}</pre>
                  </div>
                  <div className="card">
                    <div className="label">Raw</div>
                    <pre className="json">{JSON.stringify(resp, null, 2)}</pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}