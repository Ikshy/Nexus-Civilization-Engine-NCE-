// InfoWarPanel.tsx
import { useInformation } from "../hooks/useApi";

export default function InfoWarPanel() {
  const { data: info } = useInformation();

  const polarization: Record<string, number> = info?.polarization ?? {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ["Total Rumors", info?.total_rumors ?? "—", "text-nce-yellow"],
          ["News Articles", info?.total_articles ?? "—", "text-nce-accent"],
          ["Active Broadcasts", info?.active_broadcasts ?? "—", "text-nce-green"],
          ["Echo Chambers", info?.echo_chambers ?? "—", info?.echo_chambers > 2 ? "text-nce-red" : "text-gray-300"],
        ].map(([label, value, color]) => (
          <div key={label as string} className="panel">
            <div className="text-xs text-gray-500 mb-1">{label}</div>
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Polarization */}
      <div className="panel">
        <div className="panel-title">Belief Polarization by Topic</div>
        <div className="space-y-3">
          {Object.entries(polarization).length === 0 && (
            <div className="text-gray-500 text-sm">No belief data yet.</div>
          )}
          {Object.entries(polarization).map(([topic, value]) => (
            <div key={topic}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-400">{topic.replace(/_/g, " ")}</span>
                <span className={value > 0.5 ? "text-nce-red" : value > 0.3 ? "text-nce-yellow" : "text-nce-green"}>
                  {(value * 100).toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-nce-border rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${value > 0.5 ? "bg-nce-red" : value > 0.3 ? "bg-nce-yellow" : "bg-nce-green"}`}
                  style={{ width: `${Math.min(100, value * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Most eroded agents */}
      <div className="panel">
        <div className="panel-title">Most Trust-Eroded Agents</div>
        {(info?.most_eroded_agents ?? []).length === 0 ? (
          <div className="text-gray-500 text-sm">No erosion data yet.</div>
        ) : (
          <div className="space-y-2">
            {(info.most_eroded_agents ?? []).map(([agentId, erosion]: [string, number]) => (
              <div key={agentId} className="flex justify-between text-xs">
                <span className="text-nce-accent">{agentId}</span>
                <span className="text-nce-red">−{erosion.toFixed(2)} trust</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active cascades */}
      <div className="panel">
        <div className="panel-title">Information Cascades</div>
        <div className="flex items-center gap-4 text-sm">
          <div>
            <span className="text-gray-500">Active: </span>
            <span className="text-nce-green font-bold">{info?.active_cascades ?? 0}</span>
          </div>
        </div>
        <div className="mt-3 text-xs text-gray-500">
          Information cascades track how broadcasts spread virally through the trust network,
          wave by wave from the originating agent.
        </div>
      </div>
    </div>
  );
}
