import { create } from "zustand";

import {
  loadProficiencies,
  resolveDraftPreferences,
  saveDraftPreferences,
  saveProficiencies,
} from "../lib/storage";
import type {
  AppConfig,
  DraftWeights,
  Proficiency,
  RecommendationAlgorithm,
} from "../types/api";

export type DraftSide = "ally" | "enemy";

interface DraftState {
  hydrated: boolean;
  allies: number[];
  enemies: number[];
  activeSide: DraftSide;
  rank: string;
  positionIds: number[];
  weights: DraftWeights;
  topK: number;
  proficiencies: Record<number, Proficiency>;
  algorithm: RecommendationAlgorithm;
  hydrate: (config: AppConfig) => void;
  setRank: (rank: string) => void;
  togglePosition: (positionId: number) => void;
  setWeight: (key: keyof DraftWeights, value: number) => void;
  setTopK: (topK: number) => void;
  setAlgorithm: (algorithm: RecommendationAlgorithm) => void;
  setActiveSide: (side: DraftSide) => void;
  addHero: (heroId: number, side?: DraftSide) => boolean;
  removeHero: (heroId: number, side: DraftSide) => void;
  setProficiency: (heroId: number, value: Proficiency) => void;
  resetProficiencies: () => void;
}

const defaultWeights: DraftWeights = { alpha: 1, beta: 0.5, gamma: 0.8, delta: 0.05 };

export const useDraftStore = create<DraftState>((set, get) => {
  const persistPreferences = () => {
    const state = get();
    saveDraftPreferences({
      rank: state.rank,
      positionIds: state.positionIds,
      weights: state.weights,
      topK: state.topK,
      algorithm: state.algorithm,
    });
  };

  return {
    hydrated: false,
    allies: [],
    enemies: [],
    activeSide: "ally",
    rank: "",
    positionIds: [],
    weights: defaultWeights,
    topK: 15,
    proficiencies: {},
    algorithm: "v1",
    hydrate: (config) => {
      if (get().hydrated) return;
      const preferences = resolveDraftPreferences(config);
      const validHeroIds = new Set(config.heroes.map((hero) => hero.id));
      set({
        hydrated: true,
        rank: preferences.rank,
        positionIds: preferences.positionIds,
        weights: preferences.weights,
        topK: preferences.topK,
        algorithm: preferences.algorithm ?? "v1",
        proficiencies: loadProficiencies(validHeroIds),
      });
    },
    setRank: (rank) => {
      set({ rank });
      persistPreferences();
    },
    togglePosition: (positionId) => {
      set((state) => ({
        positionIds: state.positionIds.includes(positionId)
          ? state.positionIds.filter((id) => id !== positionId)
          : [...state.positionIds, positionId].sort(),
      }));
      persistPreferences();
    },
    setWeight: (key, value) => {
      set((state) => ({ weights: { ...state.weights, [key]: value } }));
      persistPreferences();
    },
    setTopK: (topK) => {
      set({ topK: Math.min(127, Math.max(1, Math.trunc(topK) || 15)) });
      persistPreferences();
    },
    setAlgorithm: (algorithm) => {
      set({ algorithm });
      persistPreferences();
    },
    setActiveSide: (activeSide) => set({ activeSide }),
    addHero: (heroId, requestedSide) => {
      const state = get();
      const side = requestedSide ?? state.activeSide;
      const target = side === "ally" ? state.allies : state.enemies;
      const capacity = side === "ally" ? 4 : 5;
      if (state.allies.includes(heroId) || state.enemies.includes(heroId) || target.length >= capacity) {
        return false;
      }
      set({ [side === "ally" ? "allies" : "enemies"]: [...target, heroId] });
      return true;
    },
    removeHero: (heroId, side) => {
      const key = side === "ally" ? "allies" : "enemies";
      set((state) => ({ [key]: state[key].filter((id) => id !== heroId) }));
    },
    setProficiency: (heroId, value) => {
      const next = { ...get().proficiencies };
      if (value === 0) delete next[heroId];
      else next[heroId] = value;
      set({ proficiencies: next });
      saveProficiencies(next);
    },
    resetProficiencies: () => {
      set({ proficiencies: {} });
      saveProficiencies({});
    },
  };
});
