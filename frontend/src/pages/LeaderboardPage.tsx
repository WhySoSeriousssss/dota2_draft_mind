import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { HeroImage } from "../components/HeroImage";
import { DEFAULT_API_ERROR, fetchLeaderboard } from "../lib/api";
import { useI18n } from "../lib/i18n";
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
  const { heroName, t } = useI18n();
  if (!matchups.length) return <span className="muted-cell">{t("common.noData")}</span>;
  return (
    <div className="matchup-strip">
      {matchups.map((matchup) => (
        <HeroImage
          key={matchup.hero_id}
          src={matchup.image}
          alt={heroName(matchup.hero_id, matchup.hero_name)}
          className="matchup-image"
        />
      ))}
    </div>
  );
}

function compareHeroes(left: LeaderboardHero, right: LeaderboardHero, sortBy: LeaderboardSort, order: SortOrder, leftName: string, rightName: string, locale: string) {
  if (sortBy === "name") {
    const value = leftName.localeCompare(rightName, locale);
    return order === "asc" ? value : -value;
  }
  const leftValue = left[sortBy] ?? -1;
  const rightValue = right[sortBy] ?? -1;
  const value = Number(leftValue) - Number(rightValue) || left.appearances - right.appearances;
  return order === "asc" ? value : -value;
}

export function LeaderboardPage({ config }: LeaderboardPageProps) {
  const { heroName, locale, numberLocale, rankName, t } = useI18n();
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
      .filter((hero) => !normalized || hero.hero_name.toLowerCase().includes(normalized) || heroName(hero.hero_id, hero.hero_name).toLowerCase().includes(normalized))
      .sort((left, right) => compareHeroes(left, right, sortBy, order, heroName(left.hero_id, left.hero_name), heroName(right.hero_id, right.hero_name), locale));
  }, [heroName, locale, order, query.data?.heroes, search, sortBy]);

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
        <div><span className="eyebrow">META OVERVIEW</span><h1>{t("leaderboard.title")}</h1><p>{query.data ? t("leaderboard.summary", { rank: query.data.rank === "All" ? t("leaderboard.allRanks") : rankName(query.data.rank), matches: query.data.total_matches.toLocaleString(numberLocale) }) : t("leaderboard.loading")}</p></div>
        <div className="leaderboard-filters">
          <label><span>{t("common.rank")}</span><select className="control-select" value={rank} onChange={(event) => setRank(event.target.value)}><option value="All">{t("leaderboard.allRanks")}</option>{config.rank_segments.map((segment) => <option value={segment} key={segment}>{rankName(segment)}</option>)}</select></label>
          <label><span>{t("common.search")}</span><span className="search-field"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("leaderboard.searchHero")} /></span></label>
        </div>
      </header>

      {query.isError && <div className="inline-error">{query.error.message === DEFAULT_API_ERROR ? t("common.requestFailed") : query.error.message}</div>}
      <div className={`leaderboard-table-wrap ${query.isFetching ? "updating" : ""}`}>
        <table className="leaderboard-table">
          <thead><tr><th>#</th><th><button type="button" onClick={() => changeSort("name")}>{t("common.hero")}{sortBy === "name" && <SortIcon size={13} />}</button></th><th><button type="button" onClick={() => changeSort("pick_rate")}>{t("leaderboard.pickRate")}{sortBy === "pick_rate" && <SortIcon size={13} />}</button></th><th><button type="button" onClick={() => changeSort("win_rate")}>{t("leaderboard.winRate")}{sortBy === "win_rate" && <SortIcon size={13} />}</button></th><th>{t("leaderboard.counters")}</th><th>{t("leaderboard.counteredBy")}</th></tr></thead>
          <tbody>{heroes.map((hero, index) => { const displayName = heroName(hero.hero_id, hero.hero_name); return <tr key={hero.hero_id}><td className="result-rank">{String(index + 1).padStart(2, "0")}</td><td><div className="leaderboard-hero"><HeroImage src={hero.image} alt={displayName} /><span><strong>{displayName}</strong><small>{t("common.matches", { count: hero.appearances.toLocaleString(numberLocale) })}</small></span></div></td><td>{(hero.pick_rate * 100).toFixed(2)}%</td><td className="win-rate">{hero.win_rate === null ? "-" : `${(hero.win_rate * 100).toFixed(2)}%`}</td><td><MatchupStrip matchups={hero.counters} /></td><td><MatchupStrip matchups={hero.countered_by} /></td></tr>; })}</tbody>
        </table>
        {!heroes.length && !query.isPending && <div className="empty-state">{t("leaderboard.empty")}</div>}
      </div>
    </main>
  );
}
