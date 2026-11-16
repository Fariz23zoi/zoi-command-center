import { api, connectEvents, type Preferences } from "@zoi/api-client";
import { type ReactElement, useEffect } from "react";
import { Route, Routes } from "react-router-dom";

import { CommandCenter } from "./layout/CommandCenter";
import { MENU } from "./menu";
import { AiLocalPage } from "./pages/AiLocalPage";
import { AssistantPage } from "./pages/AssistantPage";
import { VoicePage } from "./pages/VoicePage";
import { MemoryPage } from "./pages/MemoryPage";
import { useReplyVoice } from "./lib/voice/useReplyVoice";
import { IntegrationPage } from "./pages/IntegrationPage";
import { NotYetAvailable } from "./pages/NotYetAvailable";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { useApp } from "./stores/appStore";

const DEFAULT_PREFS: Preferences = { ui_language: "id", avatar_mode_preference: "auto", avatar_character: "female" };

const READY_PAGES: Record<string, ReactElement> = {
  "/": <OverviewPage />,
  "/assistant": <AssistantPage />,
  "/tasks": <TasksPage />,
  "/memory": <MemoryPage />,
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
    const connection = connectEvents(handleEvent, setConnected);
    return () => connection.close();
  }, [setConfig, setConnected, setTasks, setProvider, setAdapters, setPrefs, setBootstrapped, handleEvent]);

  return (
    <Routes>
      <Route element={<CommandCenter />}>
        {MENU.map((item) => (
          <Route
            key={item.path}
            path={item.path}
            element={READY_PAGES[item.path] ?? <NotYetAvailable item={item} />}
          />
        ))}
        <Route path="/settings/ai" element={<AiLocalPage />} />
        <Route path="/settings/voice" element={<VoicePage />} />
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
