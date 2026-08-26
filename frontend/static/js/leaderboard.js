import { fetchLeaderboard } from "./api.js";


const elements = {
  pageTabs: document.querySelectorAll(".page-tabs button"),
  draftPage: document.getElementById("draftAssistantPage"),
  leaderboardPage: document.getElementById("heroLeaderboardPage"),
  rank: document.getElementById("leaderboardRank"),
  search: document.getElementById("leaderboardSearch"),
  meta: document.getElementById("leaderboardMeta"),
  message: document.getElementById("leaderboardMessage"),
  body: document.getElementById("leaderboardBody"),
  sortButtons: document.querySelectorAll(".leaderboard-table [data-sort]"),
};

const leaderboardState = {
  heroes: [],
  rank: "All",
  sortBy: "win_rate",
  order: "desc",
  search: "",
  loaded: false,
  requestSequence: 0,
};

function setMessage(message = "") {
  elements.message.textContent = message;
  elements.message.classList.toggle("visible", Boolean(message));
}

function createImage(hero, className) {
  const image = document.createElement("img");
  image.className = className;
  image.src = hero.image;
  image.alt = hero.hero_name;
  image.loading = "lazy";
  image.addEventListener("error", () => image.remove());
  return image;
}

function createMatchupStrip(matchups, positive) {
  const strip = document.createElement("div");
  strip.className = "matchup-strip";

  if (!matchups.length) {
    strip.classList.add("empty");
    strip.textContent = "暂无数据";
    return strip;
  }

  matchups.forEach((matchup) => {
    const image = createImage(matchup, "matchup-image");
    const advantage = Math.abs(matchup.advantage * 100).toFixed(2);
    image.title = `${matchup.hero_name} · ${positive ? "+" : "-"}${advantage}% · ${matchup.appearances.toLocaleString("zh-CN")} 场`;
    strip.append(image);
  });
  return strip;
}

function compareHeroes(left, right) {
  if (leaderboardState.sortBy === "name") {
    const comparison = left.hero_name.localeCompare(right.hero_name, "zh-CN");
    return leaderboardState.order === "desc" ? -comparison : comparison;
  }

  const leftValue = left[leaderboardState.sortBy];
  const rightValue = right[leaderboardState.sortBy];

  if (leftValue === null) return rightValue === null ? 0 : 1;
  if (rightValue === null) return -1;
  const comparison = leftValue - rightValue || left.appearances - right.appearances;
  return leaderboardState.order === "desc" ? -comparison : comparison;
}

function updateSortHeaders() {
  elements.sortButtons.forEach((button) => {
    const active = button.dataset.sort === leaderboardState.sortBy;
    const header = button.closest("th");
    const indicator = button.querySelector(".sort-indicator");
    header.setAttribute(
      "aria-sort",
      active
        ? (leaderboardState.order === "desc" ? "descending" : "ascending")
        : "none",
    );
    indicator.textContent = active
      ? (leaderboardState.order === "desc" ? "▼" : "▲")
      : "";
  });
}

function renderLeaderboard() {
  const normalizedSearch = leaderboardState.search.trim().toLowerCase();
  const heroes = leaderboardState.heroes
    .filter((hero) => (
      !normalizedSearch
      || hero.hero_name.toLowerCase().includes(normalizedSearch)
      || String(hero.hero_id) === normalizedSearch
    ))
    .sort(compareHeroes);
  elements.body.replaceChildren();

  if (!heroes.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "leaderboard-empty";
    cell.textContent = "没有匹配的英雄";
    row.append(cell);
    elements.body.append(row);
    return;
  }

  heroes.forEach((hero, index) => {
    const row = document.createElement("tr");
    const position = document.createElement("td");
    const heroCell = document.createElement("td");
    const heroIdentity = document.createElement("div");
    const heroName = document.createElement("strong");
    const heroGames = document.createElement("span");
    const pickRate = document.createElement("td");
    const winRate = document.createElement("td");
    const counters = document.createElement("td");
    const counteredBy = document.createElement("td");
    position.className = "leaderboard-position";
    position.textContent = String(index + 1).padStart(2, "0");
    heroIdentity.className = "leaderboard-hero";
    heroName.textContent = hero.hero_name;
    heroGames.textContent = `${hero.appearances.toLocaleString("zh-CN")} 场`;
    heroIdentity.append(createImage(hero, "leaderboard-hero-image"), heroName, heroGames);
    heroCell.append(heroIdentity);
    pickRate.className = "leaderboard-rate";
    pickRate.textContent = `${(hero.pick_rate * 100).toFixed(2)}%`;
    winRate.className = "leaderboard-rate win-rate";
    winRate.textContent = hero.win_rate === null
      ? "-"
      : `${(hero.win_rate * 100).toFixed(2)}%`;
    counters.append(createMatchupStrip(hero.counters, true));
    counteredBy.append(createMatchupStrip(hero.countered_by, false));
    row.append(position, heroCell, pickRate, winRate, counters, counteredBy);
    elements.body.append(row);
  });
  updateSortHeaders();
}

async function loadLeaderboard() {
  const requestSequence = ++leaderboardState.requestSequence;
  elements.body.innerHTML = '<tr><td colspan="6" class="leaderboard-empty">正在载入排行榜</td></tr>';
  setMessage();

  try {
    const payload = await fetchLeaderboard(
      elements.rank.value,
      leaderboardState.sortBy,
      leaderboardState.order,
    );

    if (requestSequence !== leaderboardState.requestSequence) return;

    leaderboardState.heroes = payload.heroes;
    leaderboardState.rank = payload.rank;
    leaderboardState.loaded = true;
    elements.meta.textContent = `${payload.rank === "All" ? "全部分段" : payload.rank} · ${payload.total_matches.toLocaleString("zh-CN")} 场比赛 · ${payload.heroes.length} 位英雄`;
    renderLeaderboard();
  } catch (error) {
    if (requestSequence !== leaderboardState.requestSequence) return;
    elements.body.innerHTML = '<tr><td colspan="6" class="leaderboard-empty">排行榜载入失败</td></tr>';
    setMessage(error.message);
  }
}

function activatePage(page) {
  const showLeaderboard = page === "hero-leaderboard";
  elements.draftPage.hidden = showLeaderboard;
  elements.leaderboardPage.hidden = !showLeaderboard;
  elements.pageTabs.forEach((button) => {
    button.classList.toggle("active", button.dataset.page === page);
  });

  if (showLeaderboard && !leaderboardState.loaded) loadLeaderboard();
}

export function initializeLeaderboard(config) {
  const allOption = document.createElement("option");
  allOption.value = "All";
  allOption.textContent = "全部";
  elements.rank.append(allOption);
  config.rank_segments.forEach((rank) => {
    const option = document.createElement("option");
    option.value = rank;
    option.textContent = rank;
    elements.rank.append(option);
  });
  elements.pageTabs.forEach((button) => {
    button.addEventListener("click", () => activatePage(button.dataset.page));
  });
  elements.rank.addEventListener("change", loadLeaderboard);
  elements.search.addEventListener("input", () => {
    leaderboardState.search = elements.search.value;
    renderLeaderboard();
  });
  elements.sortButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const sortBy = button.dataset.sort;

      if (leaderboardState.sortBy === sortBy) {
        leaderboardState.order = leaderboardState.order === "desc" ? "asc" : "desc";
      } else {
        leaderboardState.sortBy = sortBy;
        leaderboardState.order = sortBy === "name" ? "asc" : "desc";
      }

      renderLeaderboard();
    });
  });
}
