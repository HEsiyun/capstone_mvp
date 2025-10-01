import React, { useState } from "react";

export default function ParksPrototypeApp() {
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8000");
  const [text, setText] = useState("Which playgrounds are overdue for inspection in Stanley Park?");
  const [imageFile, setImageFile] = useState(null);
  const [imageUri, setImageUri] = useState("");
  const [activeTab, setActiveTab] = useState("agent"); // "agent" | "nlu"
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState(null);
  const [error, setError] = useState("");

  const handleImage = (file) => {
    if (!file) {
      setImageFile(null);
      setImageUri("");
      return;
    }
    setImageFile(file);
    const url = URL.createObjectURL(file);
    setImageUri(url);
  };

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
      .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold mt-4 mb-2">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-4 mb-2">$1</h1>')
      .replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>")
      .replace(/^- (.*$)/gim, "<li>$1</li>")
      .replace(/^(\d+)\. (.*$)/gim, "<li>$1. $2</li>")
      .replace(/\n\n/g, "<br/><br/>");
    return <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: html }} />;
  }

  function TablesView({ tables }) {
    if (!tables || !tables.length) return null;
    return (
      <div className="space-y-4 mt-4">
        {tables.map((t, idx) => (
          <div key={idx} className="border rounded-xl p-3 bg-white">
            <div className="text-sm font-semibold mb-2">{t.name || `table_${idx}`}</div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b">
                    {(t.columns || Object.keys((t.rows && t.rows[0]) || {})).map((c) => (
                      <th key={c} className="text-left py-1 pr-4 font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(t.rows || []).map((row, rIdx) => (
                    <tr key={rIdx} className="border-b last:border-b-0">
                      {((t.columns && t.columns.length ? t.columns : Object.keys(row))).map((c) => (
                        <td key={c} className="py-1 pr-4 whitespace-nowrap">{String(row[c])}</td>
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
      <div className="mt-4 text-sm">
        <div className="font-semibold mb-1">Citations</div>
        <ul className="list-disc ml-5 space-y-1">
          {citations.map((c, i) => (
            <li key={i}>
              {c.title || "source"} — <span className="text-gray-600">{c.source}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  function LogsView({ logs }) {
    if (!logs || !logs.length) return null;
    return (
      <div className="mt-4 text-xs text-gray-600">
        <div className="font-semibold mb-1">Logs</div>
        <div className="space-y-1">
          {logs.map((l, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded-full text-white ${l.ok ? "bg-green-600" : "bg-red-600"}`}>
                {l.ok ? "ok" : "err"}
              </span>
              <span className="font-mono">{l.tool}</span>
              <span>({l.elapsed_ms} ms)</span>
              <span className="text-gray-500">args: {Array.isArray(l.args_redacted) ? l.args_redacted.join(", ") : "-"}</span>
              {l.err && <span className="text-red-600">{l.err}</span>}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-start justify-center p-8">
      <div className="w-full max-w-5xl space-y-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Parks Prototype UI</h1>
          <div className="flex items-center gap-2">
            <span className="text-sm">Base URL</span>
            <input
              className="px-2 py-1 border rounded-lg text-sm w-72 bg-white"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
            />
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 space-y-3">
            <textarea
              className="w-full h-28 p-3 border rounded-xl focus:outline-none focus:ring bg-white"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="flex items-center gap-3">
              <label className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl cursor-pointer bg-white hover:bg-gray-50">
                <input type="file" accept="image/*" className="hidden" onChange={(e) => handleImage(e.target.files[0])} />
                <span className="text-sm">+ Image (optional)</span>
              </label>
              {imageUri && (
                <div className="flex items-center gap-2">
                  <img src={imageUri} alt="preview" className="h-12 w-12 object-cover rounded-lg border" />
                  <button className="text-xs text-red-600" onClick={() => handleImage(null)}>remove</button>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 pt-1">
              <button
                className={`px-3 py-1.5 rounded-lg text-sm border ${activeTab === "agent" ? "bg-black text-white" : "bg-white"}`}
                onClick={() => setActiveTab("agent")}
              >Agent /agent/answer</button>
              <button
                className={`px-3 py-1.5 rounded-lg text-sm border ${activeTab === "nlu" ? "bg-black text-white" : "bg-white"}`}
                onClick={() => setActiveTab("nlu")}
              >NLU /nlu/parse</button>
              <button
                className="ml-auto px-4 py-1.5 rounded-lg text-sm bg-green-600 text-white disabled:opacity-60"
                disabled={loading}
                onClick={() => callEndpoint(activeTab === "agent" ? "/agent/answer" : "/nlu/parse")}
              >{loading ? "Running..." : "Send"}</button>
            </div>

            {error && <div className="text-sm text-red-600">{error}</div>}
          </div>

          <aside className="md:col-span-1 space-y-3">
            <div className="p-3 bg-white border rounded-xl">
              <div className="text-sm font-semibold mb-2">Tips</div>
              <ul className="text-sm list-disc ml-5 space-y-1">
                <li>Try: <em>Which playgrounds are overdue for inspection in Stanley Park?</em></li>
                <li>Try: <em>What steps are required to service a slide?</em></li>
                <li>Try: <em>Check this photo—does the bench need repair?</em> + upload an image(A1004)</li>
              </ul>
            </div>
          </aside>
        </div>

        <section className="bg-white border rounded-xl p-4">
          <div className="text-sm font-semibold mb-2">Response</div>
          {!resp && <div className="text-sm text-gray-500">No response yet.</div>}
          {resp && (
            <div className="space-y-4">
              {resp.answer_md && <div>{renderMarkdown(resp.answer_md)}</div>}
              {activeTab === "agent" && <TablesView tables={resp.tables} />}
              {activeTab === "agent" && <CitationsView citations={resp.citations} />}
              {activeTab === "agent" && <LogsView logs={resp.logs} />}
              {activeTab === "nlu" && (
                <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-x-auto border">
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