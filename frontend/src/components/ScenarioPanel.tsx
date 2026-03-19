// ScenarioPanel.tsx
import { useState } from "react";
import { useScenarios, useAvailableScenarios, injectScenario } from "../hooks/useApi";

export function ScenarioPanel() {
  const { data: status, mutate } = useScenarios();
  const { data: available } = useAvailableScenarios();
  const [selected, setSelected] = useState("");
  const [severity, setSeverity] = useState(0.7);
  const [loading, setLoading] = useState(false);

  const handleInject = async () => {
    if (!selected) return;
    setLoading(true);
    try {
      await injectScenario({ scenario_type: selected, severity });
      await mutate();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Inject panel */}
      <div className="panel space-y-4">
        <div className="panel-title">Inject Scenario</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Scenario Type</label>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full bg-nce-dark border border-nce-border rounded px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-nce-accent"
            >
              <option value="">Select scenario...</option>
              {(available?.scenarios ?? []).map((s: { type: string; description: string }) => (
                <option key={s.type} value={s.type}>{s.type.replace(/_/g, " ").toUpperCase()}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Severity: {(severity * 100).toFixed(0)}%</label>
            <input
              type="range"
              min={0.1}
              max={1.0}
              step={0.05}
              value={severity}
              onChange={(e) => setSeverity(Number(e.target.value))}
              className="w-full accent-nce-red mt-2"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={handleInject}
              disabled={!selected || loading}
              className="btn-danger w-full disabled:opacity-40"
            >
              ⚠ Inject Scenario
            </button>
          </div>
        </div>

        {selected && (
          <div className="text-xs text-gray-500 border border-nce-border/50 rounded p-2">
            {(available?.scenarios ?? []).find((s: { type: string; description: string }) => s.type === selected)?.description}
          </div>
        )}
      </div>

      {/* Active scenarios */}
      <div className="panel">
        <div className="panel-title">Active Scenarios ({status?.active?.length ?? 0})</div>
        {status?.active?.length === 0 && <div className="text-gray-500 text-sm">No active scenarios</div>}
        <div className="space-y-3">
          {(status?.active ?? []).map((s: {
            id: string; name: string; type: string; severity: number; ticks_remaining: number;
          }) => (
            <div key={s.id} className="flex items-center justify-between border border-nce-red/30 rounded p-3">
              <div>
                <div className="font-semibold text-sm text-nce-red">{s.name}</div>
                <div className="text-xs text-gray-500">{s.type} — {(s.severity * 100).toFixed(0)}% severity</div>
              </div>
              <div className="text-right">
                <div className="badge-red badge">{s.ticks_remaining} ticks left</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Completed scenarios */}
      {status?.completed?.length > 0 && (
        <div className="panel">
          <div className="panel-title">Completed Scenarios</div>
          <div className="space-y-2">
            {(status.completed ?? []).map((s: { id: string; name: string; status: string }) => (
              <div key={s.id} className="flex justify-between text-xs">
                <span className="text-gray-300">{s.name}</span>
                <span className="badge-green badge">{s.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ScenarioPanel;
