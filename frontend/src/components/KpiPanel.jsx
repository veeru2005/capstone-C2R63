import { useEffect, useState } from "react";
import { FlaskConical, CheckCircle2, XCircle } from "lucide-react";
import { getJSON } from "../api";

// Evaluation: O2 reference vs O3/O4 candidate on identical data (CLOUD-04 AC-4).
export default function KpiPanel() {
  const [k, setK] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    getJSON("/kpis").then(setK).catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="text-xs text-slate-400">No KPI report yet — run the pipeline. ({err})</div>;
  if (!k) return null;
  const rec = k.attribution_reconciliation || {};

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-purple-400" /> Evaluation — O2 reference vs our method
        </h2>
        <p className="text-xs text-slate-400">
          Same data, same settings for both (CLOUD-04 AC-4). Measured {new Date(k.measured_at).toLocaleString()}.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {Object.entries(k.kpis).map(([name, v]) => {
          const pp = v.unit === "%";
          const better = pp ? v["O3-candidate"] >= v["O2-reference"] + 3 : null;
          return (
            <div key={name} className="bg-[#1a1a1e] border border-[#28282e] rounded-md p-4 space-y-3">
              <div className="text-xs font-bold text-white">{name}</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded bg-[#16171d] p-2">
                  <div className="text-[10px] uppercase text-slate-400 font-bold">O2 reference</div>
                  <div className="text-xl font-bold text-slate-200">
                    {v["O2-reference"]}
                    <span className="text-xs text-slate-400"> {v.unit}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">{v["O2-method"]}</div>
                </div>
                <div className="rounded bg-blue-950/40 border border-blue-900 p-2">
                  <div className="text-[10px] uppercase text-blue-300 font-bold">Our method</div>
                  <div className="text-xl font-bold text-white">
                    {v["O3-candidate"]}
                    <span className="text-xs text-slate-400"> {v.unit}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">{v["O3-method"]}</div>
                </div>
              </div>
              {better !== null ? (
                <div className={`text-xs flex items-center gap-1.5 ${better ? "text-emerald-400" : "text-amber-300"}`}>
                  {better ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                  {v.delta_pp >= 0 ? "+" : ""}
                  {v.delta_pp} percentage points (target ≥ +3)
                </div>
              ) : (
                <div className="text-[11px] text-slate-400">{v.note}</div>
              )}
              {v.candidate_detail && (
                <div className="text-[11px] text-slate-400">
                  Reference: {v.reference_detail.tp} correct / {v.reference_detail.fp} false alarms / {v.reference_detail.fn} missed
                  <br />
                  Ours: {v.candidate_detail.tp} correct / {v.candidate_detail.fp} false alarms / {v.candidate_detail.fn} missed
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className={`text-xs rounded border p-3 ${rec.reconciled ? "border-emerald-900 text-emerald-300" : "border-rose-900 text-rose-300"}`}>
        Attribution check: team, namespace and workload views all add up to the same cluster total
        (max difference {rec.max_abs_diff} USD) → {rec.reconciled ? "PASS" : "FAIL"}
      </div>
    </div>
  );
}
