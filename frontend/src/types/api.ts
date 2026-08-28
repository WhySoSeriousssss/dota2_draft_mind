export type HeroAttribute = "str" | "agi" | "int" | "all";
export type Proficiency = -1 | 0 | 1;
export type RecommendationAlgorithm = "v1" | "v2";

export interface Hero {
  id: number;
  name: string;
  attribute: HeroAttribute;
  roles: string[];
  image: string;
  icon: string;
}

export interface Position {
  id: number;
  key: "carry" | "mid" | "offlane" | "support";
  name: string;
  hero_ids: number[];
}

export interface DraftWeights {
  alpha: number;
  beta: number;
  gamma: number;
  delta: number;
}

export interface AppConfig {
  heroes: Hero[];
  positions: Position[];
  rank_segments: string[];
  defaults: {
    rank: string;
    weights: DraftWeights;
    top_k: number;
  };
  dataset_version: string | null;
}

export interface RecommendationRequest {
  rank: string;
  allies: number[];
  enemies: number[];
  excluded_hero_ids: number[];
  position_ids: number[];
  hero_proficiencies: Record<number, Proficiency>;
  weights: DraftWeights;
  top_k: number;
}

export interface RecommendationResult {
  hero_id: number;
  hero_name: string;
  score: number;
  base_score: number;
  counter_sum: number;
  synergy_sum: number;
  proficiency_score: Proficiency;
  base_appearances: number;
  base_component: number;
  counter_component: number;
  synergy_component: number;
  proficiency_component: number;
}

export interface RecommendationResponse {
  rank: string;
  position_ids: number[];
  weights: DraftWeights;
  results: RecommendationResult[];
  model_version: string;
  dataset_version: string | null;
}

export interface V2RecommendationRequest {
  rank: string;
  allies: number[];
  enemies: number[];
  excluded_hero_ids: number[];
  position_ids: number[];
  side: "radiant" | "dire" | null;
  top_k: number;
}

export interface V2RecommendationResult {
  hero_id: number;
  hero_name: string;
  win_probability: number;
}

export interface V2RecommendationResponse {
  rank: string;
  position_ids: number[];
  side: "radiant" | "dire" | null;
  results: V2RecommendationResult[];
  model_version: string;
  dataset_version: string | null;
}

export interface LeaderboardMatchup {
  hero_id: number;
  hero_name: string;
  image: string;
  appearances: number;
  win_rate: number;
  advantage: number;
}

export interface LeaderboardHero {
  hero_id: number;
  hero_name: string;
  image: string;
  appearances: number;
  pick_rate: number;
  win_rate: number | null;
  counters: LeaderboardMatchup[];
  countered_by: LeaderboardMatchup[];
}

export interface LeaderboardResponse {
  rank: string;
  total_matches: number;
  heroes: LeaderboardHero[];
  dataset_version: string | null;
}

export type LeaderboardSort = "name" | "pick_rate" | "win_rate" | "appearances";
export type SortOrder = "asc" | "desc";
