const API_PREFIX = "/api/v1";


async function request(path, options = {}) {
  const response = await fetch(`${API_PREFIX}${path}`, options);
  const payload = await response.json();

  if (!response.ok) {
    const error = payload.error;
    throw new Error(error?.message || "请求失败");
  }

  return payload;
}


export function fetchConfig() {
  return request("/config");
}


export function fetchRecommendations(payload) {
  return request("/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
