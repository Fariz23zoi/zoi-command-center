import { api, connectEvents } from "@zoi/api-client";
import { type ReactElement, useEffect } from "react";
import { Route, Routes } from "react-router-dom";

import { CommandCenter } from "./layout/CommandCenter";
import { MENU } from "./menu";
import { AssistantPage } from "./pages/AssistantPage";
import { IntegrationPage } from "./pages/IntegrationPage";
import { NotYetAvailable } from "./pages/NotYetAvailable";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { useApp } from "./stores/appStore";

const READY_PAGES: Record<string, ReactElement> = {
  "/": <OverviewPage />,
  "/assistant": <AssistantPage />,
  "/tasks": <TasksPage />,
  "/settings": <SettingsPage />,
  "/clipper": <IntegrationPage adapterName="zoi_ai_clipper" />,
  "/blueprint": <IntegrationPage adapterName="blueprint_studio" />,
};

export function App() {
  const { setConfig, setConnected, setTasks, setProvider, setAdapters, handleEvent } = useApp.getState();

  useEffect(() => {
    api.config().then(setConfig).catch(() => undefined);
    api.tasks().then((r) => setTasks(r.tasks)).catch(() => undefined);
    api.providerStatus().then(setProvider).catch(() => undefined);
    api.adapters().then((r) => setAdapters(r.adapters)).catch(() => undefined);
    const connection = connectEvents(handleEvent, setConnected);
    return () => connection.close();
  }, [setConfig, setConnected, setTasks, setProvider, setAdapters, handleEvent]);

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
