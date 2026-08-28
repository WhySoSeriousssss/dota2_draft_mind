import {
  DRAFT_PREFERENCES_KEY,
  PROFICIENCIES_KEY,
  loadProficiencies,
  resolveDraftPreferences,
  saveDraftPreferences,
} from "./storage";
import type { AppConfig } from "../types/api";

const config: AppConfig = {
  heroes: [
    { id: 25, name: "Lina", attribute: "int", roles: [], image: "", icon: "" },
    { id: 50, name: "Dazzle", attribute: "all", roles: [], image: "", icon: "" },
  ],
  positions: [
    { id: 0, key: "carry", name: "Carry", hero_ids: [25] },
    { id: 1, key: "mid", name: "Mid", hero_ids: [25] },
  ],
  rank_segments: ["Legend", "Ancient"],
  defaults: {
    rank: "Legend",
    weights: { alpha: 1, beta: 0.5, gamma: 0.8, delta: 0.05 },
    top_k: 15,
  },
  dataset_version: null,
};

describe("local storage compatibility", () => {
  beforeEach(() => window.localStorage.clear());

  it("restores legacy draft preferences and validates values", () => {
    window.localStorage.setItem(DRAFT_PREFERENCES_KEY, JSON.stringify({
      rank: "Ancient",
      positionIds: [1, 1, 99],
      weights: { alpha: 1.2, beta: 0.4, gamma: 0.9, delta: 0.12 },
    }));

    expect(resolveDraftPreferences(config)).toEqual({
      rank: "Ancient",
      positionIds: [1],
      weights: { alpha: 1.2, beta: 0.4, gamma: 0.9, delta: 0.12 },
      topK: 15,
    });
  });

  it("persists the custom recommendation count", () => {
    saveDraftPreferences({
      rank: "Legend",
      positionIds: [0],
      weights: config.defaults.weights,
      topK: 30,
    });

    expect(resolveDraftPreferences(config).topK).toBe(30);
  });

  it("keeps only valid non-default proficiency values", () => {
    window.localStorage.setItem(PROFICIENCIES_KEY, JSON.stringify({
      25: -1,
      50: 1,
      51: 1,
      52: 0,
    }));

    expect(loadProficiencies(new Set([25, 50]))).toEqual({ 25: -1, 50: 1 });
  });
});
