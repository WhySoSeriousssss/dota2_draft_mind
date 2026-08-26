export const state = {
  heroes: [],
  heroById: new Map(),
  allies: [],
  enemies: [],
  excludedHeroIds: [],
  activeSide: "ally",
  attribute: "all",
  search: "",
  requestSequence: 0,
  debounceTimer: null,
};
