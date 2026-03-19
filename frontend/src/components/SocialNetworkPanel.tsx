import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { useAnalytics, useClusters, useLeaders } from "../hooks/useApi";

export default function SocialNetworkPanel() {
  const svgRef = useRef<SVGSVGElement>(null);
  const { data: analytics } = useAnalytics();
  const { data: clustersData } = useClusters();
  const { data: leadersData } = useLeaders();

  const clusters = clustersData?.clusters ?? [];
  const leaders = leadersData?.leaders ?? [];
  const net = analytics?.network ?? {};

  useEffect(() => {
    if (!svgRef.current || clusters.length === 0) return;

    const svg = d3.select(svgRef.current);
    const w = svgRef.current.clientWidth;
    const h = svgRef.current.clientHeight;

    svg.selectAll("*").remove();

    // Build nodes and links from clusters
    const nodes: Array<{ id: string; group: number; size: number; cohesion: number }> = [];
    const links: Array<{ source: string; target: string; value: number }> = [];

    clusters.forEach((c: { id: string; size: number; cohesion: number; avg_trust: number }, gi: number) => {
      // Create a node per cluster member (simplified)
      nodes.push({ id: c.id, group: gi, size: c.size, cohesion: c.cohesion });
    });

    // Create links between clusters (simplified — proximity based)
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        if (Math.random() < 0.3) {
          links.push({ source: nodes[i].id, target: nodes[j].id, value: Math.random() });
        }
      }
    }

    if (nodes.length === 0) return;

    const color = d3.scaleOrdinal(d3.schemeTableau10);

    const simulation = d3
      .forceSimulation(nodes as d3.SimulationNodeDatum[])
      .force("link", d3.forceLink(links).id((d: d3.SimulationNodeDatum) => (d as { id: string }).id).distance(80))
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collision", d3.forceCollide(30));

    const g = svg.append("g");

    // Links
    const link = g.append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "#374151")
      .attr("stroke-width", 1);

    // Nodes
    const node = g.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .call(
        d3.drag<SVGGElement, (typeof nodes)[0]>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            (d as d3.SimulationNodeDatum).fx = (d as d3.SimulationNodeDatum).x;
            (d as d3.SimulationNodeDatum).fy = (d as d3.SimulationNodeDatum).y;
          })
          .on("drag", (event, d) => {
            (d as d3.SimulationNodeDatum).fx = event.x;
            (d as d3.SimulationNodeDatum).fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            (d as d3.SimulationNodeDatum).fx = null;
            (d as d3.SimulationNodeDatum).fy = null;
          })
      );

    node.append("circle")
      .attr("r", (d) => 10 + d.size * 2)
      .attr("fill", (_, i) => color(String(i)))
      .attr("opacity", 0.8)
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 1);

    node.append("text")
      .text((d) => `${d.size}`)
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("fill", "#ffffff")
      .attr("font-size", 10)
      .attr("font-family", "monospace");

    // Zoom
    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on("zoom", (event) => g.attr("transform", event.transform))
    );

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => ((d.source as d3.SimulationNodeDatum).x ?? 0))
        .attr("y1", (d) => ((d.source as d3.SimulationNodeDatum).y ?? 0))
        .attr("x2", (d) => ((d.target as d3.SimulationNodeDatum).x ?? 0))
        .attr("y2", (d) => ((d.target as d3.SimulationNodeDatum).y ?? 0));

      node.attr("transform", (d) =>
        `translate(${(d as d3.SimulationNodeDatum).x ?? 0},${(d as d3.SimulationNodeDatum).y ?? 0})`
      );
    });

    return () => { simulation.stop(); };
  }, [clusters]);

  return (
    <div className="h-full flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-3">
        <div className="panel">
          <div className="text-xs text-gray-500">Network Density</div>
          <div className="text-xl font-bold text-nce-accent">{(net.density ?? 0).toFixed(4)}</div>
        </div>
        <div className="panel">
          <div className="text-xs text-gray-500">Communities</div>
          <div className="text-xl font-bold text-nce-purple">{net.num_communities ?? 0}</div>
        </div>
        <div className="panel">
          <div className="text-xs text-gray-500">Avg Clustering</div>
          <div className="text-xl font-bold text-nce-green">{(net.avg_clustering ?? 0).toFixed(4)}</div>
        </div>
      </div>

      {/* Force graph */}
      <div className="flex-1 border border-nce-border rounded overflow-hidden bg-nce-dark relative">
        <svg ref={svgRef} className="w-full h-full" />
        {clusters.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm">
            No cooperation clusters detected yet. Nodes appear as clusters emerge.
          </div>
        )}
        <div className="absolute bottom-3 left-3 text-xs text-gray-600">
          Each node = cooperation cluster. Size = member count. Drag to rearrange.
        </div>
      </div>

      {/* Top leaders below graph */}
      <div className="panel">
        <div className="panel-title">Top Influencers</div>
        <div className="flex gap-6 overflow-x-auto">
          {leaders.slice(0, 5).map((l: {
            agent_id: string; type: string; influence: number; followers: number;
          }) => (
            <div key={l.agent_id} className="text-xs shrink-0">
              <div className="text-nce-accent font-semibold">{l.agent_id}</div>
              <div className="text-gray-500">{l.type}</div>
              <div className="text-nce-green">{(l.influence * 100).toFixed(1)}%</div>
              <div className="text-gray-600">{l.followers} followers</div>
            </div>
          ))}
          {leaders.length === 0 && <span className="text-gray-500">No leaders yet.</span>}
        </div>
      </div>
    </div>
  );
}
