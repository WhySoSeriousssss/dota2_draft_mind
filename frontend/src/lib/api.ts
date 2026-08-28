import type {
  AppConfig,
  LeaderboardResponse,
  LeaderboardSort,
  RecommendationRequest,
  RecommendationResponse,
  SortOrder,
  V2RecommendationRequest,
  V2RecommendationResponse,
} from "../types/api";

export const DEFAULT_API_ERROR = "DEFAULT_API_ERROR";

const API_PREFIX = "/api/v1";

interface ApiErrorPayload {
  error?: { message?: string };
  detail?: string;
}

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, options);
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json() as T & ApiErrorPayload
    : null;

  if (!response.ok) {
    throw new ApiError(
      payload?.error?.message || payload?.detail || DEFAULT_API_ERROR,
      response.status,
    );
  }

  if (!payload) {
    throw new ApiError(DEFAULT_API_ERROR, response.status);
  }

  return payload as T;
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

export function fetchV2Recommendations(payload: V2RecommendationRequest, signal?: AbortSignal) {
  return request<V2RecommendationResponse>("/recommend/v2", {
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
