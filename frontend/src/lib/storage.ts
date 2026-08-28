import type { AppConfig, DraftWeights, Proficiency } from "../types/api";

export const DRAFT_PREFERENCES_KEY = "dota2-draft-mind:draft-preferences:v1";
export const PROFICIENCIES_KEY = "dota2-draft-mind:hero-proficiencies:v1";

export interface DraftPreferences {
  rank: string;
  positionIds: number[];
  weights: DraftWeights;
  topK?: number;
}

function readJson(key: string, storage: Storage): unknown {
  try {
    const value = storage.getItem(key);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

function validWeight(value: unknown, fallback: number, maximum = 2) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number <= maximum
    ? number
    : fallback;
}

export function resolveDraftPreferences(
  config: AppConfig,
  storage: Storage = window.localStorage,
): DraftPreferences {
  const saved = readJson(DRAFT_PREFERENCES_KEY, storage) as Partial<DraftPreferences> | null;
  const rankSet = new Set(config.rank_segments);
  const positionSet = new Set(config.positions.map((position) => position.id));
  const positionIds = Array.isArray(saved?.positionIds)
    ? [...new Set(saved.positionIds.map(Number).filter((id) => positionSet.has(id)))].sort()
    : [];
  const savedWeights = saved?.weights as Partial<DraftWeights> | undefined;
  const topK = Number(saved?.topK);

  return {
    rank: saved?.rank && rankSet.has(saved.rank) ? saved.rank : config.defaults.rank,
    positionIds,
    weights: {
      alpha: validWeight(savedWeights?.alpha, config.defaults.weights.alpha),
      beta: validWeight(savedWeights?.beta, config.defaults.weights.beta),
      gamma: validWeight(savedWeights?.gamma, config.defaults.weights.gamma),
      delta: validWeight(savedWeights?.delta, config.defaults.weights.delta, 0.2),
    },
    topK: Number.isInteger(topK) && topK >= 1 && topK <= 127
      ? topK
      : config.defaults.top_k,
  };
}

export function saveDraftPreferences(preferences: DraftPreferences, storage: Storage = window.localStorage) {
  try {
    storage.setItem(DRAFT_PREFERENCES_KEY, JSON.stringify(preferences));
  } catch {
    return false;
  }
  return true;
}

export function loadProficiencies(
  validHeroIds: Set<number>,
  storage: Storage = window.localStorage,
): Record<number, Proficiency> {
  const saved = readJson(PROFICIENCIES_KEY, storage);
  if (!saved || typeof saved !== "object") return {};

  return Object.fromEntries(
    Object.entries(saved)
      .map(([heroId, value]) => [Number(heroId), Number(value)] as const)
      .filter(([heroId, value]) => (
        validHeroIds.has(heroId) && (value === -1 || value === 1)
      )),
  ) as Record<number, Proficiency>;
}

export function saveProficiencies(
  proficiencies: Record<number, Proficiency>,
  storage: Storage = window.localStorage,
) {
  try {
    storage.setItem(PROFICIENCIES_KEY, JSON.stringify(proficiencies));
  } catch {
    return false;
  }
  return true;
}
