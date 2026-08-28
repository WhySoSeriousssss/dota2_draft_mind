import { useQuery } from "@tanstack/react-query";
import { BarChart3, Crosshair } from "lucide-react";
import { useEffect } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { SettingsMenu } from "./components/settings/SettingsMenu";
import { fetchConfig } from "./lib/api";
import { useI18n } from "./lib/i18n";
import { DraftPage } from "./pages/DraftPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { useDraftStore } from "./store/draftStore";

export function App() {
  const { t } = useI18n();
  const configQuery = useQuery({
    queryKey: ["config"],
    queryFn: ({ signal }) => fetchConfig(signal),
  });
  const hydrated = useDraftStore((state) => state.hydrated);
  const hydrate = useDraftStore((state) => state.hydrate);

  useEffect(() => {
    if (configQuery.data) hydrate(configQuery.data);
  }, [configQuery.data, hydrate]);

  if (configQuery.isPending || (configQuery.data && !hydrated)) {
    return <div className="app-loading"><span className="loading-mark" />{t("app.loading")}</div>;
  }

  if (configQuery.isError || !configQuery.data) {
    return (
      <div className="fatal-error">
        <strong>{t("app.loadError")}</strong>
        <span>{t("app.serviceHint")}</span>
        <button type="button" onClick={() => configQuery.refetch()}>{t("app.retry")}</button>
      </div>
    );
  }

  const config = configQuery.data;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <span className="brand-emblem"><Crosshair size={19} /></span>
          <div><strong>DOTA 2 Draft Mind</strong><span>{t("app.subtitle")}</span></div>
        </div>

        <nav className="primary-nav" aria-label={t("nav.main")}>
          <NavLink to="/" end><Crosshair size={16} />{t("nav.draft")}</NavLink>
          <NavLink to="/leaderboard"><BarChart3 size={16} />{t("nav.leaderboard")}</NavLink>
        </nav>

        <div className="header-meta">
          <span>{t("app.heroCount", { heroes: config.heroes.length, ranks: config.rank_segments.length })}</span>
          <SettingsMenu config={config} />
        </div>
      </header>

      <Routes>
        <Route path="/" element={<DraftPage config={config} />} />
        <Route path="/leaderboard" element={<LeaderboardPage config={config} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
