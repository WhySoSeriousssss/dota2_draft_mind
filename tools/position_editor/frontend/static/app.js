const state = {
  positions: [],
  heroes: [],
  original: new Map(),
  search: "",
  filter: "all",
};

const elements = {
  summary: document.getElementById("summary"),
  search: document.getElementById("searchInput"),
  filter: document.getElementById("positionFilter"),
  header: document.getElementById("tableHeader"),
  rows: document.getElementById("heroRows"),
  changeCount: document.getElementById("changeCount"),
  save: document.getElementById("saveButton"),
  reset: document.getElementById("resetButton"),
  message: document.getElementById("message"),
};

function normalize(positionIds) {
  return [...positionIds].sort((left, right) => left - right);
}

function samePositions(left, right) {
  return JSON.stringify(normalize(left)) === JSON.stringify(normalize(right));
}

function changedHeroes() {
  return state.heroes.filter((hero) => (
    !samePositions(hero.position_ids, state.original.get(hero.id))
  ));
}

function setMessage(message = "", type = "") {
  elements.message.textContent = message;
  elements.message.className = `message ${type}`.trim();
}

function renderSummary() {
  elements.summary.replaceChildren();
  const total = document.createElement("div");
  total.className = "summary-item";
  total.innerHTML = `<span>全部英雄</span><strong>${state.heroes.length}</strong>`;
  elements.summary.append(total);

  state.positions.forEach((position) => {
    const item = document.createElement("div");
    const count = state.heroes.filter((hero) => (
      hero.position_ids.includes(position.id)
    )).length;
    item.className = "summary-item";
    item.innerHTML = `<span>${position.name}</span><strong>${count}</strong>`;
    elements.summary.append(item);
  });
}

function renderHeader() {
  elements.header.querySelectorAll("th:not(.hero-column)").forEach((item) => item.remove());
  state.positions.forEach((position) => {
    const header = document.createElement("th");
    header.textContent = position.name;
    elements.header.append(header);
  });
}

function matchesFilter(hero) {
  if (state.filter === "all") return true;
  if (state.filter === "multi") return hero.position_ids.length > 1;
  return hero.position_ids.includes(Number(state.filter));
}

function renderRows() {
  const search = state.search.trim().toLowerCase();
  const heroes = state.heroes.filter((hero) => (
    matchesFilter(hero)
    && (
      !search
      || hero.name.toLowerCase().includes(search)
      || String(hero.id) === search
    )
  ));
  elements.rows.replaceChildren();

  heroes.forEach((hero) => {
    const row = document.createElement("tr");
    const heroCell = document.createElement("td");
    const identity = document.createElement("div");
    const image = document.createElement("img");
    const name = document.createElement("strong");
    const meta = document.createElement("span");
    row.classList.toggle(
      "row-changed",
      !samePositions(hero.position_ids, state.original.get(hero.id)),
    );
    heroCell.className = "hero-column";
    identity.className = "hero-identity";
    image.src = hero.image;
    image.alt = hero.name;
    image.loading = "lazy";
    name.textContent = hero.name;
    meta.textContent = `ID ${hero.id} · ${hero.attribute}`;
    identity.append(image, name, meta);
    heroCell.append(identity);
    row.append(heroCell);

    state.positions.forEach((position) => {
      const cell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "position-checkbox";
      checkbox.checked = hero.position_ids.includes(position.id);
      checkbox.setAttribute("aria-label", `${hero.name} ${position.name}`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          hero.position_ids = normalize([...hero.position_ids, position.id]);
        } else {
          hero.position_ids = hero.position_ids.filter((id) => id !== position.id);
        }
        renderSummary();
        updateChangeState();
        row.classList.toggle(
          "row-changed",
          !samePositions(hero.position_ids, state.original.get(hero.id)),
        );
      });
      cell.append(checkbox);
      row.append(cell);
    });
    elements.rows.append(row);
  });

  if (!heroes.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = state.positions.length + 1;
    cell.className = "loading";
    cell.textContent = "没有匹配的英雄";
    row.append(cell);
    elements.rows.append(row);
  }
}

function updateChangeState() {
  const changes = changedHeroes().length;
  elements.changeCount.textContent = changes
    ? `${changes} 位英雄有未保存修改`
    : "无未保存修改";
  elements.save.disabled = changes === 0;
  elements.reset.disabled = changes === 0;
}

function applyPayload(payload) {
  state.positions = payload.positions;
  state.heroes = payload.heroes.map((hero) => ({
    ...hero,
    position_ids: normalize(hero.position_ids),
  }));
  state.original = new Map(
    state.heroes.map((hero) => [hero.id, [...hero.position_ids]]),
  );
  renderHeader();
  renderSummary();
  renderRows();
  updateChangeState();
}

async function loadData() {
  const response = await fetch("/api/data");

  if (!response.ok) throw new Error("无法载入位置配置");

  const payload = await response.json();
  applyPayload(payload);
  state.positions.forEach((position) => {
    const option = document.createElement("option");
    option.value = position.id;
    option.textContent = position.name;
    elements.filter.append(option);
  });
}

async function saveData() {
  const heroes = Object.fromEntries(
    state.heroes.map((hero) => [String(hero.id), hero.position_ids]),
  );
  elements.save.disabled = true;
  setMessage("正在校验并保存");

  try {
    const response = await fetch("/api/data", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ heroes }),
    });
    const payload = await response.json();

    if (!response.ok) throw new Error(payload.error || "保存失败");

    applyPayload(payload);
    setMessage(
      payload.changed
        ? `保存成功，备份：${payload.backup}`
        : "配置没有变化",
      "success",
    );
  } catch (error) {
    setMessage(error.message, "error");
    updateChangeState();
  }
}

elements.search.addEventListener("input", () => {
  state.search = elements.search.value;
  renderRows();
});
elements.filter.addEventListener("change", () => {
  state.filter = elements.filter.value;
  renderRows();
});
elements.save.addEventListener("click", saveData);
elements.reset.addEventListener("click", () => {
  state.heroes.forEach((hero) => {
    hero.position_ids = [...state.original.get(hero.id)];
  });
  renderSummary();
  renderRows();
  updateChangeState();
  setMessage("已撤销未保存修改");
});

loadData().catch((error) => setMessage(error.message, "error"));
