import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import { useAnalytics, useMetricTrend, useLeaders, useClusters, useConflictZones } from "../hooks/useApi";

function StatCard({ label, value, unit = "", color = "text-white" }: {
  label: string; value: unknown; unit?: string; color?: string;
}) {
  return (
    <div className="panel flex flex-col">
      <span className="text-gray-500 text-xs mb-1">{label}</span>
      <span className={`text-xl font-bold ${color}`}>
        {typeof value === "number" ? value.toFixed(3) : value ?? "—"}
        {unit && <span className="text-sm text-gray-400 ml-1">{unit}</span>}
      </span>
    </div>
  );
}

function TrendChart({ metric, label, color }: { metric: string; label: string; color: string }) {
  const { data } = useMetricTrend(metric, 60);
  const chartData = (data?.values ?? []).map((v: number, i: number) => ({ i, value: v }));
  return (
    <div className="panel">
      <div className="panel-title">{label}</div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id={`grad-${metric}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="i" hide />
          <YAxis domain={[0, 1]} tick={{ fill: "#6b7280", fontSize: 10 }} width={30} />
          <Tooltip
            contentStyle={{ background: "#111827", border: "1px solid #1f2937", fontSize: 11 }}
            formatter={(v: number) => v.toFixed(3)}
          />
          <Area type="monotone" dataKey="value" stroke={color} fill={`url(#grad-${metric})`} dot={false} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function AnalyticsPanel() {
  const { data: analytics } = useAnalytics();
  const { data: leadersData } = useLeaders();
  const { data: clustersData } = useClusters();
  const { data: zonesData } = useConflictZones();

  const pop = analytics?.population ?? {};
  const net = analytics?.network ?? {};

  return (
    <div className="space-y-4">
      {/* Top stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <StatCard label="Gini Coefficient" value={analytics?.gini} color={analytics?.gini > 0.5 ? "text-nce-red" : "text-nce-green"} />
        <StatCard label="Stability" value={analytics?.stability} color={analytics?.stability < 0.4 ? "text-nce-red" : "text-nce-green"} />
        <StatCard label="Entropy" value={analytics?.entropy} color="text-nce-purple" />
        <StatCard label="Pop (alive)" value={`${pop.alive ?? "—"} / ${pop.total ?? "—"}`} />
        <StatCard label="Avg Health" value={pop.avg_health} color="text-nce-green" />
        <StatCard label="Avg Stress" value={pop.avg_stress} color={pop.avg_stress > 60 ? "text-nce-red" : "text-nce-yellow"} />
      </div>

      {/* Trend charts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <TrendChart metric="gini_coefficient" label="Gini Trend" color="#ef4444" />
        <TrendChart metric="stability_index" label="Stability Trend" color="#10b981" />
        <TrendChart metric="entropy" label="Entropy Trend" color="#8b5cf6" />
      </div>

      {/* Network + Instability */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="panel">
          <div className="panel-title">Network Metrics</div>
          <div className="space-y-2 text-sm">
            {[
              ["Density", (net.density ?? 0).toFixed(4)],
              ["Avg Clustering", (net.avg_clustering ?? 0).toFixed(4)],
              ["Communities", net.num_communities ?? "—"],
              ["Nodes", net.node_count ?? "—"],
              ["Edges", net.edge_count ?? "—"],
            ].map(([k, v]) => (
              <div key={k as string} className="flex justify-between">
                <span className="text-gray-500">{k}</span>
                <span className="text-white font-mono">{v}</span>
              </div>
            ))}
          </div>
        </div>

        {analytics?.instability ? (
          <div className="panel border-nce-red/40">
            <div className="panel-title text-nce-red">⚠ Instability Alert</div>
            <div className="text-sm space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-500">Severity</span>
                <span className="text-nce-red font-bold">{(analytics.instability.severity * 100).toFixed(0)}%</span>
              </div>
              <ul className="text-xs text-gray-300 space-y-1">
                {(analytics.instability.reasons ?? []).map((r: string, i: number) => (
                  <li key={i} className="text-nce-yellow">• {r}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="panel">
            <div className="panel-title">System Health</div>
            <div className="text-nce-green text-sm">✓ No instability detected</div>
          </div>
        )}
      </div>

      {/* Leaders + Clusters + Conflict Zones */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Emergent Leaders */}
        <div className="panel">
          <div className="panel-title">Emergent Leaders</div>
          <div className="space-y-2">
            {(leadersData?.leaders ?? []).slice(0, 6).map((l: {
              agent_id: string; type: string; influence: number; followers: number;
            }) => (
              <div key={l.agent_id} className="flex items-center justify-between text-xs">
                <div>
                  <span className="text-white font-semibold">{l.agent_id}</span>
                  <span className="text-gray-500 ml-2">[{l.type}]</span>
                </div>
                <div className="text-right">
                  <div className="text-nce-accent">{(l.influence * 100).toFixed(1)}%</div>
                  <div className="text-gray-500">{l.followers} followers</div>
                </div>
              </div>
            ))}
            {!leadersData?.leaders?.length && <span className="text-gray-500 text-xs">No leaders detected yet</span>}
          </div>
        </div>

        {/* Cooperation Clusters */}
        <div className="panel">
          <div className="panel-title">Cooperation Clusters</div>
          <div className="space-y-2">
            {(clustersData?.clusters ?? []).slice(0, 6).map((c: {
              id: string; size: number; cohesion: number; dominant_type: string;
            }) => (
              <div key={c.id} className="flex items-center justify-between text-xs">
                <div>
                  <span className="badge-blue badge">{c.size} agents</span>
                  <span className="text-gray-500 ml-2">{c.dominant_type}</span>
                </div>
                <div className="text-nce-green">{(c.cohesion * 100).toFixed(0)}% cohesion</div>
              </div>
            ))}
            {!clustersData?.clusters?.length && <span className="text-gray-500 text-xs">No clusters detected</span>}
          </div>
        </div>

        {/* Conflict Zones */}
        <div className="panel">
          <div className="panel-title">Conflict Zones</div>
          <div className="space-y-2">
            {(zonesData?.zones ?? []).slice(0, 6).map((z: {
              id: string; center: { x: number; y: number }; intensity: number; agents_involved: number;
            }) => (
              <div key={z.id} className="flex items-center justify-between text-xs">
                <span className="text-gray-300">({z.center.x},{z.center.y})</span>
                <div className="text-right">
                  <div className={z.intensity > 0.6 ? "text-nce-red" : "text-nce-yellow"}>
                    {(z.intensity * 100).toFixed(0)}% intensity
                  </div>
                  <div className="text-gray-500">{z.agents_involved} agents</div>
                </div>
              </div>
            ))}
            {!zonesData?.zones?.length && <span className="text-gray-500 text-xs">No active conflict zones</span>}
          </div>
        </div>
      </div>

      {/* Wealth Distribution bar chart */}
      {pop.wealth && (
        <div className="panel">
          <div className="panel-title">Wealth Distribution Stats</div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
            {[
              ["Mean", pop.wealth.mean?.toFixed(1)],
              ["Median", pop.wealth.median?.toFixed(1)],
              ["Std Dev", pop.wealth.std?.toFixed(1)],
              ["Top 10% Share", `${(pop.wealth.top10_share * 100)?.toFixed(1)}%`],
              ["Gini", pop.wealth.gini?.toFixed(3)],
            ].map(([k, v]) => (
              <div key={k as string} className="flex flex-col">
                <span className="text-gray-500">{k}</span>
                <span className="text-white font-bold text-base">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
