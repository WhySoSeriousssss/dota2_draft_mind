import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Calculator,
  Check,
  ChevronLeft,
  ChevronRight,
  Plus,
  Search,
  Users,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { HeroImage } from "../components/HeroImage";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { fetchRecommendations } from "../lib/api";
import { useDraftStore, type DraftSide } from "../store/draftStore";
import type {
  AppConfig,
  Hero,
  HeroAttribute,
  RecommendationRequest,
  RecommendationResult,
} from "../types/api";

interface DraftPageProps {
  config: AppConfig;
}

type AttributeFilter = "all" | "all_attr" | HeroAttribute;
type MobileView = "draft" | "results";

const attributeFilters: Array<{ value: AttributeFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "str", label: "力量" },
  { value: "agi", label: "敏捷" },
  { value: "int", label: "智力" },
  { value: "all_attr", label: "全才" },
];

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(4)}`;
}

function contributionClass(value: number) {
  if (value > 0.000001) return "positive";
  if (value < -0.000001) return "negative";
  return undefined;
}

interface TeamColumnProps {
  side: DraftSide;
  picks: number[];
  capacity: number;
  heroById: Map<number, Hero>;
}

function TeamColumn({ side, picks, capacity, heroById }: TeamColumnProps) {
  const activeSide = useDraftStore((state) => state.activeSide);
  const setActiveSide = useDraftStore((state) => state.setActiveSide);
  const removeHero = useDraftStore((state) => state.removeHero);
  const isAlly = side === "ally";

  return (
    <section className={clsx("team-column", isAlly ? "radiant" : "dire")}>
      <button
        type="button"
        className={clsx("team-column-heading", activeSide === side && "active")}
        onClick={() => setActiveSide(side)}
      >
        <span>{isAlly ? "我方阵容" : "敌方阵容"}</span>
        <small>{picks.length} / {capacity}</small>
      </button>
      <div className="pick-list">
        {Array.from({ length: capacity }, (_, index) => {
          const heroId = picks[index];
          const hero = heroId === undefined ? undefined : heroById.get(heroId);
          if (!hero) {
            return (
              <button
                className="pick-slot empty"
                type="button"
                key={`empty-${index}`}
                onClick={() => setActiveSide(side)}
                aria-label={`添加${isAlly ? "我方" : "敌方"}英雄`}
              >
                <Plus size={16} />
              </button>
            );
          }
          return (
            <div className="pick-slot" key={hero.id}>
              <HeroImage src={hero.icon || hero.image} alt={hero.name} />
              <span>{hero.name}</span>
              <button type="button" onClick={() => removeHero(hero.id, side)} aria-label={`移除 ${hero.name}`}>
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}

interface HeroPoolProps {
  heroes: Hero[];
  selectedIds: Set<number>;
}

function HeroPool({ heroes, selectedIds }: HeroPoolProps) {
  const [search, setSearch] = useState("");
  const [attribute, setAttribute] = useState<AttributeFilter>("all");
  const activeSide = useDraftStore((state) => state.activeSide);
  const addHero = useDraftStore((state) => state.addHero);

  const filteredHeroes = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return heroes.filter((hero) => {
      const matchesAttribute = attribute === "all"
        || (attribute === "all_attr" && hero.attribute === "all")
        || hero.attribute === attribute;
      const matchesSearch = !normalized
        || hero.name.toLowerCase().includes(normalized)
        || String(hero.id) === normalized;
      return matchesAttribute && matchesSearch;
    });
  }, [attribute, heroes, search]);

  return (
    <section className="draft-section hero-pool-section">
      <div className="section-title-row">
        <div><h2>英雄池</h2><span>点击英雄加入{activeSide === "ally" ? "我方" : "敌方"}</span></div>
        <div className="side-toggle" aria-label="当前选择阵营">
          <button
            type="button"
            className={activeSide === "ally" ? "active radiant" : ""}
            onClick={() => useDraftStore.getState().setActiveSide("ally")}
          >我方</button>
          <button
            type="button"
            className={activeSide === "enemy" ? "active dire" : ""}
            onClick={() => useDraftStore.getState().setActiveSide("enemy")}
          >敌方</button>
        </div>
      </div>
      <label className="search-field">
        <Search size={15} />
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索英雄或 ID" />
      </label>
      <div className="attribute-filter">
        {attributeFilters.map((filter) => {
          return (
            <button
              type="button"
              key={filter.value}
              className={attribute === filter.value ? "active" : ""}
              onClick={() => setAttribute(filter.value)}
            >
              {filter.label}
            </button>
          );
        })}
      </div>
      <div className="hero-grid">
        {filteredHeroes.map((hero) => (
          <button
            className="hero-tile"
            type="button"
            key={hero.id}
            disabled={selectedIds.has(hero.id)}
            onClick={() => addHero(hero.id)}
            title={`${hero.name} · ID ${hero.id}`}
          >
            <HeroImage src={hero.image} alt={hero.name} />
            <span>{hero.name}</span>
            {selectedIds.has(hero.id) && <i><Check size={14} /></i>}
          </button>
        ))}
      </div>
    </section>
  );
}

interface RecommendationsProps {
  results: RecommendationResult[];
  heroById: Map<number, Hero>;
  rank: string;
  isFetching: boolean;
  error?: string;
  onRefresh: () => void;
}

function Recommendations({ results, heroById, rank, isFetching, error, onRefresh }: RecommendationsProps) {
  const [page, setPage] = useState(1);
  const allies = useDraftStore((state) => state.allies);
  const enemies = useDraftStore((state) => state.enemies);
  const topK = useDraftStore((state) => state.topK);
  const setTopK = useDraftStore((state) => state.setTopK);
  const addHero = useDraftStore((state) => state.addHero);
  const totalPages = Math.max(1, Math.ceil(results.length / 15));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * 15;
  const pageResults = results.slice(pageStart, pageStart + 15);

  return (
    <section className="recommendations-panel">
      <header className="recommendations-header">
        <div>
          <span className="eyebrow">DRAFT SCORE V1</span>
          <h1>推荐英雄</h1>
          <p>{rank} · 我方 {allies.length} · 敌方 {enemies.length} · Top {results.length}</p>
        </div>
        <div className="recommend-actions">
          <label><span>推荐数</span><input type="number" min="1" max="127" value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></label>
          <button className="primary-button" type="button" onClick={onRefresh} disabled={isFetching}>
            <Calculator size={16} />{isFetching ? "计算中" : "计算推荐"}
          </button>
        </div>
      </header>

      {error && <div className="inline-error">{error}</div>}
      <div className={clsx("results-table-wrap", isFetching && "updating")}>
        <table className="results-table">
          <thead><tr><th>#</th><th>英雄</th><th>Draft Score</th><th>基础胜率</th><th>对位贡献</th><th>协同贡献</th><th>熟练度</th><th>分段场次</th><th /></tr></thead>
          <tbody>
            {pageResults.map((result, index) => {
              const hero = heroById.get(result.hero_id);
              if (!hero) return null;
              return (
                <tr key={result.hero_id}>
                  <td className="result-rank">{String(pageStart + index + 1).padStart(2, "0")}</td>
                  <td><div className="result-hero"><HeroImage src={hero.image} alt={hero.name} /><span><strong>{hero.name}</strong><small>ID {hero.id}</small></span></div></td>
                  <td className="score-cell">{result.score.toFixed(4)}</td>
                  <td>{(result.base_score * 100).toFixed(2)}%</td>
                  <td className={contributionClass(result.counter_component)}>{signed(result.counter_component)}</td>
                  <td className={contributionClass(result.synergy_component)}>{signed(result.synergy_component)}</td>
                  <td className={contributionClass(result.proficiency_component)}>{signed(result.proficiency_component)}</td>
                  <td>{result.base_appearances.toLocaleString("zh-CN")}</td>
                  <td><button className="table-action" type="button" onClick={() => addHero(result.hero_id, "ally")} disabled={allies.length >= 4} aria-label={`将 ${hero.name} 加入我方`}><Plus size={16} /></button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!pageResults.length && !isFetching && <div className="empty-state">当前筛选条件下没有可推荐英雄</div>}
      </div>
      {totalPages > 1 && (
        <nav className="pagination" aria-label="推荐结果分页">
          <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={currentPage === 1}><ChevronLeft size={16} />上一页</button>
          <span>第 {currentPage} / {totalPages} 页</span>
          <button type="button" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={currentPage === totalPages}>下一页<ChevronRight size={16} /></button>
        </nav>
      )}
    </section>
  );
}

export function DraftPage({ config }: DraftPageProps) {
  const [mobileView, setMobileView] = useState<MobileView>("draft");
  const allies = useDraftStore((state) => state.allies);
  const enemies = useDraftStore((state) => state.enemies);
  const rank = useDraftStore((state) => state.rank);
  const positionIds = useDraftStore((state) => state.positionIds);
  const weights = useDraftStore((state) => state.weights);
  const topK = useDraftStore((state) => state.topK);
  const proficiencies = useDraftStore((state) => state.proficiencies);
  const setRank = useDraftStore((state) => state.setRank);
  const togglePosition = useDraftStore((state) => state.togglePosition);
  const heroById = useMemo(() => new Map(config.heroes.map((hero) => [hero.id, hero])), [config.heroes]);
  const selectedIds = useMemo(() => new Set([...allies, ...enemies]), [allies, enemies]);

  const request = useMemo<RecommendationRequest>(() => ({
    rank,
    allies,
    enemies,
    excluded_hero_ids: [],
    position_ids: positionIds,
    hero_proficiencies: proficiencies,
    weights,
    top_k: topK,
  }), [allies, enemies, positionIds, proficiencies, rank, topK, weights]);
  const debouncedRequest = useDebouncedValue(request, 180);
  const recommendationQuery = useQuery({
    queryKey: ["recommendations", debouncedRequest],
    queryFn: ({ signal }) => fetchRecommendations(debouncedRequest, signal),
    enabled: Boolean(rank),
    placeholderData: (previous) => previous,
  });

  return (
    <main className="draft-page">
      <div className="mobile-view-tabs">
        <button className={mobileView === "draft" ? "active" : ""} type="button" onClick={() => setMobileView("draft")}><Users size={15} />阵容</button>
        <button className={mobileView === "results" ? "active" : ""} type="button" onClick={() => setMobileView("results")}><Calculator size={15} />推荐</button>
      </div>

      <aside className={clsx("draft-sidebar", mobileView !== "draft" && "mobile-hidden")}>
        <section className="draft-section match-settings">
          <div className="section-title-row"><div><h2>比赛参数</h2><span>筛选当前对局环境</span></div></div>
          <label className="field-label"><span>分段</span><select className="control-select" value={rank} onChange={(event) => setRank(event.target.value)}>{config.rank_segments.map((segment) => <option value={segment} key={segment}>{segment}</option>)}</select></label>
          <div className="field-label"><span>想玩的位置</span><div className="position-grid">{config.positions.map((position) => <button type="button" key={position.id} className={positionIds.includes(position.id) ? "active" : ""} onClick={() => togglePosition(position.id)}>{positionIds.includes(position.id) && <Check size={13} />}{position.name}</button>)}</div></div>
        </section>

        <section className="draft-section composition-section">
          <div className="section-title-row"><div><h2>当前阵容</h2><span>选择空位后从英雄池添加</span></div></div>
          <div className="teams-grid">
            <TeamColumn side="ally" picks={allies} capacity={4} heroById={heroById} />
            <TeamColumn side="enemy" picks={enemies} capacity={5} heroById={heroById} />
          </div>
        </section>
        <HeroPool heroes={config.heroes} selectedIds={selectedIds} />
      </aside>

      <div className={clsx("draft-results", mobileView !== "results" && "mobile-hidden-results")}>
        <Recommendations
          results={recommendationQuery.data?.results ?? []}
          heroById={heroById}
          rank={rank}
          isFetching={recommendationQuery.isFetching}
          error={recommendationQuery.error?.message}
          onRefresh={() => recommendationQuery.refetch()}
        />
      </div>
    </main>
  );
}
