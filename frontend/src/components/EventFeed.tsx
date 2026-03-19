// EventFeed.tsx
import { useRecentEvents } from "../hooks/useApi";

const EVENT_COLORS: Record<string, string> = {
  trade_completed: "text-nce-green",
  agent_death_war: "text-nce-red",
  agent_death: "text-nce-red",
  war_declared: "text-nce-red",
  plague_outbreak: "text-nce-yellow",
  disease_spread: "text-nce-yellow",
  market_crash: "text-nce-red",
  scenario_resolved: "text-nce-green",
  building_constructed: "text-nce-accent",
  agent_recruited: "text-nce-purple",
  espionage: "text-gray-400",
  rebellion_started: "text-nce-red",
};

export default function EventFeed() {
  const { data } = useRecentEvents(100);
  const events: Array<{ tick: number; type: string; description: string; agents: string[] }> =
    data?.events ?? [];

  return (
    <div className="h-full flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="panel-title">Event Feed</div>
        <span className="text-xs text-gray-500">{events.length} events</span>
      </div>
      <div className="flex-1 overflow-auto space-y-1">
        {events.map((e, i) => (
          <div
            key={i}
            className="flex gap-3 text-xs border-b border-nce-border/30 py-1.5"
          >
            <span className="text-gray-600 shrink-0 w-12 text-right">t{e.tick}</span>
            <span className={`w-36 shrink-0 ${EVENT_COLORS[e.type] ?? "text-gray-400"}`}>
              {e.type.replace(/_/g, " ")}
            </span>
            <span className="text-gray-300 flex-1">{e.description}</span>
            {e.agents?.length > 0 && (
              <span className="text-nce-accent shrink-0 text-right">
                {e.agents.slice(0, 2).join(", ")}
                {e.agents.length > 2 && ` +${e.agents.length - 2}`}
              </span>
            )}
          </div>
        ))}
        {events.length === 0 && (
          <div className="text-gray-500 text-sm">No events yet. Start the simulation.</div>
        )}
      </div>
    </div>
  );
}
