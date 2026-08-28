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
import { DEFAULT_API_ERROR, fetchRecommendations } from "../lib/api";
import { useI18n, type TranslationKey } from "../lib/i18n";
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

const attributeFilters: AttributeFilter[] = ["all", "str", "agi", "int", "all_attr"];

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
  const { heroName, t } = useI18n();
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
        <span>{isAlly ? t("draft.allyLineup") : t("draft.enemyLineup")}</span>
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
                aria-label={t("draft.addHero", { side: isAlly ? t("draft.ally") : t("draft.enemy") })}
              >
                <Plus size={16} />
              </button>
            );
          }
          const displayName = heroName(hero.id, hero.name);
          return (
            <div className="pick-slot" key={hero.id}>
              <HeroImage src={hero.icon || hero.image} alt={displayName} />
              <span>{displayName}</span>
              <button type="button" onClick={() => removeHero(hero.id, side)} aria-label={t("draft.removeHero", { hero: displayName })}>
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
  const { heroName, t } = useI18n();
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
        || heroName(hero.id, hero.name).toLowerCase().includes(normalized);
      return matchesAttribute && matchesSearch;
    });
  }, [attribute, heroName, heroes, search]);

  return (
    <section className="draft-section hero-pool-section">
      <div className="section-title-row">
        <div><h2>{t("draft.heroPool")}</h2><span>{t("draft.heroPoolHint", { side: activeSide === "ally" ? t("draft.ally") : t("draft.enemy") })}</span></div>
        <div className="side-toggle" aria-label={t("draft.activeSide")}>
          <button
            type="button"
            className={activeSide === "ally" ? "active radiant" : ""}
            onClick={() => useDraftStore.getState().setActiveSide("ally")}
          >{t("draft.ally")}</button>
          <button
            type="button"
            className={activeSide === "enemy" ? "active dire" : ""}
            onClick={() => useDraftStore.getState().setActiveSide("enemy")}
          >{t("draft.enemy")}</button>
        </div>
      </div>
      <label className="search-field">
        <Search size={15} />
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("draft.searchHero")} />
      </label>
      <div className="attribute-filter">
        {attributeFilters.map((filter) => {
          return (
            <button
              type="button"
              key={filter}
              className={attribute === filter ? "active" : ""}
              onClick={() => setAttribute(filter)}
            >
              {t(`attribute.${filter}` as TranslationKey)}
            </button>
          );
        })}
      </div>
      <div className="hero-grid">
        {filteredHeroes.map((hero) => {
          const displayName = heroName(hero.id, hero.name);
          return (
            <button
              className="hero-tile"
              type="button"
              key={hero.id}
              disabled={selectedIds.has(hero.id)}
              onClick={() => addHero(hero.id)}
              title={displayName}
            >
              <HeroImage src={hero.image} alt={displayName} />
              <span>{displayName}</span>
              {selectedIds.has(hero.id) && <i><Check size={14} /></i>}
            </button>
          );
        })}
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
  const { heroName, numberLocale, rankName, t } = useI18n();
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
          <h1>{t("draft.recommendations")}</h1>
          <p>{t("draft.recommendationSummary", { rank: rankName(rank), allies: allies.length, enemies: enemies.length, count: results.length })}</p>
        </div>
        <div className="recommend-actions">
          <label><span>{t("draft.recommendationCount")}</span><input type="number" min="1" max="127" value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></label>
          <button className="primary-button" type="button" onClick={onRefresh} disabled={isFetching}>
            <Calculator size={16} />{isFetching ? t("draft.calculating") : t("draft.calculate")}
          </button>
        </div>
      </header>

      {error && <div className="inline-error">{error}</div>}
      <div className={clsx("results-table-wrap", isFetching && "updating")}>
        <table className="results-table">
          <thead><tr><th>#</th><th>{t("common.hero")}</th><th>Draft Score</th><th>{t("draft.baseWinRate")}</th><th>{t("draft.counterContribution")}</th><th>{t("draft.synergyContribution")}</th><th>{t("draft.proficiency")}</th><th>{t("draft.rankMatches")}</th><th /></tr></thead>
          <tbody>
            {pageResults.map((result, index) => {
              const hero = heroById.get(result.hero_id);
              if (!hero) return null;
              const displayName = heroName(hero.id, hero.name);
              return (
                <tr key={result.hero_id}>
                  <td className="result-rank">{String(pageStart + index + 1).padStart(2, "0")}</td>
                  <td><div className="result-hero"><HeroImage src={hero.image} alt={displayName} /><span><strong>{displayName}</strong></span></div></td>
                  <td className="score-cell">{result.score.toFixed(4)}</td>
                  <td>{(result.base_score * 100).toFixed(2)}%</td>
                  <td className={contributionClass(result.counter_component)}>{signed(result.counter_component)}</td>
                  <td className={contributionClass(result.synergy_component)}>{signed(result.synergy_component)}</td>
                  <td className={contributionClass(result.proficiency_component)}>{signed(result.proficiency_component)}</td>
                  <td>{result.base_appearances.toLocaleString(numberLocale)}</td>
                  <td><button className="table-action" type="button" onClick={() => addHero(result.hero_id, "ally")} disabled={allies.length >= 4} aria-label={t("draft.addToAllies", { hero: displayName })}><Plus size={16} /></button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!pageResults.length && !isFetching && <div className="empty-state">{t("draft.emptyRecommendations")}</div>}
      </div>
      {totalPages > 1 && (
        <nav className="pagination" aria-label={t("draft.resultsPagination")}>
          <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={currentPage === 1}><ChevronLeft size={16} />{t("draft.previous")}</button>
          <span>{t("draft.page", { current: currentPage, total: totalPages })}</span>
          <button type="button" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={currentPage === totalPages}>{t("draft.next")}<ChevronRight size={16} /></button>
        </nav>
      )}
    </section>
  );
}

export function DraftPage({ config }: DraftPageProps) {
  const { rankName, t } = useI18n();
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
        <button className={mobileView === "draft" ? "active" : ""} type="button" onClick={() => setMobileView("draft")}><Users size={15} />{t("draft.mobileDraft")}</button>
        <button className={mobileView === "results" ? "active" : ""} type="button" onClick={() => setMobileView("results")}><Calculator size={15} />{t("draft.mobileResults")}</button>
      </div>

      <aside className={clsx("draft-sidebar", mobileView !== "draft" && "mobile-hidden")}>
        <section className="draft-section match-settings">
          <div className="section-title-row"><div><h2>{t("draft.matchSettings")}</h2><span>{t("draft.matchSettingsHint")}</span></div></div>
          <label className="field-label"><span>{t("common.rank")}</span><select className="control-select" value={rank} onChange={(event) => setRank(event.target.value)}>{config.rank_segments.map((segment) => <option value={segment} key={segment}>{rankName(segment)}</option>)}</select></label>
          <div className="field-label"><span>{t("draft.positions")}</span><div className="position-grid">{config.positions.map((position) => <button type="button" key={position.id} className={positionIds.includes(position.id) ? "active" : ""} onClick={() => togglePosition(position.id)}>{positionIds.includes(position.id) && <Check size={13} />}{t(`position.${position.key}`)}</button>)}</div></div>
        </section>

        <section className="draft-section composition-section">
          <div className="section-title-row"><div><h2>{t("draft.composition")}</h2><span>{t("draft.compositionHint")}</span></div></div>
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
          error={recommendationQuery.error?.message === DEFAULT_API_ERROR ? t("common.requestFailed") : recommendationQuery.error?.message}
          onRefresh={() => recommendationQuery.refetch()}
        />
      </div>
    </main>
  );
}
