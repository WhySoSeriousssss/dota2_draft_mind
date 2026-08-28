import type {
  AppConfig,
  LeaderboardResponse,
  LeaderboardSort,
  RecommendationRequest,
  RecommendationResponse,
  SortOrder,
} from "../types/api";

const API_PREFIX = "/api/v1";

interface ApiErrorPayload {
  error?: { message?: string };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, options);
  const payload = (await response.json()) as T & ApiErrorPayload;

  if (!response.ok) {
    throw new Error(payload.error?.message || "请求失败，请稍后重试");
  }

  return payload;
}

export function fetchConfig(signal?: AbortSignal) {
  return request<AppConfig>("/config", { signal });
}

export function fetchRecommendations(payload: RecommendationRequest, signal?: AbortSignal) {
  return request<RecommendationResponse>("/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export function fetchLeaderboard(
  rank: string,
  sortBy: LeaderboardSort,
  order: SortOrder,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({ rank, sort_by: sortBy, order });
  return request<LeaderboardResponse>(`/leaderboard?${query}`, { signal });
}
