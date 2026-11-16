import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Download } from "lucide-react";
import Sidebar from "./Sidebar";
import HealthBanner from "./HealthBanner";
import CostSummaryCards from "./CostSummaryCards";
import AttributionPanel from "./AttributionPanel";
import TrendsPanel from "./TrendsPanel";
import CostAllocationChart from "./CostAllocationChart";
import WorkloadTable from "./WorkloadTable";
import AnomalyTable from "./AnomalyTable";
import ForecastChart from "./ForecastChart";
import RecommendationsTable from "./RecommendationsTable";
import LivePanel from "./LivePanel";
import KpiPanel from "./KpiPanel";
import SettingsView from "./SettingsView";
import { API_BASE, getJSON } from "../api";

const TITLES = {
  home: ["Overview", "Visibility → Intelligence → Action, on one screen"],
  live: ["Live Cluster", "What is running right now and whether it is wasting money"],
  allocation: ["Cost Allocation (O1)", "Who is spending how much — by team, namespace and workload"],
  trends: ["Spend Trends (O2 reference)", "Daily spend, moving average, week-over-week change"],
  anomalies: ["Anomalies (O3)", "Days where a workload cost much more than its own recent normal"],
  forecast: ["Forecast (O3)", "Next 14 days of cost per workload"],
  recommendations: ["Savings (O4)", "Idle, right-size and commitment recommendations with ₹/$ impact"],
  evaluation: ["Evaluation (KPIs)", "Reference vs our method on identical data"],
  settings: ["Settings", ""],
};

export default function Dashboard() {
  // Tab lives in the URL hash so demo links work, e.g. http://localhost:5173/#live
  const [activeTab, setActiveTabState] = useState(() => {
    const h = window.location.hash.replace("#", "");
    return TITLES[h] ? h : "home";
  });
  const setActiveTab = (t) => {
    setActiveTabState(t);
    window.history.replaceState(null, "", `#${t}`);
  };
  const [currency, setCurrency] = useState(() => {
    try {
      return localStorage.getItem("finops_currency") || "INR";
    } catch {
      return "INR";
    }
  });

  const [health, setHealth] = useState(null);
  const [costs, setCosts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    document.documentElement.classList.add("dark");
    document.documentElement.style.colorScheme = "dark";
  }, []);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [h, c, s, a, f, r] = await Promise.all([
        getJSON("/health"),
        getJSON("/costs"),
        getJSON("/costs/summary"),
        getJSON("/anomalies"),
        getJSON("/forecast"),
        getJSON("/recommendations"),
      ]);
      setHealth(h);
      setCosts(c);
      setSummary(s);
      setAnomalies(a);
      setForecast(f);
      setRecommendations(r);
      setLastUpdated(new Date());
      setRefreshKey((k) => k + 1);
      setError(null);
    } catch (err) {
      console.error(err);
      setError(`Cannot reach the backend at ${API_BASE}. Start it with ./start.sh`);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + auto-refresh every 60 s (picks up new data from live auto-sync)
  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 60000);
    return () => clearInterval(t);
  }, [fetchAll]);

  // The last 30 days are plenty for the per-workload charts
  const recentCosts = (() => {
    if (!costs.length) return costs;
    const dates = [...new Set(costs.map((c) => c.date))].sort();
    const cutoff = dates[Math.max(dates.length - 30, 0)];
    return costs.filter((c) => c.date >= cutoff);
  })();

  const [title, subtitle] = TITLES[activeTab] || TITLES.home;

  return (
    <div className="flex h-screen w-screen overflow-hidden dark bg-[#121214] text-white font-sans antialiased">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} anomalyCount={anomalies.length} />

      <div className="flex-1 flex flex-col min-w-0 h-full overflow-y-auto">
        <div className="h-12 border-b border-[#262730] px-6 flex items-center justify-between flex-shrink-0 bg-[#101012]">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold">FinOps · CLOUD-04</span>
            <span>/</span>
            <span className="font-bold text-white">{title}</span>
          </div>
          <div className="flex items-center gap-2">
            {lastUpdated && <span className="text-[11px] text-slate-500 hidden sm:inline">Updated {lastUpdated.toLocaleTimeString()}</span>}
            <a
              href={`${API_BASE}/export/focus.csv`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#1a1a1e] border border-[#28282e] text-xs font-semibold text-slate-200 hover:bg-[#222228]"
              title="Download all cost data in FinOps FOCUS format"
            >
              <Download className="w-3 h-3" /> FOCUS CSV
            </a>
            <button
              onClick={fetchAll}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#1a1a1e] border border-[#28282e] text-xs font-semibold text-slate-200 hover:bg-[#222228]"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin text-blue-500" : ""}`} /> Refresh
            </button>
          </div>
        </div>

        <div className="p-6 sm:px-8 space-y-6 flex-1 max-w-7xl w-full mx-auto">
          <div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">{title}</h1>
            {subtitle && <p className="text-xs mt-1 text-slate-400">{subtitle}</p>}
          </div>

          {error && (
            <div className="bg-rose-950/40 border border-rose-900 text-rose-300 rounded p-3 text-xs flex items-center justify-between">
              <span>{error}</span>
              <button onClick={fetchAll} className="underline font-bold">Retry</button>
            </div>
          )}

          {activeTab !== "settings" && <HealthBanner health={health} />}

          {activeTab === "home" && (
            <>
              <CostSummaryCards summary={summary} recommendations={recommendations} currency={currency} />
              <AttributionPanel key={`a${refreshKey}`} currency={currency} />
              <TrendsPanel key={`t${refreshKey}`} currency={currency} compact />
              <RecommendationsTable data={recommendations} currency={currency} />
              <AnomalyTable data={anomalies.slice(0, 5)} />
            </>
          )}

          {activeTab === "live" && <LivePanel currency={currency} />}

          {activeTab === "allocation" && (
            <div className="space-y-6">
              <AttributionPanel key={`a${refreshKey}`} currency={currency} />
              <CostAllocationChart data={recentCosts} isDark currency={currency} />
              <WorkloadTable costs={recentCosts} summary={summary} currency={currency} />
            </div>
          )}

          {activeTab === "trends" && <TrendsPanel key={`t${refreshKey}`} currency={currency} />}

          {activeTab === "anomalies" && (
            <div className="space-y-6">
              <AnomalyTable data={anomalies} />
              <CostAllocationChart data={recentCosts} isDark currency={currency} />
            </div>
          )}

          {activeTab === "forecast" && <ForecastChart costData={recentCosts} forecastData={forecast} isDark />}

          {activeTab === "recommendations" && <RecommendationsTable data={recommendations} currency={currency} />}

          {activeTab === "evaluation" && <KpiPanel key={`k${refreshKey}`} />}

          {activeTab === "settings" && <SettingsView currency={currency} setCurrency={setCurrency} />}
        </div>
      </div>
    </div>
  );
}
