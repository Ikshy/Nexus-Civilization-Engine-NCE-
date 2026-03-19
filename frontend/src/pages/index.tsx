import type { NextPage } from "next";
import Head from "next/head";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import SimulationControl from "../components/SimulationControl";
import WorldMap from "../components/WorldMap";
import AgentTable from "../components/AgentTable";
import EconomyPanel from "../components/EconomyPanel";
import SocialNetworkPanel from "../components/SocialNetworkPanel";
import AnalyticsPanel from "../components/AnalyticsPanel";
import EventFeed from "../components/EventFeed";
import ScenarioPanel from "../components/ScenarioPanel";
import InfoWarPanel from "../components/InfoWarPanel";
import { useSimStatus } from "../hooks/useApi";

const Dashboard: NextPage = () => {
  const { data: status } = useSimStatus();
  const [activeTab, setActiveTab] = useState("world");

  const statusColor =
    status?.status === "running"
      ? "text-nce-green"
      : status?.status === "paused"
      ? "text-nce-yellow"
      : "text-gray-400";

  return (
    <>
      <Head>
        <title>Nexus Civilization Engine</title>
        <meta name="description" content="Multi-agent civilization simulation research platform" />
      </Head>

      <div className="min-h-screen bg-nce-dark text-gray-100 font-mono">
        {/* Header */}
        <header className="border-b border-nce-border bg-nce-panel px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-xl font-bold text-nce-accent tracking-widest">NCE</span>
            <span className="text-gray-500 text-sm">Nexus Civilization Engine</span>
          </div>
          <div className="flex items-center gap-6 text-sm">
            {status && (
              <>
                <span className={`font-semibold ${statusColor}`}>
                  ● {status.status?.toUpperCase()}
                </span>
                <span className="text-gray-400">
                  Tick <span className="text-white font-semibold">{status.tick ?? "—"}</span>
                </span>
                <span className="text-gray-400">
                  Agents <span className="text-white font-semibold">{status.agent_count ?? "—"}</span>
                </span>
                {status.active_scenarios > 0 && (
                  <span className="text-nce-red">
                    ⚠ {status.active_scenarios} scenario{status.active_scenarios > 1 ? "s" : ""}
                  </span>
                )}
              </>
            )}
          </div>
        </header>

        <div className="flex h-[calc(100vh-57px)]">
          {/* Sidebar: Simulation Control */}
          <aside className="w-72 border-r border-nce-border bg-nce-panel overflow-y-auto shrink-0 p-4">
            <SimulationControl />
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-hidden flex flex-col">
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex flex-col h-full"
            >
              <TabsList className="flex bg-nce-panel border-b border-nce-border px-4 gap-1 shrink-0">
                {[
                  ["world", "🗺 World"],
                  ["agents", "🤖 Agents"],
                  ["economy", "📊 Economy"],
                  ["social", "🕸 Social"],
                  ["analytics", "📈 Analytics"],
                  ["infowar", "📡 Info War"],
                  ["scenarios", "⚠ Scenarios"],
                  ["events", "📋 Events"],
                ].map(([value, label]) => (
                  <TabsTrigger
                    key={value}
                    value={value}
                    className="px-4 py-2 text-sm text-gray-400 data-[state=active]:text-nce-accent data-[state=active]:border-b-2 data-[state=active]:border-nce-accent hover:text-gray-200 transition-colors"
                  >
                    {label}
                  </TabsTrigger>
                ))}
              </TabsList>

              <div className="flex-1 overflow-auto">
                <TabsContent value="world" className="h-full p-4">
                  <WorldMap />
                </TabsContent>
                <TabsContent value="agents" className="h-full p-4">
                  <AgentTable />
                </TabsContent>
                <TabsContent value="economy" className="h-full p-4">
                  <EconomyPanel />
                </TabsContent>
                <TabsContent value="social" className="h-full p-4">
                  <SocialNetworkPanel />
                </TabsContent>
                <TabsContent value="analytics" className="h-full p-4">
                  <AnalyticsPanel />
                </TabsContent>
                <TabsContent value="infowar" className="h-full p-4">
                  <InfoWarPanel />
                </TabsContent>
                <TabsContent value="scenarios" className="h-full p-4">
                  <ScenarioPanel />
                </TabsContent>
                <TabsContent value="events" className="h-full p-4">
                  <EventFeed />
                </TabsContent>
              </div>
            </Tabs>
          </main>
        </div>
      </div>
    </>
  );
};

export default Dashboard;
