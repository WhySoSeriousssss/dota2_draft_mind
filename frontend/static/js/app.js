import { fetchConfig, fetchRecommendations } from "./api.js";
import { initializeLeaderboard } from "./leaderboard.js";
import {
  loadDraftPreferences,
  resolveDraftPreferences,
  saveDraftPreferences,
} from "./preferences.js";
import { state } from "./state.js";

    const elements = {
      rank: document.getElementById("rankSelect"),
      positionFilter: document.getElementById("positionFilter"),
      alpha: document.getElementById("alphaInput"),
      beta: document.getElementById("betaInput"),
      gamma: document.getElementById("gammaInput"),
      alphaValue: document.getElementById("alphaValue"),
      betaValue: document.getElementById("betaValue"),
      gammaValue: document.getElementById("gammaValue"),
      allyPicks: document.getElementById("allyPicks"),
      enemyPicks: document.getElementById("enemyPicks"),
      allyCount: document.getElementById("allyCount"),
      enemyCount: document.getElementById("enemyCount"),
      heroSearch: document.getElementById("heroSearch"),
      heroPool: document.getElementById("heroPool"),
      attrFilter: document.getElementById("attrFilter"),
      calculateButton: document.getElementById("calculateButton"),
      recommendCount: document.getElementById("recommendCount"),
      resultsContainer: document.getElementById("resultsContainer"),
      resultsMeta: document.getElementById("resultsMeta"),
      messageBar: document.getElementById("messageBar"),
      dataStatus: document.getElementById("dataStatus"),
    };

    function createHeroImage(hero, className, useIcon = false) {
      const wrapper = document.createDocumentFragment();
      const image = document.createElement("img");
      const fallback = document.createElement("div");
      image.className = className;
      image.src = useIcon ? hero.icon : hero.image;
      image.alt = hero.name;
      image.loading = "lazy";
      fallback.className = className.replace("image", "fallback");
      fallback.textContent = hero.name.slice(0, 1).toUpperCase();
      fallback.hidden = true;
      image.addEventListener("error", () => {
        image.hidden = true;
        fallback.hidden = false;
      });
      wrapper.append(image, fallback);
      return wrapper;
    }

    function showError(message) {
      elements.messageBar.textContent = message;
      elements.messageBar.classList.add("visible");
    }

    function clearError() {
      elements.messageBar.textContent = "";
      elements.messageBar.classList.remove("visible");
    }

    function updateWeightLabels() {
      elements.alphaValue.value = Number(elements.alpha.value).toFixed(2);
      elements.betaValue.value = Number(elements.beta.value).toFixed(2);
      elements.gammaValue.value = Number(elements.gamma.value).toFixed(2);
    }

    function persistDraftPreferences() {
      saveDraftPreferences({
        rank: elements.rank.value,
        positionIds: state.selectedPositionIds,
        weights: {
          alpha: Number(elements.alpha.value),
          beta: Number(elements.beta.value),
          gamma: Number(elements.gamma.value),
        },
      });
    }

    function renderPositionFilter(positions) {
      elements.positionFilter.replaceChildren();

      positions.forEach((position) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        const text = document.createElement("span");
        label.className = "position-option";
        input.type = "checkbox";
        input.value = position.id;
        input.checked = state.selectedPositionIds.includes(position.id);
        text.textContent = position.name;
        input.addEventListener("change", () => {
          state.selectedPositionIds = Array.from(
            elements.positionFilter.querySelectorAll("input:checked"),
            (item) => Number(item.value),
          );
          persistDraftPreferences();
          scheduleRecommendation();
        });
        label.append(input, text);
        elements.positionFilter.append(label);
      });
    }

    function renderTeam(side) {
      const isAlly = side === "ally";
      const picks = isAlly ? state.allies : state.enemies;
      const capacity = isAlly ? 4 : 5;
      const container = isAlly ? elements.allyPicks : elements.enemyPicks;
      const counter = isAlly ? elements.allyCount : elements.enemyCount;
      container.replaceChildren();
      counter.textContent = `${picks.length} / ${capacity}`;

      for (let index = 0; index < capacity; index += 1) {
        const heroId = picks[index];

        if (heroId === undefined) {
          const empty = document.createElement("button");
          empty.type = "button";
          empty.className = "pick-slot empty";
          empty.textContent = "+";
          empty.title = isAlly ? "添加我方英雄" : "添加敌方英雄";
          empty.addEventListener("click", () => setActiveSide(side));
          container.append(empty);
          continue;
        }

        const hero = state.heroById.get(heroId);
        const slot = document.createElement("div");
        const name = document.createElement("span");
        const remove = document.createElement("button");
        slot.className = "pick-slot";
        name.className = "pick-name";
        name.textContent = hero.name;
        remove.type = "button";
        remove.className = "remove-pick";
        remove.textContent = "×";
        remove.title = `移除 ${hero.name}`;
        remove.addEventListener("click", () => removePick(side, heroId));
        slot.append(createHeroImage(hero, "pick-image", true), name, remove);
        container.append(slot);
      }
    }

    function renderTeams() {
      renderTeam("ally");
      renderTeam("enemy");
    }

    function setActiveSide(side) {
      state.activeSide = side;
      document.querySelectorAll(".side-switch button").forEach((button) => {
        button.classList.toggle("active", button.dataset.side === side);
      });
    }

    function addPick(heroId, side = state.activeSide) {
      const target = side === "ally" ? state.allies : state.enemies;
      const other = side === "ally" ? state.enemies : state.allies;
      const capacity = side === "ally" ? 4 : 5;

      if (target.includes(heroId) || other.includes(heroId)) return;

      if (target.length >= capacity) {
        showError(side === "ally" ? "我方最多选择 4 个已选英雄" : "敌方最多选择 5 个英雄");
        return;
      }

      target.push(heroId);
      clearError();
      renderTeams();
      renderHeroPool();
      scheduleRecommendation();
    }

    function removePick(side, heroId) {
      const target = side === "ally" ? state.allies : state.enemies;
      const index = target.indexOf(heroId);

      if (index >= 0) target.splice(index, 1);

      renderTeams();
      renderHeroPool();
      scheduleRecommendation();
    }

    function renderHeroPool() {
      const normalizedSearch = state.search.trim().toLowerCase();
      const selected = new Set([...state.allies, ...state.enemies]);
      const heroes = state.heroes.filter((hero) => {
        const matchesAttribute = (
          state.attribute === "all"
          || (state.attribute === "all_attr" && hero.attribute === "all")
          || hero.attribute === state.attribute
        );
        const matchesSearch = !normalizedSearch || hero.name.toLowerCase().includes(normalizedSearch) || String(hero.id) === normalizedSearch;
        return matchesAttribute && matchesSearch;
      });
      elements.heroPool.replaceChildren();

      heroes.forEach((hero) => {
        const button = document.createElement("button");
        const label = document.createElement("span");
        button.type = "button";
        button.className = "hero-tile";
        button.disabled = selected.has(hero.id);
        button.title = `${hero.name} · ID ${hero.id}`;
        label.className = "hero-tile-name";
        label.textContent = hero.name;
        button.append(createHeroImage(hero, "hero-image"), label);
        button.addEventListener("click", () => addPick(hero.id));
        elements.heroPool.append(button);
      });
    }

    function signed(value) {
      const number = Number(value);
      return `${number >= 0 ? "+" : ""}${number.toFixed(4)}`;
    }

    function contributionClass(value) {
      if (value > 0.000001) return "positive";
      if (value < -0.000001) return "negative";
      return "";
    }

    function renderResults(payload, page = 1) {
      state.recommendationResults = payload;
      const totalResults = payload.results.length;
      const totalPages = Math.max(1, Math.ceil(totalResults / state.resultsPerPage));
      state.resultPage = Math.min(Math.max(page, 1), totalPages);
      const pageStart = (state.resultPage - 1) * state.resultsPerPage;
      const pageResults = payload.results.slice(pageStart, pageStart + state.resultsPerPage);
      const tableWrap = document.createElement("div");
      const table = document.createElement("table");
      const thead = document.createElement("thead");
      const tbody = document.createElement("tbody");
      tableWrap.className = "results-table-wrap";
      table.className = "results-table";
      thead.innerHTML = `
        <tr>
          <th style="width:52px">排名</th>
          <th style="width:230px">英雄</th>
          <th>Draft Score</th>
          <th>基础胜率</th>
          <th>对位贡献</th>
          <th>协同贡献</th>
          <th>分段场次</th>
          <th style="width:54px"></th>
        </tr>`;

      pageResults.forEach((result, index) => {
        const hero = state.heroById.get(result.hero_id);
        const row = document.createElement("tr");
        const rankCell = document.createElement("td");
        const heroCell = document.createElement("td");
        const heroWrap = document.createElement("div");
        const nameWrap = document.createElement("div");
        const name = document.createElement("strong");
        const id = document.createElement("span");
        const scoreCell = document.createElement("td");
        const baseCell = document.createElement("td");
        const counterCell = document.createElement("td");
        const synergyCell = document.createElement("td");
        const gamesCell = document.createElement("td");
        const actionCell = document.createElement("td");
        const addButton = document.createElement("button");
        rankCell.className = "rank-number";
        rankCell.textContent = String(pageStart + index + 1).padStart(2, "0");
        heroWrap.className = "result-hero";
        nameWrap.className = "result-name";
        name.textContent = result.hero_name;
        id.textContent = `ID ${result.hero_id}`;
        nameWrap.append(name, id);
        heroWrap.append(createHeroImage(hero, "result-image"), nameWrap);
        heroCell.append(heroWrap);
        scoreCell.className = "numeric score-value";
        scoreCell.textContent = result.score.toFixed(4);
        baseCell.className = "numeric";
        baseCell.textContent = `${(result.base_score * 100).toFixed(2)}%`;
        counterCell.className = `numeric ${contributionClass(result.counter_component)}`;
        counterCell.textContent = signed(result.counter_component);
        synergyCell.className = `numeric ${contributionClass(result.synergy_component)}`;
        synergyCell.textContent = signed(result.synergy_component);
        gamesCell.className = "numeric";
        gamesCell.textContent = result.base_appearances.toLocaleString("zh-CN");
        addButton.type = "button";
        addButton.className = "add-result";
        addButton.textContent = "+";
        addButton.title = `将 ${result.hero_name} 加入我方`;
        addButton.disabled = state.allies.length >= 4;
        addButton.addEventListener("click", () => addPick(result.hero_id, "ally"));
        actionCell.append(addButton);
        row.append(rankCell, heroCell, scoreCell, baseCell, counterCell, synergyCell, gamesCell, actionCell);
        tbody.append(row);
      });

      table.append(thead, tbody);
      tableWrap.append(table);
      const pagination = createPagination(totalPages);
      elements.resultsContainer.replaceChildren(tableWrap, pagination);
      elements.resultsMeta.textContent = `${payload.rank} · 我方 ${state.allies.length} · 敌方 ${state.enemies.length} · Top ${totalResults}`;
    }

    function createPagination(totalPages) {
      const pagination = document.createElement("nav");
      const pageStatus = document.createElement("span");
      const previous = document.createElement("button");
      const next = document.createElement("button");
      pagination.className = "pagination";
      pagination.setAttribute("aria-label", "推荐结果分页");
      pageStatus.textContent = `${state.resultPage} / ${totalPages}`;
      previous.type = "button";
      previous.textContent = "上一页";
      previous.disabled = state.resultPage <= 1;
      previous.addEventListener("click", () => renderResults(state.recommendationResults, state.resultPage - 1));
      next.type = "button";
      next.textContent = "下一页";
      next.disabled = state.resultPage >= totalPages;
      next.addEventListener("click", () => renderResults(state.recommendationResults, state.resultPage + 1));
      pagination.append(previous, pageStatus, next);
      pagination.hidden = totalPages <= 1;
      return pagination;
    }

    async function calculateRecommendations() {
      if (!elements.rank.value) return;

      const requestSequence = ++state.requestSequence;
      elements.calculateButton.disabled = true;
      elements.calculateButton.textContent = "计算中";
      clearError();

      try {
        const payload = await fetchRecommendations({
          rank: elements.rank.value,
          allies: state.allies,
          enemies: state.enemies,
          excluded_hero_ids: state.excludedHeroIds,
          position_ids: state.selectedPositionIds,
          weights: {
            alpha: Number(elements.alpha.value),
            beta: Number(elements.beta.value),
            gamma: Number(elements.gamma.value),
          },
          top_k: Number(elements.recommendCount.value),
        });
        if (requestSequence !== state.requestSequence) return;

        renderResults(payload);
      } catch (error) {
        if (requestSequence === state.requestSequence) showError(error.message);
      } finally {
        if (requestSequence === state.requestSequence) {
          elements.calculateButton.disabled = false;
          elements.calculateButton.textContent = "计算推荐";
        }
      }
    }

    function scheduleRecommendation() {
      window.clearTimeout(state.debounceTimer);
      state.debounceTimer = window.setTimeout(calculateRecommendations, 180);
    }

    function bindEvents() {
      document.querySelectorAll(".mobile-tabs button").forEach((button) => {
        button.addEventListener("click", () => {
          const showDraft = button.dataset.view === "draft";
          document.querySelector(".draft-panel").classList.toggle("mobile-hidden", !showDraft);
          document.querySelector(".results-panel").classList.toggle("mobile-hidden", showDraft);
          document.querySelectorAll(".mobile-tabs button").forEach((item) => item.classList.toggle("active", item === button));
        });
      });
      document.querySelectorAll(".side-switch button").forEach((button) => {
        button.addEventListener("click", () => setActiveSide(button.dataset.side));
      });
      elements.attrFilter.querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
          state.attribute = button.dataset.attr;
          elements.attrFilter.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
          renderHeroPool();
        });
      });
      elements.heroSearch.addEventListener("input", () => {
        state.search = elements.heroSearch.value;
        renderHeroPool();
      });
      [elements.alpha, elements.beta, elements.gamma].forEach((input) => {
        input.addEventListener("input", () => {
          updateWeightLabels();
          persistDraftPreferences();
          scheduleRecommendation();
        });
      });
      elements.rank.addEventListener("change", () => {
        persistDraftPreferences();
        scheduleRecommendation();
      });
      elements.recommendCount.addEventListener("change", () => {
        const count = Math.min(127, Math.max(1, Number.parseInt(elements.recommendCount.value, 10) || 15));
        elements.recommendCount.value = String(count);
        scheduleRecommendation();
      });
      elements.calculateButton.addEventListener("click", calculateRecommendations);
    }

    async function initialize() {
      bindEvents();
      updateWeightLabels();

      try {
        const config = await fetchConfig();
        const preferences = resolveDraftPreferences(
          loadDraftPreferences(),
          config,
        );

        state.heroes = config.heroes;
        state.heroById = new Map(config.heroes.map((hero) => [hero.id, hero]));
        state.selectedPositionIds = preferences.positionIds;
        renderPositionFilter(config.positions);
        initializeLeaderboard(config);
        config.rank_segments.forEach((rank) => {
          const option = document.createElement("option");
          option.value = rank;
          option.textContent = rank;
          option.selected = rank === preferences.rank;
          elements.rank.append(option);
        });
        elements.alpha.value = preferences.weights.alpha;
        elements.beta.value = preferences.weights.beta;
        elements.gamma.value = preferences.weights.gamma;
        elements.recommendCount.value = config.defaults.top_k;
        elements.dataStatus.textContent = `${config.heroes.length} 位英雄 · ${config.rank_segments.length} 个分段`;
        updateWeightLabels();
        renderTeams();
        renderHeroPool();
        await calculateRecommendations();
      } catch (error) {
        elements.dataStatus.textContent = "基础数据不可用";
        elements.resultsContainer.innerHTML = '<div class="empty-results">无法载入评分数据</div>';
        showError(error.message);
      }
    }

    initialize();
