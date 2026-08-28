import { useQuery } from "@tanstack/react-query";
import { BarChart3, Crosshair } from "lucide-react";
import { useEffect } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { SettingsMenu } from "./components/settings/SettingsMenu";
import { fetchConfig } from "./lib/api";
import { DraftPage } from "./pages/DraftPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { useDraftStore } from "./store/draftStore";

export function App() {
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
    return <div className="app-loading"><span className="loading-mark" />正在载入比赛数据</div>;
  }

  if (configQuery.isError || !configQuery.data) {
    return (
      <div className="fatal-error">
        <strong>无法载入比赛数据</strong>
        <span>{configQuery.error?.message ?? "请确认 FastAPI 服务正在运行"}</span>
        <button type="button" onClick={() => configQuery.refetch()}>重新连接</button>
      </div>
    );
  }

  const config = configQuery.data;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <span className="brand-emblem"><Crosshair size={19} /></span>
          <div><strong>DOTA 2 Draft Mind</strong><span>Ranked Draft Intelligence</span></div>
        </div>

        <nav className="primary-nav" aria-label="主要功能">
          <NavLink to="/" end><Crosshair size={16} />选人助手</NavLink>
          <NavLink to="/leaderboard"><BarChart3 size={16} />英雄排行榜</NavLink>
        </nav>

        <div className="header-meta">
          <span>{config.heroes.length} 位英雄 · {config.rank_segments.length} 个分段</span>
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
