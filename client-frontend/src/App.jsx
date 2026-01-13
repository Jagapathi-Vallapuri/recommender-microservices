import React, { useEffect, useMemo, useState } from "react";

const DEFAULT_GATEWAY_URL = "http://localhost:9000";

function buildUrl(baseUrl, path, params) {
  const url = new URL(path, baseUrl);
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    url.searchParams.set(k, String(v));
  });
  return url.toString();
}

async function readErrorBody(res) {
  try {
    const data = await res.json();
    return typeof data === "string" ? data : JSON.stringify(data);
  } catch {
    try {
      return await res.text();
    } catch {
      return "";
    }
  }
}

function App() {
  const gatewayUrl = useMemo(
    () => (import.meta.env.VITE_GATEWAY_URL || DEFAULT_GATEWAY_URL).replace(/\/$/, ""),
    []
  );

  const [mode, setMode] = useState("auto");
  const [source, setSource] = useState("");
  const [destination, setDestination] = useState("");
  const [userId, setUserId] = useState("");
  const [topN, setTopN] = useState(10);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const fetchHealth = async () => {
      try {
        const res = await fetch(buildUrl(gatewayUrl, "/service-health", {}));
        if (!res.ok) {
          const body = await readErrorBody(res);
          throw new Error(`Health failed (${res.status}): ${body}`);
        }
        const data = await res.json();
        if (!cancelled) {
          setHealth(data);
          setHealthError("");
        }
      } catch (err) {
        if (!cancelled) {
          setHealth(null);
          setHealthError(err?.message || String(err));
        }
      }
    };

    fetchHealth();
    const t = setInterval(fetchHealth, 5000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [gatewayUrl]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);

    const src = source.trim();
    const dst = destination.trim();
    if (!src || !dst) {
      setError("Please provide both source and destination.");
      return;
    }

    const params = {
      source: src,
      destination: dst,
      top_n: topN,
    };
    if (userId.trim()) params.user_id = userId.trim();
    if (mode !== "auto") params.mode = mode;

    const url = buildUrl(gatewayUrl, "/recommend-route", params);

    setLoading(true);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const body = await readErrorBody(res);
        throw new Error(`Request failed (${res.status}): ${body}`);
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err?.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  const recommendations = Array.isArray(result?.recommendations) ? result.recommendations : [];

  return (
    <div className="container">
      <h1>Recommender Client</h1>
      <p className="subtle">Gateway: {gatewayUrl}</p>

      <div className="results" style={{ marginTop: "1rem" }}>
        <h2>Services Dashboard</h2>
        {healthError ? <div className="error">{healthError}</div> : null}
        {health ? (
          <div className="grid">
            {Object.entries(health).map(([service, status]) => (
              <div key={service} className={`card ${String(status).startsWith("healthy") ? "healthy" : "unhealthy"}`}>
                <h2>{service}</h2>
                <p>Status: {status}</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <form className="form" onSubmit={onSubmit}>
        <div className="row">
          <label>
            Mode
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="auto">Auto</option>
              <option value="air">Air</option>
              <option value="rail">Rail</option>
            </select>
          </label>

          <label>
            Top N
            <input
              type="number"
              min={1}
              max={50}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value || 10))}
            />
          </label>
        </div>

        <div className="row">
          <label>
            Source
            <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="BOS or HBR" />
          </label>
          <label>
            Destination
            <input value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="DEN or IVY" />
          </label>
        </div>

        <div className="row">
          <label className="wide">
            User ID (optional)
            <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="test-user" />
          </label>
        </div>

        <div className="row">
          <button className="button" type="submit" disabled={loading}>
            {loading ? "Loading…" : "Get Recommendations"}
          </button>
        </div>
      </form>

      {error ? <div className="error">{error}</div> : null}

      {result ? (
        <div className="results">
          <div className="meta">
            <div>Resolved mode: <b>{result.mode}</b></div>
            <div>Upstream: <b>{result.upstream}</b></div>
            <div>
              Route: <b>{result.source}</b> → <b>{result.destination}</b>
            </div>
          </div>

          <div className="grid">
            {recommendations.map((rec) => (
              <div key={rec.id} className="card">
                <h2>{rec.name}</h2>
                <p className="mono">{rec.id}</p>
                <p>
                  {rec.source} → {rec.destination}
                </p>
                <p className="subtle">
                  Dep: {rec.departure || "-"} | Arr: {rec.arrival || "-"}
                </p>
                <pre className="pre">{JSON.stringify(rec.meta || {}, null, 2)}</pre>
              </div>
            ))}
          </div>

          <details className="raw">
            <summary>Raw response</summary>
            <pre className="pre">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      ) : null}
    </div>
  );
}

export default App;
