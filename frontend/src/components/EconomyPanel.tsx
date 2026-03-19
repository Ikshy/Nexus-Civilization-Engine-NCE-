import { useAnalytics, useWorldState } from "../hooks/useApi";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function EconomyPanel() {
  const { data: analytics } = useAnalytics();
  const { data: world } = useWorldState();
  const wealth = analytics?.population?.wealth ?? {};

  const wealthChartData = wealth.gini != null ? [
    { name: "Mean", value: wealth.mean ?? 0 },
    { name: "Median", value: wealth.median ?? 0 },
    { name: "Min", value: wealth.min ?? 0 },
    { name: "Max", value: wealth.max ?? 0 },
  ] : [];

  return (
    <div className="space-y-4">
      {/* World economy stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ["Inflation Rate", world?.inflation_rate?.toFixed(3) ?? "1.000", world?.inflation_rate > 1.5 ? "text-nce-red" : "text-nce-green"],
          ["Institution Health", world?.institution_health?.toFixed(0) ?? "—", world?.institution_health < 50 ? "text-nce-red" : "text-nce-green"],
          ["Enforcement", world?.enforcement_strength?.toFixed(2) ?? "—", "text-nce-accent"],
          ["Buildings", world?.buildings ?? "—", "text-white"],
        ].map(([label, value, color]) => (
          <div key={label as string} className="panel">
            <div className="text-xs text-gray-500 mb-1">{label}</div>
            <div className={`text-xl font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Wealth distribution */}
      <div className="panel">
        <div className="panel-title">Wealth Distribution</div>
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-3">
            {[
              ["Gini Coefficient", wealth.gini?.toFixed(4), wealth.gini > 0.5 ? "text-nce-red" : "text-nce-green"],
              ["Mean Wealth", wealth.mean?.toFixed(1), "text-white"],
              ["Median Wealth", wealth.median?.toFixed(1), "text-white"],
              ["Top 10% Share", `${((wealth.top10_share ?? 0) * 100).toFixed(1)}%`, "text-nce-yellow"],
              ["Std Dev", wealth.std?.toFixed(1), "text-gray-300"],
            ].map(([k, v, color]) => (
              <div key={k as string} className="flex justify-between text-sm">
                <span className="text-gray-500">{k}</span>
                <span className={`font-bold ${color}`}>{v ?? "—"}</span>
              </div>
            ))}
          </div>
          <div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={wealthChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 10 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: "#111827", border: "1px solid #1f2937", fontSize: 11 }}
                  formatter={(v: number) => v.toFixed(2)}
                />
                <Bar dataKey="value" fill="#3b82f6" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Inequality info */}
      <div className="panel">
        <div className="panel-title">Inequality Interpretation</div>
        <div className="text-sm text-gray-400 space-y-2">
          {wealth.gini != null ? (
            <>
              <p>
                Gini coefficient of <strong className="text-white">{wealth.gini?.toFixed(3)}</strong>{" "}
                {wealth.gini < 0.3 ? "indicates a relatively egalitarian distribution." :
                 wealth.gini < 0.5 ? "indicates moderate inequality." :
                 "indicates high inequality — political instability risk elevated."}
              </p>
              <p>
                The top 10% of agents hold{" "}
                <strong className="text-nce-yellow">{((wealth.top10_share ?? 0) * 100).toFixed(1)}%</strong>{" "}
                of all wealth.
              </p>
            </>
          ) : (
            <p className="text-gray-600">No wealth data available yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
