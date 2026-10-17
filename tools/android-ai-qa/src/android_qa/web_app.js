const $ = (selector) => document.querySelector(selector);
const icon = {create:"＋",move:"↗",status:"✓",delete:"×",lifecycle:"⟳",undo:"↶","empty-title":"Aa","long-title":"↔",keyboard:"⌨"};
const statusText = {passed:"ПРОЙДЕН",failed:"ОШИБКА",blocked:"БЛОКИРОВАН",not_checked:"НЕ ПРОВЕРЕН",running:"ВЫПОЛНЯЕТСЯ",queued:"В ОЧЕРЕДИ",unverified:"FLOW НЕ ПРОВЕРЕН",unknown:"НЕТ ЗАПУСКОВ",pending:"ОЖИДАЕТ"};
let state = null;
let selectedScenario = "create";
let noticeTimer;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function statusName(status) { return statusText[status] || String(status || "unknown").toUpperCase(); }
function statusClass(status) { return `status-${status || "unknown"}`; }
function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("ru-RU", {hour:"2-digit",minute:"2-digit",day:"2-digit",month:"short"}).format(date);
}
function notify(message) {
  const node = $("#notice"); node.textContent = message; node.hidden = false;
  clearTimeout(noticeTimer); noticeTimer = setTimeout(() => { node.hidden = true; }, 5000);
}

function renderScenarios() {
  const list = $("#scenario-list"); list.replaceChildren();
  const scenarios = state?.scenarios || [];
  $("#scenario-count").textContent = String(scenarios.length).padStart(2, "0");
  const activeScenario = state?.active && ["queued","running"].includes(state.active.status) ? state.active.scenario : null;
  for (const scenario of scenarios) {
    const card = el("article", `scenario-card${scenario.id === selectedScenario ? " selected" : ""}`);
    card.addEventListener("click", () => { selectedScenario = scenario.id; renderScenarios(); renderDetails(); });
    const top = el("div", "scenario-top");
    top.append(el("div", "scenario-icon", icon[scenario.id] || "•"));
    const copy = el("div", "scenario-copy");
    const titleRow = el("div", "scenario-title-row");
    titleRow.append(el("span", "scenario-title", scenario.title));
    if (scenario.primary) titleRow.append(el("span", "primary-tag", "ОСНОВНОЙ"));
    copy.append(titleRow, el("p", "scenario-desc", scenario.description)); top.append(copy); card.append(top);
    const bottom = el("div", "scenario-bottom");
    const latest = scenario.latest;
    const label = latest ? `${statusName(latest.status)} · ${formatTime(latest.started)}` : "ЕЩЁ НЕ ЗАПУСКАЛСЯ";
    bottom.append(el("span", `scenario-status ${statusClass(latest?.status || "unknown")}`, label));
    const button = el("button", "run-small", activeScenario ? (activeScenario === scenario.id ? "Выполняется…" : "Устройство занято") : "Запустить");
    button.disabled = Boolean(activeScenario);
    button.addEventListener("click", (event) => { event.stopPropagation(); startScenario(scenario.id); });
    bottom.append(button); card.append(bottom); list.append(card);
  }
}

function renderCheck(check) {
  const card = el("article", "check-card");
  const head = el("div", "check-head");
  head.append(el("span", "check-name", check.name), el("span", `scenario-status ${statusClass(check.status)}`, statusName(check.status)));
  card.append(head);
  if (check.actual) card.append(el("p", "check-body", check.actual));
  if (check.expected) card.append(el("p", "check-expected", `Ожидалось: ${check.expected}`));
  if (check.category) card.append(el("div", "check-category", `${check.category}${check.confidence === "preliminary" ? " · предварительный вывод" : ""}`));
  if (check.screenshots?.length) {
    const shots = el("div", "check-shots");
    for (const src of check.screenshots) {
      const link = el("a"); link.href = src; link.target = "_blank"; link.rel = "noreferrer";
      const image = el("img", "check-shot"); image.src = src; image.alt = `Скриншот проверки ${check.name}`; image.loading = "lazy";
      link.append(image); shots.append(link);
    }
    card.append(shots);
  }
  return card;
}

function renderDetails() {
  const panel = $("#detail");
  if (!state) return;
  const active = state.active && ["queued","running"].includes(state.active.status) ? state.active : null;
  const scenario = state.scenarios.find((item) => item.id === selectedScenario) || state.scenarios[0];
  if (!scenario) return;
  const report = active?.scenario === scenario.id ? state.active_report : scenario.latest;
  panel.replaceChildren();
  const head = el("div", "detail-head");
  const text = el("div"); text.append(el("h2", "detail-title", scenario.title), el("div", "detail-subtitle", report?.id ? `RUN ${report.id}` : "RUN DETAILS"));
  head.append(text, el("span", `status-badge ${statusClass(active?.scenario === scenario.id ? active.status : report?.status)}`, statusName(active?.scenario === scenario.id ? active.status : report?.status || "unknown")));
  panel.append(head);
  if (!report && !active) {
    panel.append(el("p", "check-body", "Этот сценарий ещё не запускался. Нажмите «Запустить», чтобы начать проверку."));
    return;
  }
  const progress = report?.progress || {done:0,total:0};
  const percent = progress.total ? Math.round(progress.done / progress.total * 100) : 0;
  const progressWrap = el("div", "progress-wrap");
  const progressMeta = el("div", "progress-meta");
  progressMeta.append(el("span", "", "ПРОГРЕСС ПРОВЕРКИ"), el("strong", "", `${progress.done || 0} / ${progress.total || 0}`));
  const track = el("div", "progress-track"); const value = el("div", "progress-value"); value.style.width = `${percent}%`; track.append(value);
  progressWrap.append(progressMeta, track);
  if (progress.current || progress.action) {
    const action = el("div", "current-action");
    action.append(document.createTextNode("Сейчас: "));
    action.append(el("b", "", progress.current || "подготовка"));
    if (progress.action) action.append(document.createTextNode(` · ${progress.action}${progress.target ? ` · ${progress.target}` : ""}`));
    progressWrap.append(action);
  } else if (active) progressWrap.append(el("div", "current-action", "Подключение к устройству и подготовка сценария…"));
  panel.append(progressWrap);

  if (report?.checkpoints?.length) {
    const section = el("section"); const sub = el("div", "subhead"); sub.append(el("h3", "", "Этапы сценария"), el("span", "", "CHECKPOINTS")); section.append(sub);
    const points = el("div", "checkpoint-list");
    for (const point of report.checkpoints) {
      const row = el("div", `checkpoint${point.done ? " done" : ""}${["failed","blocked"].includes(point.status) ? ` ${point.status}` : ""}`);
      row.append(el("span", "checkpoint-mark", point.done ? (point.status === "passed" ? "✓" : "!") : "·"), el("span", "", point.name)); points.append(row);
    }
    section.append(points); panel.append(section);
  }

  if (report?.errors?.length) {
    const section = el("section"); const sub = el("div", "subhead"); sub.append(el("h3", "", "Ошибки и остановки"), el("span", "", String(report.errors.length).padStart(2,"0"))); section.append(sub);
    for (const error of report.errors) {
      const box = el("div", "error-card"); box.append(el("div", "error-title", `${error.name} · ${statusName(error.status)}`), el("div", "", error.actual));
      if (error.screenshots?.length) {
        const shots = el("div", "check-shots");
        for (const src of error.screenshots) {
          const link = el("a"); link.href = src; link.target = "_blank"; link.rel = "noreferrer";
          const image = el("img", "check-shot"); image.src = src; image.alt = `Скриншот ошибки ${error.name}`; image.loading = "lazy";
          link.append(image); shots.append(link);
        }
        box.append(shots);
      }
      section.append(box);
    }
    panel.append(section);
  }

  if (report?.checks?.length) {
    const section = el("section"); const sub = el("div", "subhead"); sub.append(el("h3", "", "Результаты проверок"), el("span", "", `${report.checks.length} CHECKS`)); section.append(sub);
    const checks = el("div", "checks"); report.checks.forEach((check) => checks.append(renderCheck(check))); section.append(checks); panel.append(section);
  }
  if (report?.id) {
    const link = el("a", "report-link", `ОТЧЁТ RUN ${report.id}`);
    link.href = `/api/runs/${encodeURIComponent(report.id)}/report`; link.target = "_blank"; link.rel = "noreferrer";
    panel.append(link);
  }
}

async function refresh() {
  try {
    const response = await fetch("/api/state", {cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state = await response.json();
    $("#device-label").textContent = `${state.device || "device"} · ${state.app_id || "app"}`;
    $("#footer-app").textContent = `APP ID · ${state.app_id || "—"}`;
    if (!state.scenarios.some((item) => item.id === selectedScenario)) selectedScenario = state.scenarios[0]?.id || "create";
    renderScenarios(); renderDetails();
  } catch (error) {
    $("#device-label").textContent = "сервер недоступен";
    notify(`Не удалось получить состояние: ${error.message}`);
  }
}

async function startScenario(scenario) {
  try {
    selectedScenario = scenario;
    const response = await fetch("/api/runs", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    await refresh();
  } catch (error) { notify(error.message); }
}

refresh();
setInterval(refresh, 1800);
