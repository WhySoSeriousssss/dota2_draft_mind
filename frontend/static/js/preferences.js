const STORAGE_KEY = "dota2-draft-mind:draft-preferences:v1";


export function loadDraftPreferences(storage = window.localStorage) {
  try {
    const value = storage.getItem(STORAGE_KEY);
    return value ? JSON.parse(value) : null;
  } catch (_error) {
    return null;
  }
}


export function saveDraftPreferences(preferences, storage = window.localStorage) {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    return true;
  } catch (_error) {
    return false;
  }
}


function validWeight(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number <= 2
    ? number
    : fallback;
}


export function resolveDraftPreferences(saved, config) {
  const availableRanks = new Set(config.rank_segments);
  const availablePositionIds = new Set(
    config.positions.map((position) => position.id),
  );
  const savedPositionIds = Array.isArray(saved?.positionIds)
    ? saved.positionIds
    : [];
  const positionIds = [...new Set(
    savedPositionIds
      .map(Number)
      .filter((positionId) => availablePositionIds.has(positionId)),
  )].sort((left, right) => left - right);

  return {
    rank: availableRanks.has(saved?.rank)
      ? saved.rank
      : config.defaults.rank,
    positionIds,
    weights: {
      alpha: validWeight(
        saved?.weights?.alpha,
        config.defaults.weights.alpha,
      ),
      beta: validWeight(
        saved?.weights?.beta,
        config.defaults.weights.beta,
      ),
      gamma: validWeight(
        saved?.weights?.gamma,
        config.defaults.weights.gamma,
      ),
    },
  };
}
