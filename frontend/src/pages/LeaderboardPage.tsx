import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { HeroImage } from "../components/HeroImage";
import { fetchLeaderboard } from "../lib/api";
import type {
  AppConfig,
  LeaderboardHero,
  LeaderboardMatchup,
  LeaderboardSort,
  SortOrder,
} from "../types/api";

interface LeaderboardPageProps {
  config: AppConfig;
}

function MatchupStrip({ matchups }: { matchups: LeaderboardMatchup[] }) {
  if (!matchups.length) return <span className="muted-cell">暂无数据</span>;
  return (
    <div className="matchup-strip">
      {matchups.map((matchup) => (
        <HeroImage
          key={matchup.hero_id}
          src={matchup.image}
          alt={matchup.hero_name}
          className="matchup-image"
        />
      ))}
    </div>
  );
}

function compareHeroes(left: LeaderboardHero, right: LeaderboardHero, sortBy: LeaderboardSort, order: SortOrder) {
  if (sortBy === "name") {
    const value = left.hero_name.localeCompare(right.hero_name, "zh-CN");
    return order === "asc" ? value : -value;
  }
  const leftValue = left[sortBy] ?? -1;
  const rightValue = right[sortBy] ?? -1;
  const value = Number(leftValue) - Number(rightValue) || left.appearances - right.appearances;
  return order === "asc" ? value : -value;
}

export function LeaderboardPage({ config }: LeaderboardPageProps) {
  const [rank, setRank] = useState("All");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<LeaderboardSort>("win_rate");
  const [order, setOrder] = useState<SortOrder>("desc");
  const query = useQuery({
    queryKey: ["leaderboard", rank, sortBy, order],
    queryFn: ({ signal }) => fetchLeaderboard(rank, sortBy, order, signal),
    placeholderData: (previous) => previous,
  });

  const heroes = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return (query.data?.heroes ?? [])
      .filter((hero) => !normalized || hero.hero_name.toLowerCase().includes(normalized) || String(hero.hero_id) === normalized)
      .sort((left, right) => compareHeroes(left, right, sortBy, order));
  }, [order, query.data?.heroes, search, sortBy]);

  const changeSort = (nextSort: LeaderboardSort) => {
    if (sortBy === nextSort) setOrder((value) => value === "desc" ? "asc" : "desc");
    else {
      setSortBy(nextSort);
      setOrder(nextSort === "name" ? "asc" : "desc");
    }
  };

  const SortIcon = order === "desc" ? ArrowDown : ArrowUp;

  return (
    <main className="leaderboard-page">
      <header className="page-heading">
        <div><span className="eyebrow">META OVERVIEW</span><h1>英雄排行榜</h1><p>{query.data ? `${query.data.rank === "All" ? "全部分段" : query.data.rank} · ${query.data.total_matches.toLocaleString("zh-CN")} 场比赛` : "正在读取比赛统计"}</p></div>
        <div className="leaderboard-filters">
          <label><span>分段</span><select className="control-select" value={rank} onChange={(event) => setRank(event.target.value)}><option value="All">全部分段</option>{config.rank_segments.map((segment) => <option value={segment} key={segment}>{segment}</option>)}</select></label>
          <label><span>搜索</span><span className="search-field"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="英雄名称或 ID" /></span></label>
        </div>
      </header>

      {query.isError && <div className="inline-error">{query.error.message}</div>}
      <div className={`leaderboard-table-wrap ${query.isFetching ? "updating" : ""}`}>
        <table className="leaderboard-table">
          <thead><tr><th>#</th><th><button type="button" onClick={() => changeSort("name")}>英雄{sortBy === "name" && <SortIcon size={13} />}</button></th><th><button type="button" onClick={() => changeSort("pick_rate")}>Pick 率{sortBy === "pick_rate" && <SortIcon size={13} />}</button></th><th><button type="button" onClick={() => changeSort("win_rate")}>胜率{sortBy === "win_rate" && <SortIcon size={13} />}</button></th><th>对阵克制</th><th>被克制</th></tr></thead>
          <tbody>{heroes.map((hero, index) => <tr key={hero.hero_id}><td className="result-rank">{String(index + 1).padStart(2, "0")}</td><td><div className="leaderboard-hero"><HeroImage src={hero.image} alt={hero.hero_name} /><span><strong>{hero.hero_name}</strong><small>{hero.appearances.toLocaleString("zh-CN")} 场</small></span></div></td><td>{(hero.pick_rate * 100).toFixed(2)}%</td><td className="win-rate">{hero.win_rate === null ? "-" : `${(hero.win_rate * 100).toFixed(2)}%`}</td><td><MatchupStrip matchups={hero.counters} /></td><td><MatchupStrip matchups={hero.countered_by} /></td></tr>)}</tbody>
        </table>
        {!heroes.length && !query.isPending && <div className="empty-state">没有匹配的英雄</div>}
      </div>
    </main>
  );
}
