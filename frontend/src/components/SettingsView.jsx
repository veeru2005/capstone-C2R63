import { useEffect, useState } from "react";
import { ExternalLink, Check, Activity, Database, Radio, SlidersHorizontal, Palette } from "lucide-react";
import { CURRENCIES } from "../utils/currency";
import { API_BASE, getJSON } from "../api";

function Card({ icon: Icon, title, children }) {
  return (
    <div className="bg-[#1a1a1e] border border-[#28282e] rounded-md overflow-hidden">
      <div className="px-5 py-3 border-b border-[#28282e] flex items-center gap-2">
        <Icon className="w-4 h-4 text-blue-400" />
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="p-5 space-y-4">{children}</div>
    </div>
  );
}

function Row({ label, value, good }) {
  return (
    <div className="flex items-start justify-between gap-4 text-xs py-1.5 border-b border-[#232329] last:border-0">
      <span className="text-slate-400">{label}</span>
      <span className={`text-right font-semibold ${good === true ? "text-emerald-400" : good === false ? "text-amber-300" : "text-slate-100"}`}>{value}</span>
    </div>
  );
}

function Toggle({ on, onChange }) {
  return (
    <button
      onClick={() => onChange(!on)}
      role="switch"
      aria-checked={on}
      className={`w-10 h-5 rounded-full relative transition-colors flex-shrink-0 ${on ? "bg-blue-600" : "bg-[#34343d]"}`}
    >
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${on ? "left-5" : "left-0.5"}`} />
    </button>
  );
}

const LINKS = [
  ["Project repository (GitHub)", "https://github.com/veeru2005/capstone-C2R63"],
  ["API documentation (Swagger)", `${API_BASE || ""}/docs`],
  ["OpenCost documentation", "https://www.opencost.io/docs"],
  ["FinOps FOCUS specification", "https://focus.finops.org/"],
];

export default function SettingsView({ currency, setCurrency, autoRefresh, setAutoRefresh }) {
  const [selected, setSelected] = useState(currency || "INR");
  const [saved, setSaved] = useState(false);
  const [health, setHealth] = useState(null);
  const [live, setLive] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [apiOk, setApiOk] = useState(null);

  useEffect(() => {
    getJSON("/health").then((h) => { setHealth(h); setApiOk(true); }).catch(() => setApiOk(false));
    getJSON("/live?window=10m").then(setLive).catch(() => setLive(null));
    getJSON("/config").then(setCfg).catch(() => setCfg(null));
  }, []);

  const save = () => {
    setCurrency(selected);
    try { localStorage.setItem("finops_currency", selected); } catch { /* private mode */ }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const rate = CURRENCIES[selected]?.rate;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <div className="space-y-6">
        <Card icon={Palette} title="Display">
          <div>
            <label className="block text-xs font-semibold text-slate-200 mb-1">Currency</label>
            <p className="text-xs text-slate-400 mb-2">
              OpenCost reports cost in USD. Amounts are converted for display only
              {selected !== "USD" && rate ? ` (1 USD = ${rate} ${selected}).` : "."}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="w-full sm:w-64 bg-[#161619] border border-[#28282e] rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              >
                {Object.values(CURRENCIES).map((c) => (
                  <option key={c.code} value={c.code}>{c.code} ({c.symbol}) — {c.name}</option>
                ))}
              </select>
              <button
                onClick={save}
                className="px-4 py-2 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5"
              >
                {saved ? (<><Check className="w-3.5 h-3.5" /> Saved</>) : "Save"}
              </button>
            </div>
          </div>
          <div className="flex items-center justify-between gap-4 pt-2 border-t border-[#232329]">
            <div>
              <div className="text-xs font-semibold text-slate-200">Auto-refresh dashboard</div>
              <p className="text-xs text-slate-400">Reload data every 60 seconds (useful in live mode).</p>
            </div>
            <Toggle on={autoRefresh} onChange={setAutoRefresh} />
          </div>
        </Card>

        <Card icon={Activity} title="About">
          <div>
            <div className="text-base font-bold text-white">FinOps Cloud-Cost Optimisation Dashboard</div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              KL University capstone AY 2026-27 · use case CLOUD-04 · Batch C2R-63. Splits Kubernetes cost by team,
              shows trends, flags cost spikes, forecasts the next 14 days and recommends safe savings, using OpenCost data.
            </p>
          </div>
          <div className="space-y-2 text-xs">
            {LINKS.map(([label, href]) => (
              <a key={label} href={href} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1.5">
                {label} <ExternalLink className="w-3 h-3" />
              </a>
            ))}
          </div>
        </Card>
      </div>

      <div className="space-y-6">
        <Card icon={Database} title="Data connection">
          <div>
            <Row label="Backend API" value={apiOk === null ? "checking…" : apiOk ? `connected · ${API_BASE || window.location.origin}` : "not reachable"} good={apiOk ?? undefined} />
            <Row label="Data source" value={!health ? "—" : health.data_source === "opencost" ? "LIVE — OpenCost" : health.data_source === "simulator" ? "SANDBOX — simulated 90 days" : health.data_source || "no data"} />
            <Row label="Data range" value={health?.data_start ? `${health.data_start} – ${health.data_end}` : "—"} />
            <Row label="Last successful sync" value={health?.last_successful_ingest ? new Date(health.last_successful_ingest).toLocaleString() : "—"} />
            <Row label="Status" value={health?.status === "ok" ? "OK" : health?.status === "degraded" ? `Degraded: ${health.reasons?.join("; ")}` : health?.status || "—"} good={health ? health.status === "ok" : undefined} />
          </div>
        </Card>

        <Card icon={Radio} title="Live cluster (OpenCost)">
          <div>
            <Row label="OpenCost URL" value={cfg?.opencost_url || live?.opencost_url || "—"} />
            <Row label="Connection" value={live ? (live.connected ? `connected · ${live.workloads.length} workloads` : "not connected") : "—"} good={live ? live.connected : undefined} />
            <Row label="Auto-sync from OpenCost" value={cfg ? (cfg.auto_sync_minutes > 0 ? `every ${cfg.auto_sync_minutes} min` : "off (demo mode)") : "—"} />
          </div>
          <p className="text-xs text-slate-500">Turn live mode on with <code className="text-slate-300">./start.sh live</code>.</p>
        </Card>

        <Card icon={SlidersHorizontal} title="Detection & savings rules">
          {cfg ? (
            <div>
              <Row label="Anomaly: compare with last" value={`${cfg.anomaly.window_days} days`} />
              <Row label="Anomaly: flag when z-score above" value={cfg.anomaly.z_threshold} />
              <Row label="IDLE when efficiency below" value={`${cfg.recommendations.idle_below_pct}%`} />
              <Row label="RIGHT-SIZE when efficiency below" value={`${cfg.recommendations.rightsize_below_pct}%`} />
              <Row label="Right-size target" value={`p95 usage × ${cfg.recommendations.rightsize_headroom}`} />
              <Row label="COMMITMENT after stable spend of" value={`${cfg.recommendations.commitment_min_days} days (≈${Math.round(cfg.recommendations.commitment_discount * 100)}% discount)`} />
              <Row label="Never marked as waste" value={cfg.system_namespaces.join(", ")} />
            </div>
          ) : (
            <p className="text-xs text-slate-400">Backend not reachable.</p>
          )}
          <p className="text-xs text-slate-500">Read-only here. Change them in <code className="text-slate-300">backend/finops/config.py</code> so every result stays reproducible.</p>
        </Card>
      </div>
    </div>
  );
}
