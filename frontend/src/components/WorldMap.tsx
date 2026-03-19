import { useRef, useEffect, useState } from "react";
import * as d3 from "d3";
import { useHeatmap, useSimState } from "../hooks/useApi";

const RESOURCES = ["food", "water", "energy", "tools", "medicine", "money"];

export default function WorldMap() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedResource, setSelectedResource] = useState("food");
  const { data: heatmapData } = useHeatmap(selectedResource);
  const { data: simState } = useSimState();
  const [hoveredCell, setHoveredCell] = useState<{ x: number; y: number; value: number } | null>(null);

  const agents = simState?.agents ? Object.values(simState.agents) : [];

  useEffect(() => {
    if (!svgRef.current || !heatmapData?.grid) return;

    const grid: number[][] = heatmapData.grid;
    const rows = grid.length;
    const cols = grid[0]?.length ?? 0;
    if (rows === 0 || cols === 0) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;
    const cellW = width / cols;
    const cellH = height / rows;

    const maxVal = d3.max(grid.flat()) || 1;
    const colorScale = d3.scaleSequential(d3.interpolateYlGn).domain([0, maxVal]);

    svg.selectAll("g.grid-layer").remove();
    const layer = svg.append("g").attr("class", "grid-layer");

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const val = grid[row][col];
        layer
          .append("rect")
          .attr("x", col * cellW)
          .attr("y", row * cellH)
          .attr("width", cellW)
          .attr("height", cellH)
          .attr("fill", colorScale(val))
          .attr("stroke", "none")
          .on("mouseover", () => setHoveredCell({ x: col, y: row, value: val }))
          .on("mouseout", () => setHoveredCell(null));
      }
    }

    // Render agents
    svg.selectAll("g.agent-layer").remove();
    const agentLayer = svg.append("g").attr("class", "agent-layer");

    const typeColors: Record<string, string> = {
      worker: "#60a5fa",
      trader: "#34d399",
      leader: "#f59e0b",
      scientist: "#a78bfa",
      builder: "#f97316",
      spy: "#6b7280",
      farmer: "#86efac",
      thief: "#ef4444",
      diplomat: "#38bdf8",
      guard: "#fbbf24",
      rebel: "#dc2626",
      mediator: "#2dd4bf",
    };

    for (const agent of agents as Array<{
      position: { x: number; y: number };
      type: string;
      health: number;
      agent_id: string;
    }>) {
      const cx = (agent.position.x + 0.5) * cellW;
      const cy = (agent.position.y + 0.5) * cellH;
      const r = Math.max(2, Math.min(cellW / 2.5, cellH / 2.5));
      const color = typeColors[agent.type] || "#ffffff";

      agentLayer
        .append("circle")
        .attr("cx", cx)
        .attr("cy", cy)
        .attr("r", r)
        .attr("fill", color)
        .attr("opacity", 0.75)
        .attr("stroke", agent.health < 30 ? "#ef4444" : "none")
        .attr("stroke-width", 1.5);
    }
  }, [heatmapData, agents]);

  return (
    <div className="h-full flex flex-col gap-3">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-gray-500 text-xs">Resource overlay:</span>
        {RESOURCES.map((r) => (
          <button
            key={r}
            onClick={() => setSelectedResource(r)}
            className={`badge ${selectedResource === r ? "badge-green" : "bg-nce-border text-gray-400"} cursor-pointer`}
          >
            {r}
          </button>
        ))}
        {simState?.world && (
          <span className="ml-auto text-xs text-gray-500">
            {simState.world.season} · {simState.world.weather} · Day {simState.world.day}
          </span>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 relative border border-nce-border rounded overflow-hidden bg-black">
        <svg ref={svgRef} className="w-full h-full" />

        {/* Tooltip */}
        {hoveredCell && (
          <div className="absolute bottom-4 left-4 bg-nce-panel border border-nce-border rounded px-3 py-1.5 text-xs">
            ({hoveredCell.x}, {hoveredCell.y}) — {selectedResource}: <strong>{hoveredCell.value.toFixed(1)}</strong>
          </div>
        )}

        {/* Legend */}
        <div className="absolute top-3 right-3 flex flex-col gap-1 bg-nce-panel/80 rounded px-2 py-1.5 text-xs">
          <span className="text-gray-500 font-semibold mb-1">Agents</span>
          {[
            ["leader", "#f59e0b"],
            ["rebel", "#dc2626"],
            ["guard", "#fbbf24"],
            ["spy", "#6b7280"],
            ["trader", "#34d399"],
            ["worker", "#60a5fa"],
          ].map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
              <span className="text-gray-300">{type}</span>
            </div>
          ))}
        </div>

        {/* Active disasters */}
        {simState?.world?.active_disasters?.length > 0 && (
          <div className="absolute top-3 left-3 bg-nce-red/20 border border-nce-red/40 rounded px-2 py-1 text-xs text-nce-red">
            ⚠ {simState.world.active_disasters.join(", ")}
          </div>
        )}
      </div>

      {/* Agent count bar */}
      <div className="flex gap-4 text-xs text-gray-500">
        <span>Agents shown: {agents.length}</span>
        {simState?.world && (
          <span>Buildings: {simState.world.buildings}</span>
        )}
      </div>
    </div>
  );
}
