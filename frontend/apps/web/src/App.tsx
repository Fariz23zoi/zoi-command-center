import { api, connectEvents, type Preferences } from "@zoi/api-client";
import { type ReactElement, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { CommandCenter } from "./layout/CommandCenter";
import { UniverseShell } from "./layout/UniverseShell";
import { DashboardPage } from "./pages/DashboardPage";
import { MENU } from "./menu";
import { AiLocalPage } from "./pages/AiLocalPage";
import { AssistantPage } from "./pages/AssistantPage";
import { VoicePage } from "./pages/VoicePage";
import { MemoryPage } from "./pages/MemoryPage";
import { AiCloudPage } from "./pages/AiCloudPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AutomationPage } from "./pages/AutomationPage";
import { CompetitorsPage } from "./pages/CompetitorsPage";
import { IdeasPage } from "./pages/IdeasPage";
import { PerformancePage } from "./pages/PerformancePage";
import { ProductionPage } from "./pages/ProductionPage";
import { ScriptPage } from "./pages/ScriptPage";
import { TrendsPage } from "./pages/TrendsPage";
import { ViralPage } from "./pages/ViralPage";
import { MonetizationPage } from "./pages/MonetizationPage";
import { YouTubeSettingsPage } from "./pages/YouTubeSettingsPage";
import { useReplyVoice } from "./lib/voice/useReplyVoice";
import { IntegrationPage } from "./pages/IntegrationPage";
import { NotYetAvailable } from "./pages/NotYetAvailable";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { useApp } from "./stores/appStore";

const DEFAULT_PREFS: Preferences = { ui_language: "id", avatar_mode_preference: "auto", avatar_character: "female" };

const READY_PAGES: Record<string, ReactElement> = {
  "/dashboard": <DashboardPage />,
  "/diagnostics": <OverviewPage />,
  "/tasks": <TasksPage />,
  "/memory": <MemoryPage />,
  "/analytics": <AnalyticsPage />,
  "/monetization": <MonetizationPage />,
  "/competitors": <CompetitorsPage />,
  "/viral": <ViralPage />,
  "/trends": <TrendsPage />,
  "/ideas": <IdeasPage />,
  "/script": <ScriptPage />,
  "/production": <ProductionPage />,
  "/automation": <AutomationPage />,
  "/performance": <PerformancePage />,
  "/settings": <SettingsPage />,
  "/clipper": <IntegrationPage adapterName="zoi_ai_clipper" />,
  "/blueprint": <IntegrationPage adapterName="blueprint_studio" />,
};

export function App() {
  const { setConfig, setConnected, setTasks, setProvider, setAdapters, setPrefs, setBootstrapped, handleEvent } =
    useApp.getState();

  useReplyVoice();
  useEffect(() => {
    // Avatar menunggu konfigurasi + preferensi (atau kegagalan keduanya) agar renderer dipilih sekali saja.
    Promise.allSettled([
      api.config().then(setConfig),
      api.preferences().then(setPrefs, () => setPrefs(DEFAULT_PREFS)),
    ]).then(setBootstrapped);
    api.voice.status().then(useApp.getState().setVoiceStatus).catch(() => undefined);
    api.tasks().then((r) => setTasks(r.tasks)).catch(() => undefined);
    api.providerStatus().then(setProvider).catch(() => undefined);
    api.adapters().then((r) => setAdapters(r.adapters)).catch(() => undefined);
    api.notifications.list().then((r) => useApp.setState({ unreadNotifications: r.unread })).catch(() => undefined);
    const connection = connectEvents(handleEvent, setConnected);
    return () => connection.close();
  }, [setConfig, setConnected, setTasks, setProvider, setAdapters, setPrefs, setBootstrapped, handleEvent]);

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      {/* Workspace ZOI AI (chat + avatar). Phase 4 menggantinya dengan workspace khusus. */}
      <Route element={<CommandCenter />}>
        <Route path="/ai" element={<AssistantPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/ai/settings" element={<SettingsPage />} />
      </Route>
      <Route element={<UniverseShell />}>
        {MENU.filter((item) => item.path !== "/ai").map((item) => (
          <Route
            key={item.path}
            path={item.path}
            element={READY_PAGES[item.path] ?? <NotYetAvailable item={item} />}
          />
        ))}
        <Route path="/settings/ai" element={<AiLocalPage />} />
        <Route path="/settings/voice" element={<VoicePage />} />
        <Route path="/settings/youtube" element={<YouTubeSettingsPage />} />
        <Route path="/settings/ai-cloud" element={<AiCloudPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

function NotFoundPage() {
  return (
    <section className="page">
      <h1>Halaman tidak ditemukan</h1>
      <p className="muted">Pilih menu di sebelah kiri.</p>
    </section>
  );
}
