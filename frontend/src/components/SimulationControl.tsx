import { useState } from "react";
import {
  startSimulation, stopSimulation, pauseSimulation,
  resumeSimulation, stepSimulation, updateParameters,
  useSimStatus,
} from "../hooks/useApi";

export default function SimulationControl() {
  const { data: status, mutate } = useSimStatus();
  const [config, setConfig] = useState({
    world_width: 50,
    world_height: 50,
    initial_agents: 80,
    max_agents: 200,
    tick_interval_ms: 100,
    max_ticks: 10000,
    auto_scenarios: true,
  });
  const [loading, setLoading] = useState(false);

  const isRunning = status?.status === "running";
  const isPaused = status?.status === "paused";
  const isIdle = !status || ["idle", "ready", "stopped"].includes(status.status);

  const handle = async (fn: () => Promise<unknown>) => {
    setLoading(true);
    try {
      await fn();
      await mutate();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="panel-title">Simulation Control</div>

      {/* Status indicator */}
      <div className="panel space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">Status</span>
          <span className={
            isRunning ? "text-nce-green" :
            isPaused ? "text-nce-yellow" : "text-gray-400"
          }>
            {status?.status?.toUpperCase() ?? "IDLE"}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">Tick</span>
          <span className="text-white">{status?.tick ?? 0}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">Agents</span>
          <span className="text-white">{status?.agent_count ?? 0}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">Scenarios</span>
          <span className={status?.active_scenarios > 0 ? "text-nce-red" : "text-gray-400"}>
            {status?.active_scenarios ?? 0} active
          </span>
        </div>
      </div>

      {/* Action buttons */}
      <div className="space-y-2">
        {isIdle && (
          <button
            className="btn-primary w-full"
            onClick={() => handle(() => startSimulation(config))}
            disabled={loading}
          >
            ▶ Start Simulation
          </button>
        )}
        {isRunning && (
          <>
            <button className="btn-ghost w-full" onClick={() => handle(pauseSimulation)}>
              ⏸ Pause
            </button>
            <button className="btn-danger w-full" onClick={() => handle(stopSimulation)}>
              ⏹ Stop
            </button>
          </>
        )}
        {isPaused && (
          <>
            <button className="btn-primary w-full" onClick={() => handle(resumeSimulation)}>
              ▶ Resume
            </button>
            <button className="btn-ghost w-full" onClick={() => handle(() => stepSimulation(10))}>
              ⏭ Step ×10
            </button>
            <button className="btn-danger w-full" onClick={() => handle(stopSimulation)}>
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      {/* Configuration (shown only when idle) */}
      {isIdle && (
        <div className="panel space-y-3">
          <div className="panel-title">Configuration</div>

          {[
            { label: "World Width", key: "world_width", min: 20, max: 200 },
            { label: "World Height", key: "world_height", min: 20, max: 200 },
            { label: "Initial Agents", key: "initial_agents", min: 10, max: 400 },
            { label: "Max Agents", key: "max_agents", min: 20, max: 800 },
            { label: "Tick Interval (ms)", key: "tick_interval_ms", min: 10, max: 2000 },
            { label: "Max Ticks", key: "max_ticks", min: 500, max: 50000 },
          ].map(({ label, key, min, max }) => (
            <div key={key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-400">{label}</span>
                <span className="text-white">{(config as Record<string, unknown>)[key] as number}</span>
              </div>
              <input
                type="range"
                min={min}
                max={max}
                value={(config as Record<string, unknown>)[key] as number}
                onChange={(e) => setConfig((c) => ({ ...c, [key]: Number(e.target.value) }))}
                className="w-full accent-nce-accent"
              />
            </div>
          ))}

          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400">Auto Scenarios</span>
            <button
              onClick={() => setConfig((c) => ({ ...c, auto_scenarios: !c.auto_scenarios }))}
              className={`px-2 py-0.5 rounded text-xs font-bold ${
                config.auto_scenarios ? "bg-nce-green/20 text-nce-green" : "bg-gray-700 text-gray-400"
              }`}
            >
              {config.auto_scenarios ? "ON" : "OFF"}
            </button>
          </div>
        </div>
      )}

      {/* Live parameter tuning (when running/paused) */}
      {(isRunning || isPaused) && (
        <div className="panel space-y-3">
          <div className="panel-title">Live Tuning</div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-400">Tick Speed (ms)</span>
              <span className="text-white">{config.tick_interval_ms}</span>
            </div>
            <input
              type="range"
              min={10}
              max={2000}
              value={config.tick_interval_ms}
              onChange={(e) => {
                const v = Number(e.target.value);
                setConfig((c) => ({ ...c, tick_interval_ms: v }));
                updateParameters({ tick_interval_ms: v });
              }}
              className="w-full accent-nce-accent"
            />
          </div>
        </div>
      )}
    </div>
  );
}
