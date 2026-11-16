import { Database, Radio, AlertTriangle } from "lucide-react";

// Tells the viewer *where the numbers come from* and whether they are fresh.
export default function HealthBanner({ health }) {
  if (!health) return null;
  if (health.status === "no-data") {
    return (
      <div className="rounded border border-amber-700 bg-amber-950/40 p-3 text-xs text-amber-300">
        No data yet. Run <code className="font-mono">./start.sh</code> (demo) or{" "}
        <code className="font-mono">./start.sh live</code>.
      </div>
    );
  }
  const live = health.data_source === "opencost";
  const degraded = health.status === "degraded";
  return (
    <div
      className={`rounded border p-3 text-xs flex flex-wrap items-center gap-x-4 gap-y-1 ${
        degraded ? "border-amber-700 bg-amber-950/40 text-amber-200" : "border-[#28282e] bg-[#16171d] text-slate-300"
      }`}
    >
      <span className="flex items-center gap-1.5 font-semibold">
        {live ? <Radio className="w-3.5 h-3.5 text-emerald-400" /> : <Database className="w-3.5 h-3.5 text-blue-400" />}
        {live ? "LIVE — OpenCost on Kubernetes" : "SANDBOX — simulated 90-day cluster history (OpenCost format)"}
      </span>
      <span>
        Data: {health.data_start} → {health.data_end}
      </span>
      {health.last_successful_ingest && <span>Last sync: {new Date(health.last_successful_ingest).toLocaleString()}</span>}
      {degraded && (
        <span className="flex items-center gap-1 font-semibold">
          <AlertTriangle className="w-3.5 h-3.5" /> Degraded: {health.reasons?.join("; ")} — showing last good data
        </span>
      )}
    </div>
  );
}
