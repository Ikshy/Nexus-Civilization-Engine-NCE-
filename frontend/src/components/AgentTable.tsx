import { useState } from "react";
import { useAgents, useAgent } from "../hooks/useApi";

export default function AgentTable() {
  const [filter, setFilter] = useState({ type: "", alive: true });
  const [selected, setSelected] = useState<string | null>(null);
  const params = `?alive_only=${filter.alive}${filter.type ? `&agent_type=${filter.type}` : ""}`;
  const { data: agentsData } = useAgents(params);
  const { data: agentDetail } = useAgent(selected);

  const TYPES = ["worker", "trader", "leader", "scientist", "builder", "spy",
    "farmer", "thief", "diplomat", "guard", "rebel", "mediator"];

  return (
    <div className="h-full flex gap-4">
      {/* Table */}
      <div className="flex-1 flex flex-col gap-3 min-w-0">
        {/* Filters */}
        <div className="flex gap-3 flex-wrap items-center">
          <select
            value={filter.type}
            onChange={(e) => setFilter((f) => ({ ...f, type: e.target.value }))}
            className="bg-nce-panel border border-nce-border rounded px-2 py-1 text-xs text-gray-300 focus:outline-none"
          >
            <option value="">All types</option>
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button
            onClick={() => setFilter((f) => ({ ...f, alive: !f.alive }))}
            className={`badge ${filter.alive ? "badge-green" : "bg-nce-border text-gray-400"} cursor-pointer`}
          >
            {filter.alive ? "Alive only" : "All agents"}
          </button>
          <span className="text-gray-500 text-xs ml-auto">{agentsData?.count ?? 0} agents</span>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-nce-border text-left">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 pr-3">Type</th>
                <th className="py-2 pr-3">Pos</th>
                <th className="py-2 pr-3">HP</th>
                <th className="py-2 pr-3">Energy</th>
                <th className="py-2 pr-3">Stress</th>
                <th className="py-2">Faction</th>
              </tr>
            </thead>
            <tbody>
              {(agentsData?.agents ?? []).map((a: {
                agent_id: string; type: string; position: { x: number; y: number };
                health: number; energy: number; stress: number; faction: string;
              }) => (
                <tr
                  key={a.agent_id}
                  onClick={() => setSelected(a.agent_id)}
                  className={`border-b border-nce-border/40 cursor-pointer hover:bg-nce-border/30 transition-colors ${
                    selected === a.agent_id ? "bg-nce-accent/10" : ""
                  }`}
                >
                  <td className="py-1.5 pr-3 text-nce-accent">{a.agent_id}</td>
                  <td className="py-1.5 pr-3 text-gray-300">{a.type}</td>
                  <td className="py-1.5 pr-3 text-gray-500">({a.position.x},{a.position.y})</td>
                  <td className="py-1.5 pr-3">
                    <span className={a.health < 30 ? "text-nce-red" : a.health < 60 ? "text-nce-yellow" : "text-nce-green"}>
                      {a.health.toFixed(0)}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 text-blue-400">{a.energy.toFixed(0)}</td>
                  <td className="py-1.5 pr-3">
                    <span className={a.stress > 70 ? "text-nce-red" : "text-gray-400"}>{a.stress.toFixed(0)}</span>
                  </td>
                  <td className="py-1.5 text-gray-500">{a.faction ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Agent Detail */}
      {agentDetail && (
        <div className="w-72 panel overflow-y-auto shrink-0 space-y-4">
          <div className="flex justify-between items-center">
            <span className="panel-title">{agentDetail.agent_id}</span>
            <button onClick={() => setSelected(null)} className="text-gray-500 hover:text-white text-lg">×</button>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Type / Faction</div>
            <div className="text-sm">
              <span className="badge-blue badge">{agentDetail.type}</span>
              {agentDetail.faction && <span className="badge-purple badge ml-2">{agentDetail.faction}</span>}
            </div>
          </div>

          {/* Vitals */}
          <div>
            <div className="text-xs text-gray-500 mb-2">Vitals</div>
            <div className="space-y-1">
              {Object.entries(agentDetail.vitals ?? {}).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-gray-400">{k}</span>
                  <span className="text-white">{typeof v === "number" ? (v as number).toFixed(1) : String(v)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Resources */}
          <div>
            <div className="text-xs text-gray-500 mb-2">Resources</div>
            <div className="space-y-1">
              {Object.entries(agentDetail.resources ?? {}).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-gray-400">{k}</span>
                  <span className="text-white">{typeof v === "number" ? (v as number).toFixed(1) : String(v)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Skills */}
          <div>
            <div className="text-xs text-gray-500 mb-2">Skills</div>
            <div className="space-y-1">
              {Object.entries(agentDetail.skills ?? {}).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-xs">
                  <span className="text-gray-400 w-20">{k}</span>
                  <div className="flex-1 bg-nce-border rounded-full h-1.5">
                    <div
                      className="bg-nce-accent h-1.5 rounded-full"
                      style={{ width: `${Math.min(100, (v as number) * 100)}%` }}
                    />
                  </div>
                  <span className="text-white w-8 text-right">{((v as number) * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Memory summary */}
          <div>
            <div className="text-xs text-gray-500 mb-2">Memory</div>
            <div className="space-y-1">
              {Object.entries(agentDetail.memory ?? {}).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-gray-400">{k}</span>
                  <span className="text-white">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
