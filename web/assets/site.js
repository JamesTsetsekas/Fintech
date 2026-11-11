const appState = {
  manifest: null,
  payloadCache: new Map(),
  signals: [],
  activeChartId: null,
  chartRequest: null,
  currentChart: null,
  currentPayload: null,
  chartOptions: {
    movingAverage: false,
    halvings: false,
    grid: true,
    table: false,
    scale: null,
    signalView: false,
    rangePayload: null,
    rangeTransition: null,
    range: "all",
    customRange: null,
    touchMode: "inspect",
  },
  sectionFilter: "",
  lastSearchResultCount: 0,
};

const initialParams = new URLSearchParams(window.location.search);
const pageConfig = {
  view: document.body.dataset.view || "dashboard",
  manifestPath: document.body.dataset.manifest || "web/data/bitcoin/site-manifest.json",
  assetPrefix: document.body.dataset.assetPrefix || "",
};

const POPULAR_IDS = [
  "pb-various",
  "ohlc",
  "nupl",
  "pi-cycle-top",
  "mvrv-z-score",
  "circulating-supply",
  "difficulty",
  "pb-realized-prices",
];

// The signal list, the scoring method and the Cycle Index membership live in
// one place: web/assets/signal-definitions.json. The site build scores them
// into signals.json; the browser re-computes them from chart payloads only
// when that artifact is missing or invalid.
const SIGNAL_DEFINITIONS_PATH = "web/assets/signal-definitions.json";
const SIGNALS_ARTIFACT_NAME = "signals.json";
const SIGNALS_ARTIFACT_SCHEMA = 1;
const DEFAULT_SIGNAL_PHASES = [
  { key: "bottom", label: "Bottom", below: 25 },
  { key: "bearish", label: "Bearish", below: 50 },
  { key: "bullish", label: "Bullish", below: 75 },
  { key: "top", label: "Top", below: null },
];
const ALERT_RULES_KEY = "fintech-alerts-v1";
const ALERT_SEEN_KEY = "fintech-alerts-seen-v1";
const alertSession = { seenAt: "", fired: new Set() };

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindTheme();
  bindKeyboardSearch();
  try {
    appState.manifest = await fetchJson(pageConfig.manifestPath);
    renderSidebar();
    if (pageConfig.view === "dashboard") await renderDashboard();
    if (pageConfig.view === "charts") await renderChartTerminal();
    if (pageConfig.view === "signals") await renderSignalsPage();
    if (pageConfig.view === "alerts") await renderAlertsPage();
    else void checkAlertsInBackground();
  } catch (error) {
    renderFatalError(error);
  }
}

function bindTheme() {
  document.querySelectorAll(".theme-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("fintech-theme", next);
      document.dispatchEvent(new CustomEvent("fintech-theme-change"));
    });
  });
}

function setLibraryOpen(open, restoreFocus = false) {
  const button = document.querySelector("#library-toggle");
  const sidebar = document.querySelector(".library-sidebar");
  button?.setAttribute("aria-expanded", String(open));
  sidebar?.classList.toggle("library-open", open);
  if (restoreFocus) button?.focus();
}

function bindKeyboardSearch() {
  const search = document.querySelector("#sidebar-search");
  if (!search) return;
  const button = document.querySelector("#library-toggle");
  button?.addEventListener("click", () => setLibraryOpen(button.getAttribute("aria-expanded") !== "true"));
  search.addEventListener("focus", () => setLibraryOpen(true));
  search.addEventListener("input", () => {
    setLibraryOpen(true);
    renderSidebar();
    announceStatus(librarySearchStatus(), 450);
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      const first = search.value.trim() ? document.querySelector("#all-chart-list .sidebar-chart-link[data-chart-id]") : null;
      if (!first) return;
      event.preventDefault();
      first.click();
    } else if (event.key === "ArrowDown") {
      const links = libraryResultLinks();
      if (!links.length) return;
      event.preventDefault();
      setLibraryOpen(true);
      links[0].focus();
    } else if (event.key === "Escape" && search.value) {
      // Clear first; a second Escape closes the mobile library as before.
      event.preventDefault();
      event.stopPropagation();
      search.value = "";
      renderSidebar();
      announceStatus(librarySearchStatus());
    }
  });
  const results = document.querySelector("#library-results");
  results?.addEventListener("keydown", (event) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const links = libraryResultLinks();
    const index = links.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    if (event.key === "ArrowUp" && index === 0) search.focus();
    else if (event.key === "Home") links[0].focus();
    else if (event.key === "End") links.at(-1).focus();
    else links[clamp(index + (event.key === "ArrowDown" ? 1 : -1), 0, links.length - 1)].focus();
  });
  document.querySelector("#section-filters")?.addEventListener("click", (event) => {
    const chip = event.target.closest?.("[data-section]");
    if (!chip || chip.disabled) return;
    const key = chip.dataset.section;
    appState.sectionFilter = key && key !== appState.sectionFilter ? key : "";
    renderSidebar();
    document.querySelector(`#section-filters [data-section="${CSS.escape(appState.sectionFilter)}"]`)?.focus();
    if (pageConfig.view === "charts") syncTerminalUrl();
    announceStatus(librarySearchStatus());
  });
  document.querySelector(".library-sidebar")?.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && window.matchMedia("(max-width: 820px)").matches) {
      event.preventDefault();
      setLibraryOpen(false, true);
    }
  });
  document.addEventListener("keydown", (event) => {
    const target = document.activeElement;
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName) && !target?.isContentEditable) {
      event.preventDefault();
      setLibraryOpen(true);
      search.focus();
    }
  });
}

function readPinnedCharts() {
  try {
    const value = JSON.parse(localStorage.getItem("fintech-pins") || "[]");
    const validIds = new Set((appState.manifest?.charts || []).map(chart => chart.id));
    return new Set(Array.isArray(value) ? value.filter(id => typeof id === "string" && validIds.has(id)) : []);
  } catch {
    return new Set();
  }
}

// A section filter should not hide that the search matched elsewhere.
function elsewhereMatchText(total) {
  const section = terminalSections().find((item) => item.key === appState.sectionFilter);
  if (!section || !total) return "";
  return `No ${escapeHtml(section.name)} charts match. ${total} ${total === 1 ? "match is" : "matches are"} in other sections; choose All to see ${total === 1 ? "it" : "them"}.`;
}

function libraryResultLinks() {
  return [...(document.querySelectorAll("#library-results .sidebar-chart-link[data-chart-id]") || [])];
}

function librarySearchStatus() {
  const query = document.querySelector("#sidebar-search")?.value.trim() || "";
  const section = terminalSections().find((item) => item.key === appState.sectionFilter);
  const count = Number(document.querySelector("#all-count")?.textContent) || 0;
  if (!query && !section) return `Showing all ${count} charts`;
  const prefix = section ? `${section.name} ` : "";
  const suffix = query ? ` “${query}”` : "";
  if (!count) {
    const elsewhere = section ? appState.lastSearchResultCount || 0 : 0;
    return `No ${prefix}charts match${suffix}${elsewhere ? `; ${elsewhere} in other sections` : ""}`;
  }
  return count === 1 ? `1 ${prefix}chart matches${suffix}` : `${count} ${prefix}charts match${suffix}`;
}

// Small vocabulary bridge for common on-chain abbreviations. Each query word
// must match (AND), but a word may match any of its listed alternatives.
const SEARCH_ALIASES = {
  sth: ["short term", "sts"],
  sts: ["short term", "sth"],
  lth: ["long term", "lts"],
  lts: ["long term", "lth"],
  mvrv: ["market value to realized value"],
  nupl: ["net unrealized profit loss"],
  zscore: ["z score"],
  realized: ["realised"],
  realised: ["realized"],
  s2f: ["stock to flow"],
  ath: ["all time high"],
  ma: ["moving average"],
  utxo: ["utxos"],
};

function normalizeSearchText(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const boilerplateDescriptionCache = new WeakMap();

function boilerplateDescriptions(charts) {
  if (!Array.isArray(charts)) return new Set();
  if (boilerplateDescriptionCache.has(charts)) return boilerplateDescriptionCache.get(charts);
  const counts = new Map();
  charts.forEach((chart) => {
    const key = normalizeSearchText(chart?.description);
    if (key) counts.set(key, (counts.get(key) || 0) + 1);
  });
  // A description shared by several charts describes the import pipeline,
  // not the chart, so it should never make every imported chart match.
  const boilerplate = new Set([...counts].filter(([, count]) => count >= 3).map(([key]) => key));
  boilerplateDescriptionCache.set(charts, boilerplate);
  return boilerplate;
}

function searchCharts(charts, query) {
  const list = Array.isArray(charts) ? charts : [];
  const terms = normalizeSearchText(query).split(" ").filter(Boolean)
    .map((term) => [...new Set([term, ...(Object.hasOwn(SEARCH_ALIASES, term) ? SEARCH_ALIASES[term] : [])])]);
  const byTitle = (a, b) => String(a.title).localeCompare(String(b.title));
  if (!terms.length) return [...list].sort(byTitle);
  const boilerplate = boilerplateDescriptions(list);
  const phrase = normalizeSearchText(query);
  return list.map((chart) => {
    const description = normalizeSearchText(chart.description);
    const fields = [
      [` ${normalizeSearchText(chart.title)}`, 10],
      [` ${normalizeSearchText(chart.section)} ${normalizeSearchText(chart.section_id)}`, 4],
      [` ${normalizeSearchText(Array.isArray(chart.tags) ? chart.tags.join(" ") : chart.tags)}`, 4],
      [boilerplate.has(description) ? "" : ` ${description}`, 1],
    ];
    let score = 0;
    let titleTerms = 0;
    for (const alternatives of terms) {
      const weight = Math.max(0, ...fields.map(([text, value]) => (
        alternatives.some((alternative) => text.includes(` ${alternative}`)) ? value : 0
      )));
      if (!weight) return null;
      score += weight;
      if (weight === 10) titleTerms += 1;
    }
    const title = normalizeSearchText(chart.title);
    if (title.startsWith(phrase)) score += 6;
    else if (` ${title}`.includes(` ${phrase}`)) score += 3;
    return { chart, score, allInTitle: titleTerms === terms.length };
  }).filter(Boolean)
    .sort((a, b) => Number(b.allInTitle) - Number(a.allInTitle) || b.score - a.score || byTitle(a.chart, b.chart))
    .map((result) => result.chart);
}

function chartSectionKey(chart) {
  return String(chart?.section_id || normalizeSearchText(chart?.section).replaceAll(" ", "-") || "");
}

function terminalSections() {
  const charts = appState.manifest?.charts || [];
  const listed = Array.isArray(appState.manifest?.sections) ? appState.manifest.sections : [];
  const sections = listed.filter((section) => section?.id).map((section) => ({ key: String(section.id), name: String(section.name || section.id) }));
  charts.forEach((chart) => {
    const key = chartSectionKey(chart);
    if (key && !sections.some((section) => section.key === key)) sections.push({ key, name: String(chart.section || key) });
  });
  return sections;
}

function renderSectionFilters(results) {
  const node = document.querySelector("#section-filters");
  if (!node) return;
  const counts = new Map();
  results.forEach((chart) => counts.set(chartSectionKey(chart), (counts.get(chartSectionKey(chart)) || 0) + 1));
  const chips = [{ key: "", name: "All", count: results.length }, ...terminalSections().map((section) => ({ ...section, count: counts.get(section.key) || 0 }))];
  node.innerHTML = chips.map(({ key, name, count }) => {
    const active = (appState.sectionFilter || "") === key;
    return `<button type="button" class="section-chip${active ? " active" : ""}" data-section="${escapeHtml(key)}" aria-pressed="${active}"${!count && !active ? " disabled" : ""}>${escapeHtml(name)} <span aria-label="${count} charts">${count}</span></button>`;
  }).join("");
}

function renderSidebar(query = document.querySelector("#sidebar-search")?.value || "") {
  if (!appState.manifest) return;
  const results = searchCharts(appState.manifest.charts, query);
  appState.lastSearchResultCount = results.length;
  renderSectionFilters(results);
  const charts = appState.sectionFilter
    ? results.filter((chart) => chartSectionKey(chart) === appState.sectionFilter)
    : results;
  const ranked = Boolean(normalizeSearchText(query));
  const allHeading = document.querySelector("#all-heading");
  if (allHeading) allHeading.textContent = ranked ? "Best matches" : "All charts";
  const selectedPopular = POPULAR_IDS.map((id) => charts.find((chart) => chart.id === id)).filter(Boolean);
  const popularLayer = selectedPopular.length ? selectedPopular : charts.slice(0, 8);
  const allList = document.querySelector("#all-chart-list");
  const popularList = document.querySelector("#popular-list");
  if (!allList || !popularList) return;

  const focusedLink = document.activeElement?.closest?.(".sidebar-chart-link[data-chart-id]");
  const focusedChartId = focusedLink?.dataset.chartId;
  const focusedListId = focusedLink?.parentElement?.id;
  const pins = readPinnedCharts();
  const pinnedCharts = charts.filter(chart => pins.has(chart.id));
  const pinnedList = document.querySelector("#pinned-list");
  if (pinnedList) {
    pinnedList.innerHTML = pinnedCharts.map(sidebarChartLink).join("") || `<p class="empty-state">${query ? "No pinned charts match this search." : "Pin a chart from its toolbar to keep it here."}</p>`;
    document.querySelector("#pinned-count").textContent = String(pinnedCharts.length);
  }
  popularList.classList.remove("skeleton-list");
  allList.classList.remove("skeleton-list");
  popularList.innerHTML = popularLayer.length
    ? popularLayer.map((chart) => sidebarChartLink(chart)).join("")
    : `<p class="empty-state">No popular charts match.</p>`;

  let lastLetter = "";
  allList.innerHTML = charts.map((chart) => {
    if (ranked) return sidebarChartLink(chart);
    const letter = chart.title.charAt(0).toUpperCase();
    const heading = letter !== lastLetter
      ? `<div class="sidebar-section-label" data-letter="${escapeHtml(letter)}"><span class="visually-hidden">Charts beginning with ${escapeHtml(letter)}</span></div>`
      : "";
    lastLetter = letter;
    return `${heading}${sidebarChartLink(chart)}`;
  }).join("") || `<p class="empty-state">${elsewhereMatchText(results.length) || "No charts match this search."}</p>`;

  document.querySelector("#popular-count").textContent = String(popularLayer.length);
  document.querySelector("#all-count").textContent = String(charts.length);
  if (pageConfig.view === "charts") document.querySelectorAll(".sidebar-chart-link[data-chart-id]").forEach(bindChartLink);
  if (focusedChartId && focusedListId) {
    document.querySelector(`#${CSS.escape(focusedListId)} [data-chart-id="${CSS.escape(focusedChartId)}"]`)?.focus({ preventScroll: true });
  }
}

function sidebarChartLink(chart) {
  const href = pageConfig.assetPrefix
    ? `${pageConfig.assetPrefix}charts/?chart=${encodeURIComponent(chart.id)}`
    : `charts/?chart=${encodeURIComponent(chart.id)}`;
  return `
    <a class="sidebar-chart-link ${chart.id === appState.activeChartId ? "active" : ""}" href="${href}" data-chart-id="${escapeHtml(chart.id)}" ${chart.id === appState.activeChartId ? 'aria-current="page"' : ""}>
      <span>${escapeHtml(chart.title)}</span>
      ${chart.kind === "interactive" ? `<span class="pin-mark" aria-hidden="true" title="Interactive chart">◔</span>` : ""}
    </a>
  `;
}

async function renderDashboard() {
  const renderCharts = () => renderDashboardCharts().catch((error) => console.warn("Dashboard charts unavailable", error));
  document.addEventListener("fintech-theme-change", renderCharts);
  const charts = renderCharts();
  renderFreshness(document.querySelector("#dashboard-updated"), null);
  void loadSignalState().then(async (state) => {
    renderFreshness(document.querySelector("#dashboard-updated"), state);
    await Promise.allSettled([
      Promise.resolve().then(() => renderMetricRibbon(state)),
      Promise.resolve().then(() => renderSignalHeatmap(document.querySelector("#dashboard-signal-heatmap"), buildDashboardSignalSet(state), 92, { startDate: "2012-01-01" })),
    ]);
  }).catch((error) => console.warn("Dashboard signals unavailable", error));
  await charts;
}

function renderMetricRibbon(state = appState.signalState) {
  const ribbon = document.querySelector("#metric-ribbon");
  if (!ribbon || !state) return;
  const market = state.market;
  const composite = state.composite;
  const members = state.signals.filter((signal) => signal.composite);
  const price = toFiniteNumber(market?.price);
  const change30 = toFiniteNumber(market?.change30dPct);
  const distance = toFiniteNumber(market?.distance200dPct);
  const supplySignal = state.signals.find((signal) => signal.id === "supply-profit");
  const supplyValue = toFiniteNumber(supplySignal?.rawValue);
  const supplyChange30 = rawSignalDelta(supplySignal, 30);
  const supplyHistory = recentSignalValues(supplySignal, 45);
  const cycleIndex = toFiniteNumber(composite?.score);
  const bullishCount = members.filter((signal) => signal.score >= 50).length;
  const phases = phaseCounts(members);
  const share = (count) => (members.length ? count / members.length * 100 : 0);
  const membership = composite
    ? `${composite.membersUsed === composite.membersTotal ? composite.membersTotal : `${composite.membersUsed} of ${composite.membersTotal}`} signals · equal weight`
    : "";

  ribbon.innerHTML = `
    <article class="terminal-metric has-sparkline">
      <span class="terminal-metric-label">Bitcoin price</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${Number.isFinite(price) ? formatUsd(price) : "Unavailable"}</strong>
        <span class="terminal-metric-change ${change30 < 0 ? "negative" : ""}">${Number.isFinite(change30) ? `${change30 < 0 ? "↘" : "↗"} ${signed(change30)} 30d` : ""}</span>
      </div>
      ${Number.isFinite(price) ? sparklineSvg((market.recentPrices || []).slice(-45)) : ""}
    </article>
    <article class="terminal-metric has-sparkline">
      <span class="terminal-metric-label">Supply in profit</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${Number.isFinite(supplyValue) ? `${supplyValue.toFixed(1)}%` : "Unavailable"}</strong>
        <span class="terminal-metric-change ${supplyChange30 < 0 ? "negative" : ""}">${Number.isFinite(supplyChange30) ? `${supplyChange30 < 0 ? "↘" : "↗"} ${supplyChange30 >= 0 ? "+" : ""}${supplyChange30.toFixed(1)}pp 30d` : ""}</span>
      </div>
      ${Number.isFinite(supplyValue) ? sparklineSvg(supplyHistory) : ""}
    </article>
    <article class="terminal-metric has-sparkline wide-only-metric">
      <span class="terminal-metric-label">Price vs 200D</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${Number.isFinite(distance) ? signed(distance) : "Unavailable"}</strong>
        <span class="terminal-metric-change ${distance < 0 ? "negative" : ""}">${Number.isFinite(distance) ? (distance >= 0 ? "above trend" : "below trend") : ""}</span>
      </div>
      ${Number.isFinite(distance) ? sparklineSvg((market.recentRatios || []).slice(-45)) : ""}
    </article>
    <article class="terminal-metric" title="${escapeHtml(membership ? `Cycle Index: ${membership}, scoring method v${state.method?.version ?? "?"}` : "")}">
      <span class="terminal-metric-label">Cycle index</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${Number.isFinite(cycleIndex) ? Math.round(cycleIndex) : "—"}</strong>
        <span class="metric-phase">${Number.isFinite(cycleIndex) ? phaseFor(cycleIndex).label : "Unavailable"}</span>
      </div>
      <div class="metric-bar" aria-hidden="true"><span style="width:25%"></span><span style="width:25%"></span><span style="width:25%"></span><span style="width:25%"></span></div>
    </article>
    <article class="terminal-metric" title="Cycle Index signals scoring 50 or higher">
      <span class="terminal-metric-label">Signal breadth</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${bullishCount}</strong>
        <span class="terminal-metric-change">/ ${members.length} bullish</span>
      </div>
      <div class="metric-bar" aria-label="${phaseCountLabel(phases)}">
        <span style="width:${share(phases.bottom)}%"></span>
        <span style="width:${share(phases.bearish)}%"></span>
        <span style="width:${share(phases.bullish)}%"></span>
        <span style="width:${share(phases.top)}%"></span>
      </div>
    </article>
  `;
}

async function renderDashboardCharts() {
  const grid = document.querySelector("#dashboard-chart-grid");
  const chartIds = POPULAR_IDS.filter((id) => chartById(id));
  grid.innerHTML = chartIds.map((id) => {
    const chart = chartById(id);
    const title = chart?.title || id;
    const href = `charts/?chart=${encodeURIComponent(id)}${id === "mvrv-z-score" ? "&signals=1" : ""}`;
    return `
      <article class="dashboard-chart-card">
        <div class="dashboard-card-heading">
          <a class="dashboard-card-title" href="${href}">${escapeHtml(title)}</a>
          <a class="dashboard-card-menu" href="${href}" aria-label="Open ${escapeHtml(title)}">•••</a>
        </div>
        <div id="dashboard-plot-${escapeHtml(id)}" class="dashboard-mini-plot loading-block"></div>
      </article>
    `;
  }).join("");

  await Promise.all(chartIds.map(async (id) => {
    const target = document.querySelector(`#dashboard-plot-${CSS.escape(id)}`);
    try {
      const payload = await getPayload(id);
      target.classList.remove("loading-block");
      const showHalvings = payload.show_halvings_default || ["pi-cycle-top", "200-dma-200-wma"].includes(payload.id);
      await renderPlot(target, payload, {
        compact: true,
        maxPoints: 600,
        signalView: id === "mvrv-z-score",
        layout: showHalvings ? halvingOverlayLayout(payload) : undefined,
      });
    } catch (error) {
      target.classList.remove("loading-block");
      target.innerHTML = `<p class="error-state">${escapeHtml(error.message)}</p>`;
    }
  }));
}

async function renderChartTerminal() {
  bindChartToolbar();
  document.querySelectorAll(".sidebar-chart-link[data-chart-id]").forEach(bindChartLink);
  void loadSignalState().then(() => {
    updateChartAlertLink();
    if (appState.currentPayload) updateChartPhase(appState.currentPayload);
  }).catch((error) => console.warn("Chart signals unavailable", error));
  document.addEventListener("fintech-theme-change", () => {
    if (appState.currentPayload && !appState.chartOptions.table) {
      void Promise.resolve().then(() => renderTerminalPlot()).catch((error) => console.warn("Chart theme update unavailable", error));
    }
  });
  window.addEventListener?.("popstate", () => {
    void restoreTerminalFromUrl().catch((error) => console.warn("Chart history unavailable", error));
  });
  updateTouchModeControls();
  await restoreTerminalFromUrl();
}

// Resolves the chart and options named in the current URL. Used for the first
// render and for Back/Forward, so a copied link and history entries reopen the
// same view. Unknown ids show a visible notice instead of a silent fallback.
async function restoreTerminalFromUrl() {
  const state = parseTerminalUrlState(window.location?.search || "");
  const sectionKeys = terminalSections().map((section) => section.key);
  const nextSection = sectionKeys.includes(state.section) ? state.section : "";
  if (nextSection !== appState.sectionFilter) {
    appState.sectionFilter = nextSection;
    renderSidebar();
  }
  const charts = appState.manifest?.charts || [];
  const requested = state.chart ? chartById(state.chart) : null;
  const firstInteractive = charts.find((chart) => chart.kind === "interactive" && chart.data_path);
  const chart = requested
    || charts.find((item) => item.id === POPULAR_IDS[0])
    || firstInteractive
    || charts[0];
  if (!chart) return;
  const notice = state.chart && !requested
    ? `Chart “${state.chart}” isn’t in the library. Showing ${chart.title} instead.`
    : "";
  await selectTerminalChart(chart.id, {
    updateUrl: false,
    signalView: Boolean(requested && state.signals),
    restore: requested ? state : null,
    notice,
  });
}

const TERMINAL_RANGES = ["1m", "3m", "6m", "ytd", "1y", "4y", "all"];
const TERMINAL_URL_KEYS = ["chart", "signals", "range", "from", "to", "scale", "ma", "halvings", "grid", "view", "section", "market"];

function parseTerminalUrlState(search) {
  const params = new URLSearchParams(search || "");
  const dateParam = (key) => {
    const value = params.get(key) || "";
    return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(new Date(`${value}T00:00:00Z`).getTime()) ? value : null;
  };
  let from = dateParam("from");
  let to = dateParam("to");
  if (!from || !to) from = to = null;
  else if (from > to) [from, to] = [to, from];
  const halvings = params.get("halvings");
  return {
    chart: params.get("chart") || null,
    signals: params.get("signals") === "1",
    range: !from && TERMINAL_RANGES.includes(params.get("range")) ? params.get("range") : null,
    from,
    to,
    scale: ["log", "linear"].includes(params.get("scale")) ? params.get("scale") : null,
    movingAverage: params.get("ma") === "1",
    halvings: halvings === "1" ? true : halvings === "0" ? false : null,
    grid: params.get("grid") !== "0",
    view: params.get("view") === "sheet" ? "sheet" : "chart",
    section: params.get("section") || "",
  };
}

function terminalOptionDefaults(payload) {
  return {
    halvings: Boolean(payload?.show_halvings_default || ["pi-cycle-top", "200-dma-200-wma"].includes(payload?.id)),
    scale: payload?.default_scale || payload?.layout?.yaxis?.type || "linear",
  };
}

function terminalUrlState() {
  const options = appState.chartOptions;
  const payload = appState.currentPayload;
  const defaults = payload ? terminalOptionDefaults(payload) : null;
  return {
    chart: appState.activeChartId || appState.currentChart?.id || null,
    signals: Boolean(options.signalView),
    range: options.customRange ? null : options.range,
    from: options.customRange?.[0] || null,
    to: options.customRange?.[1] || null,
    scale: defaults && payload.allow_scale_toggle && options.scale && options.scale !== defaults.scale ? options.scale : null,
    movingAverage: Boolean(options.movingAverage),
    halvings: defaults && payload.x_value_type === "date" && options.halvings !== defaults.halvings ? options.halvings : null,
    grid: options.grid !== false,
    view: options.table ? "sheet" : "chart",
    section: appState.sectionFilter || "",
  };
}

function terminalUrl(state, href) {
  const url = new URL(href);
  TERMINAL_URL_KEYS.forEach((key) => url.searchParams.delete(key));
  if (state.chart) url.searchParams.set("chart", state.chart);
  if (state.signals) url.searchParams.set("signals", "1");
  if (state.from && state.to) {
    url.searchParams.set("from", state.from);
    url.searchParams.set("to", state.to);
  } else if (state.range && state.range !== "all") url.searchParams.set("range", state.range);
  if (state.scale) url.searchParams.set("scale", state.scale);
  if (state.movingAverage) url.searchParams.set("ma", "1");
  if (typeof state.halvings === "boolean") url.searchParams.set("halvings", state.halvings ? "1" : "0");
  if (state.grid === false) url.searchParams.set("grid", "0");
  if (state.view === "sheet") url.searchParams.set("view", "sheet");
  if (state.section) url.searchParams.set("section", state.section);
  return url;
}

function terminalHistory() {
  // Tests and embedded previews may only expose a partial window object.
  return typeof history !== "undefined" ? history : window.history;
}

// Chart changes push a history entry; option, range, and drag updates replace
// the current one so Back returns to the previous chart rather than every zoom.
function syncTerminalUrl({ push = false } = {}) {
  const historyApi = terminalHistory();
  const href = window.location?.href;
  if (!historyApi?.replaceState || !href) return;
  let url;
  try {
    url = terminalUrl(terminalUrlState(), href);
  } catch {
    return;
  }
  if (url.href === href) return;
  const state = { fintechChart: appState.activeChartId || null };
  if (push && typeof historyApi.pushState === "function") historyApi.pushState(state, "", url);
  else historyApi.replaceState(state, "", url);
}

function queryNode(selector) {
  return typeof document.querySelector === "function" ? document.querySelector(selector) : null;
}

let statusTimer = 0;

// The page has a single polite status line. Lists and the chart canvas are not
// live regions, so typing or redrawing does not re-read hundreds of links.
function announceStatus(message, delay = 0) {
  const node = queryNode("#terminal-status");
  if (!node) return;
  if (statusTimer && typeof window.clearTimeout === "function") window.clearTimeout(statusTimer);
  statusTimer = 0;
  if (!delay || typeof window.setTimeout !== "function") {
    node.textContent = message;
    return;
  }
  statusTimer = window.setTimeout(() => {
    statusTimer = 0;
    node.textContent = message;
  }, delay);
}

function terminalRangeLabel() {
  const options = appState.chartOptions;
  if (options.customRange) return `${formatDate(new Date(`${options.customRange[0]}T00:00:00Z`))} to ${formatDate(new Date(`${options.customRange[1]}T00:00:00Z`))}`;
  if (!options.range) return "zoomed";
  if (options.range === "all") return "all history";
  return `${options.range.toUpperCase()} range`;
}

function announceChartStatus() {
  if (!appState.currentChart) return;
  announceStatus(`Showing ${appState.currentChart.title}, ${terminalRangeLabel()}${appState.chartOptions.table ? ", data sheet" : ""}`);
}

function showChartNotice(message) {
  const node = queryNode("#chart-notice");
  if (!node) return;
  node.textContent = message || "";
  node.hidden = !message;
}

function setPressed(node, pressed) {
  if (!node) return;
  node.classList?.toggle?.("active", Boolean(pressed));
  node.setAttribute?.("aria-pressed", String(Boolean(pressed)));
}

function updateRangeButtons() {
  const active = appState.chartOptions.customRange ? null : (appState.chartOptions.range || null);
  document.querySelectorAll("[data-range]").forEach((button) => setPressed(button, button.dataset.range === active));
}

function updateToolbarPressedStates() {
  const options = appState.chartOptions;
  setPressed(queryNode('[data-chart-action="moving-average"]'), options.movingAverage);
  setPressed(queryNode('[data-chart-action="halvings"]'), options.halvings);
  setPressed(queryNode('[data-chart-action="grid"]'), options.grid);
  setPressed(queryNode('[data-chart-action="table"]'), options.table);
  updateRangeButtons();
}

function bindChartLink(link) {
  if (link.dataset.chartBound) return;
  link.dataset.chartBound = "true";
  link.addEventListener("click", (event) => {
    if (event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (link.classList.contains("related-chart-link")) {
      void selectTerminalChart(link.dataset.chartId);
      document.querySelector(".chart-workspace")?.scrollIntoView?.({ block: "start" });
      return;
    }
    if (window.matchMedia("(max-width: 820px)").matches) setLibraryOpen(false, true);
    selectTerminalChart(link.dataset.chartId);
  });
}

function bindChartToolbar() {
  document.querySelectorAll("[data-chart-action]").forEach((button) => {
    button.addEventListener("click", () => handleChartAction(button.dataset.chartAction, button));
  });
  document.querySelectorAll("[data-range]").forEach((button) => {
    button.addEventListener("click", () => setChartRange(button.dataset.range));
  });
  document.querySelector("#scale-toggle")?.addEventListener("click", toggleChartScale);
  document.querySelectorAll("[data-touch-mode]").forEach((button) => {
    button.addEventListener("click", () => setTouchMode(button.dataset.touchMode));
  });
  document.querySelector("#data-sheet")?.addEventListener("click", (event) => {
    if (event.target.closest?.('[data-sheet-action="csv"]')) downloadSheetCsv();
  });
}

async function selectTerminalChart(chartId, options = {}) {
  const chart = chartById(chartId);
  if (!chart) return;
  const restore = options.restore || null;
  const previousChartId = appState.activeChartId;
  const request = {};
  appState.chartRequest = request;
  appState.activeChartId = chart.id;
  appState.currentChart = chart;
  appState.currentPayload = null;
  appState.chartOptions.movingAverage = false;
  appState.chartOptions.halvings = false;
  appState.chartOptions.table = false;
  appState.chartOptions.scale = null;
  appState.chartOptions.signalView = false;
  appState.chartOptions.rangePayload = null;
  appState.chartOptions.rangeTransition = null;
  appState.chartOptions.range = "all";
  appState.chartOptions.customRange = null;
  if (restore && typeof restore.grid === "boolean") appState.chartOptions.grid = restore.grid;
  updateToolbarPressedStates();
  const pinButton = document.querySelector('[data-chart-action="pin"]');
  if (pinButton) {
    const pinned = readPinnedCharts().has(chart.id);
    pinButton.classList.toggle("active", pinned);
    pinButton.setAttribute("aria-pressed", String(pinned));
    pinButton.textContent = pinned ? "⌖ Pinned" : "⌖ Pin";
  }
  document.querySelector("#terminal-plot")?.removeAttribute("hidden");
  document.querySelector("#data-sheet")?.setAttribute("hidden", "");
  showChartNotice(options.notice || "");

  const search = document.querySelector("#sidebar-search");
  renderSidebar(search?.value || "");
  document.querySelectorAll(".sidebar-chart-link[data-chart-id]").forEach(bindChartLink);
  updateChartHeadings(chart);
  renderRelatedCharts(chart);
  if (options.updateUrl !== false) syncTerminalUrl({ push: chart.id !== previousChartId });

  const target = document.querySelector("#terminal-plot");
  target.innerHTML = "";
  target.classList.add("loading-block");

  if (!chart.data_path) {
    renderImageChart(chart, target);
    syncTerminalUrl();
    announceChartStatus();
    return;
  }

  try {
    const payload = await getPayload(chart.id);
    if (appState.chartRequest !== request) return;
    appState.currentPayload = payload;
    const defaults = terminalOptionDefaults(payload);
    appState.chartOptions.halvings = typeof restore?.halvings === "boolean" && payload.x_value_type === "date"
      ? restore.halvings
      : defaults.halvings;
    appState.chartOptions.scale = payload.allow_scale_toggle && restore?.scale ? restore.scale : defaults.scale;
    appState.chartOptions.signalView = Boolean(payload.signal_view && (options.signalView || restore?.signals));
    appState.chartOptions.movingAverage = Boolean(restore?.movingAverage && payloadHasNumericLine(payload));
    updateChartControls(payload);
    updateToolbarPressedStates();
    target.classList.remove("loading-block");
    await renderTerminalPlot();
    if (appState.chartRequest !== request) return;
    if (restore && payload.x_value_type === "date") {
      if (restore.from && restore.to) await applyCustomRange([restore.from, restore.to]);
      else if (restore.range && restore.range !== "all") await setChartRange(restore.range);
      if (appState.chartRequest !== request) return;
    }
    renderChartDetails(payload);
    if (restore?.view === "sheet") setTableView(true);
    else renderDataSheet(payload);
    updateScaleButton();
    syncTerminalUrl();
    announceChartStatus();
  } catch (error) {
    if (appState.chartRequest !== request) return;
    target.classList.remove("loading-block");
    if (chart.image_path) renderImageChart(chart, target);
    else target.innerHTML = `<p class="error-state">${escapeHtml(error.message)}</p>`;
  }
}

function payloadHasNumericLine(payload) {
  return (payload?.series || []).some((series) => (
    series.type === "scatter"
    && Array.isArray(series.y)
    && series.y.some((value) => Number.isFinite(toFiniteNumber(value)))
  ));
}

function updateChartControls(payload) {
  const hasNumericLine = payloadHasNumericLine(payload);
  const movingAverage = document.querySelector('[data-chart-action="moving-average"]');
  const halvings = document.querySelector('[data-chart-action="halvings"]');
  const rangeOptions = document.querySelector(".range-options");
  const signalView = document.querySelector('[data-chart-action="signals"]');
  if (signalView) {
    signalView.hidden = !payload.signal_view;
    signalView.classList.toggle("active", appState.chartOptions.signalView);
    signalView.setAttribute("aria-pressed", String(appState.chartOptions.signalView));
  }
  if (movingAverage) movingAverage.disabled = !hasNumericLine;
  if (halvings) halvings.disabled = payload.x_value_type !== "date";
  if (rangeOptions) rangeOptions.hidden = payload.show_range_selector === false || payload.x_value_type !== "date";
}

function updateChartHeadings(chart) {
  ["#chart-title", "#chart-mobile-title"].forEach((selector) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = chart.title;
  });
  ["#chart-section", "#chart-mobile-section"].forEach((selector) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = chart.section;
  });
  document.title = `${chart.title} | Fintech Charts`;
  const summary = document.querySelector("#chart-summary");
  if (summary) setChartSummary(chart.description);
  renderChartAttribution(chart);
  updateChartAlertLink(chart);
}

function updateChartAlertLink(chart = appState.currentChart) {
  const alertLink = document.querySelector("#chart-alert-link");
  if (!alertLink || !chart) return;
  // The alerts page resolves ?chart= itself, so this link is right before the
  // signals finish loading and explains charts that have no cycle signal.
  const signal = (appState.signals || []).find((item) => item.chartId === chart.id);
  alertLink.href = signal
    ? `../alerts/?signal=${encodeURIComponent(signal.id)}`
    : `../alerts/?chart=${encodeURIComponent(chart.id)}`;
  alertLink.title = signal
    ? `Create an alert on the ${signal.label} cycle score`
    : appState.signalState
      ? "This chart has no cycle signal. Open alerts to choose a scored signal."
      : "Create a cycle-score alert";
}

function renderRelatedCharts(chart) {
  const section = queryNode("#related-section");
  const list = queryNode("#related-list");
  if (!section || !list) return;
  const key = chartSectionKey(chart);
  const related = (appState.manifest?.charts || [])
    .filter((item) => item.id !== chart.id && key && chartSectionKey(item) === key)
    .sort((a, b) => (Number(a.order) || 0) - (Number(b.order) || 0) || String(a.title).localeCompare(String(b.title)));
  const heading = queryNode("#related-heading");
  const count = queryNode("#related-count");
  if (heading) heading.textContent = `More in ${chart.section || "this section"}`;
  if (count) count.textContent = String(related.length);
  const shown = related.slice(0, 8);
  list.innerHTML = shown.map((item) => {
    const href = `?chart=${encodeURIComponent(item.id)}`;
    return `<a class="related-chart-link" href="${escapeHtml(href)}" data-chart-id="${escapeHtml(item.id)}">${escapeHtml(item.title)}</a>`;
  }).join("") + (related.length > shown.length && key
    ? `<button type="button" class="related-more" data-related-section="${escapeHtml(key)}">Show all ${related.length + 1} in the library</button>`
    : "");
  section.hidden = !related.length;
  list.querySelectorAll?.(".related-chart-link[data-chart-id]").forEach(bindChartLink);
  list.querySelector?.("[data-related-section]")?.addEventListener("click", (event) => {
    appState.sectionFilter = event.currentTarget.dataset.relatedSection;
    renderSidebar();
    syncTerminalUrl();
    setLibraryOpen(true);
    document.querySelector("#sidebar-search")?.focus();
    announceStatus(librarySearchStatus());
  });
}

async function renderTerminalPlot() {
  const target = document.querySelector("#terminal-plot");
  const payload = appState.currentPayload;
  if (!target || !payload) return;
  // Finish a shortcut animation before capturing its final viewport. Keep the
  // original render baseline so Reset zoom still restores the complete chart.
  await appState.chartOptions.rangeTransition;
  if (appState.currentPayload !== payload) return;
  const visibleRange = appState.chartOptions.rangePayload === payload
    ? target._fullLayout?.xaxis?.range?.slice() : null;
  target.innerHTML = "";
  const series = terminalSeries(payload);
  const layout = terminalLayout(payload);
  if (payload.allow_scale_toggle && appState.chartOptions.scale && payload.layout?.yaxis !== undefined) {
    (payload.scale_axes || ["y"]).forEach((axis) => {
      const key = axis === "y" ? "yaxis" : `yaxis${axis.replace("y", "")}`;
      layout[key] = { ...(layout[key] || {}), type: appState.chartOptions.scale };
    });
  }
  await renderPlot(target, payload, {
    series,
    layout,
    grid: appState.chartOptions.grid,
    maxPoints: 2200,
    signalView: appState.chartOptions.signalView,
    onViewportChange: onTerminalViewportChange,
  });
  if (appState.currentPayload !== payload) return;
  appState.chartOptions.rangePayload = payload;
  installTerminalInspector(target, payload);
  if (visibleRange && target._fintechNavigation) {
    await target._fintechNavigation.zoomTo(visibleRange, "restore");
  } else if (visibleRange && window.Plotly) {
    await Plotly.relayout(target, { "xaxis.range": visibleRange, "xaxis.autorange": false });
  }
}

// Drag, wheel, keyboard, and modebar zooms report here once they settle.
// Shortcut and restore transitions already own their URL state.
function onTerminalViewportChange({ source, range, full } = {}) {
  if (source !== "user" || !appState.currentPayload) return;
  if (full) {
    appState.chartOptions.range = "all";
    appState.chartOptions.customRange = null;
  } else {
    appState.chartOptions.range = null;
    appState.chartOptions.customRange = appState.currentPayload.x_value_type === "date" ? customRangeFromAxis(range) : null;
  }
  updateRangeButtons();
  syncTerminalUrl();
  if (appState.chartOptions.table) renderDataSheet(appState.currentPayload);
  announceStatus(`Showing ${appState.currentChart?.title || "chart"}, ${terminalRangeLabel()}`, 300);
}

function customRangeFromAxis(range) {
  if (!Array.isArray(range) || range.length < 2) return null;
  const times = range.map((value) => new Date(value).getTime()).filter(Number.isFinite).sort((a, b) => a - b);
  if (times.length < 2) return null;
  // Round to whole UTC days: `from` is the first day shown and `to` the last,
  // matching applyCustomRange's start-of-from to end-of-to window.
  const day = 86_400_000;
  const from = new Date(Math.round(times[0] / day) * day).toISOString().slice(0, 10);
  const to = new Date(Math.round(times[1] / day) * day - 1).toISOString().slice(0, 10);
  return [from, to < from ? from : to];
}

async function applyCustomRange(range) {
  const target = queryNode("#terminal-plot");
  appState.chartOptions.range = null;
  appState.chartOptions.customRange = range.slice();
  updateRangeButtons();
  const selected = [`${range[0]}T00:00:00.000Z`, `${range[1]}T23:59:59.999Z`];
  const transition = Promise.resolve(target?._fintechNavigation
    ? target._fintechNavigation.zoomTo(selected, "restore")
    : window.Plotly && target ? Plotly.relayout(target, { "xaxis.range": selected }) : null);
  appState.chartOptions.rangeTransition = transition;
  await transition;
}

function isCoarsePointer() {
  try {
    return Boolean(window.matchMedia?.("(pointer: coarse)").matches || window.matchMedia?.("(hover: none)").matches);
  } catch {
    return false;
  }
}

function touchInspectActive() {
  return isCoarsePointer() && appState.chartOptions.touchMode !== "zoom";
}

function updateTouchModeControls() {
  const group = queryNode("#chart-touch-mode");
  if (group) group.hidden = !isCoarsePointer();
  document.querySelectorAll?.("[data-touch-mode]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.touchMode === appState.chartOptions.touchMode));
  });
  const target = queryNode("#terminal-plot");
  target?.classList?.toggle?.("touch-inspect", touchInspectActive());
}

async function setTouchMode(mode) {
  appState.chartOptions.touchMode = mode === "zoom" ? "zoom" : "inspect";
  updateTouchModeControls();
  const target = queryNode("#terminal-plot");
  if (target?._fullLayout && window.Plotly) {
    await Plotly.relayout(target, { dragmode: touchInspectActive() ? false : "zoom" }).catch(() => {});
  }
  announceStatus(appState.chartOptions.touchMode === "zoom" ? "Touch drag zooms the chart" : "Touch drag inspects values");
}

function terminalSeries(payload) {
  const series = payload.series.map((item) => ({ ...item, line: item.line ? { ...item.line } : item.line }));
  if (!appState.chartOptions.movingAverage) return series;
  const base = series.find((item) => Array.isArray(item.y) && item.y.some((value) => Number.isFinite(Number(value))));
  if (!base) return series;
  const moving = movingAverage(base.y, 50);
  series.push({
    name: `${base.name} · 50 period MA`,
    type: "scatter",
    mode: "lines",
    x: base.x,
    y: moving,
    line: { color: "#7c5ca8", width: 1.7, dash: "dot" },
    hovertemplate: "%{x}<br>%{y:,.2f}<extra>50 period MA</extra>",
  });
  return series;
}

function terminalLayout(payload) {
  const layout = appState.chartOptions.halvings && payload.x_value_type !== "number"
    ? halvingOverlayLayout(payload)
    : {};
  // On touch screens a one-finger drag scrubs values unless Zoom is chosen.
  if (touchInspectActive()) layout.dragmode = false;
  return layout;
}

function halvingOverlayLayout(payload) {
  const dates = ["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"];
  return {
    shapes: [
      ...(payload.layout?.shapes || []),
      ...dates.map((date) => ({
        type: "line",
        xref: "x",
        yref: "paper",
        x0: date,
        x1: date,
        y0: 0,
        y1: 1,
        line: { color: "#c85f3c", width: 1, dash: "dot" },
      })),
    ],
    annotations: [
      ...(payload.layout?.annotations || []),
      ...dates.map((date, index) => ({
        x: date,
        y: 0.02,
        xref: "x",
        yref: "paper",
        text: `Halving ${index + 1}`,
        showarrow: false,
        textangle: 90,
        font: { size: 9, color: "#98958e" },
      })),
    ],
  };
}

function renderImageChart(chart, target) {
  target.classList.remove("loading-block");
  target.innerHTML = chart.image_path
    ? `<img class="terminal-chart-image" src="${escapeHtml(assetPath(chart.image_path))}" alt="${escapeHtml(chart.title)}">`
    : `<p class="empty-state">This report does not have a browser-ready chart payload yet.</p>`;
  document.querySelector("#series-list").innerHTML = `<p class="empty-state">Generated report image</p>`;
  document.querySelector("#performance-list").innerHTML = "";
  document.querySelector("#chart-phase").innerHTML = `<span>Report</span><strong>Image view</strong>`;
  clearChartInsights();
  renderChartReadout(null, null);
}

function renderChartDetails(payload) {
  const seriesList = document.querySelector("#series-list");
  const performanceList = document.querySelector("#performance-list");
  // Projection traces can run years past today; "latest" means the last
  // observed date, the same anchor the range shortcuts use.
  const anchor = payload.x_value_type === "date" ? observedRangeEnd(payload) : null;
  document.querySelector("#series-date").textContent = anchor !== null ? shortDate(anchor) : "Latest";
  setChartSummary(payload.summary_text || appState.currentChart.description);
  renderChartAttribution(payload);

  seriesList.innerHTML = payload.series.slice(0, 8).map((series, index) => {
    const value = seriesLatestValue(series, anchor);
    return `
      <div class="series-row" data-series-index="${index}">
        <span class="series-dot" style="background:${escapeHtml(seriesColor(series, index))}"></span>
        <span class="series-name" title="${escapeHtml(series.name)}">${escapeHtml(series.name)}</span>
        <strong class="series-value">${escapeHtml(seriesDisplayValue(series, value))}</strong>
      </div>
    `;
  }).join("");

  const base = payload.x_value_type === "date" ? detailSeries(payload) : null;
  const performanceLabel = document.querySelector("#performance-series-label");
  const changes = base
    ? [[7, "1W"], [30, "1M"], [90, "3M"], [180, "6M"], ["ytd", "YTD"], [365, "1Y"]].map(([window, label]) => ({
      label,
      result: seriesWindowChange(base, window, { anchor }),
    }))
    : [];
  const mode = changes.find((item) => item.result)?.result.mode || seriesChangeMode(base);
  if (performanceLabel) {
    performanceLabel.textContent = base ? `${base.name || "main series"} · ${{ relative: "% change", points: "pp change", absolute: "Δ change" }[mode]}` : "—";
    performanceLabel.title = performanceLabel.textContent;
  }
  const largest = Math.max(0, ...changes.map((item) => Math.abs(item.result?.change || 0)));
  performanceList.innerHTML = base
    ? changes.map(({ label, result }) => {
      const change = result?.change;
      const finite = Number.isFinite(change);
      const width = !finite ? 0 : result.mode === "relative"
        ? Math.min(50, Math.abs(change) / 2)
        : largest ? (Math.abs(change) / largest) * 50 : 0;
      return `
        <div class="performance-row ${finite && change < 0 ? "negative" : ""}">
          <span>${label}</span>
          <span class="performance-bar"><span style="width:${width}%"></span></span>
          <strong class="performance-value">${escapeHtml(formatSeriesChange(result))}</strong>
        </div>
      `;
    }).join("")
    : `<p class="empty-state">Performance comparison is unavailable for this chart type.</p>`;

  renderChartInsights(payload, base);

  updateChartPhase(payload);
}

function updateChartPhase(payload) {
  if (payload !== appState.currentPayload || payload.id !== appState.currentChart?.id) return;
  const signal = appState.signals.find((item) => item.chartId === appState.currentChart.id);
  const phaseBox = document.querySelector("#chart-phase");
  if (signal) phaseBox.innerHTML = `<span>Cycle signal</span><strong>${Math.round(signal.score)} · ${signal.phase.label}</strong>`;
  else phaseBox.innerHTML = `<span>Data status</span><strong>${formatDate(new Date(payload.updated_at || appState.manifest.generated_at))}</strong>`;
}

function detailSeries(payload) {
  const usable = (series) => series?.type !== "heatmap"
    && Array.isArray(series?.x)
    && Array.isArray(series?.y)
    && series.x.length === series.y.length
    && primaryValues(series).length > 8;
  const isBtcOverlay = (series) => payload.id !== "price" && series?.source_key === "price";
  return payload.series.find((series) => series.source_key === payload.main_series_key && usable(series))
    // Imported metric charts can carry BTC only as a visual overlay. Their
    // sidebar modules should analyse the underlying metric, as the source
    // terminal does, rather than silently switching to the overlay.
    || payload.series.find((series) => usable(series) && !isBtcOverlay(series))
    || payload.series.find(usable)
    || null;
}

function clearChartInsights() {
  [
    ["#cycle-comparison", "#cycle-series-label", "#cycle-comparison-section"],
    ["#month-to-month", "#month-series-label", "#month-to-month-section"],
    ["#time-spent", "#time-series-label", "#time-spent-section"],
  ].forEach(([contentSelector, labelSelector, sectionSelector]) => {
    const content = document.querySelector(contentSelector);
    const label = document.querySelector(labelSelector);
    const section = document.querySelector(sectionSelector);
    if (content) content.innerHTML = "";
    if (label) label.textContent = "—";
    if (section) section.hidden = true;
  });
}

function renderChartInsights(payload, series) {
  if (!series || payload.x_value_type !== "date") {
    clearChartInsights();
    return;
  }
  const points = datedSeriesPoints(series);
  const label = series.name || "Main series";
  ["#cycle-series-label", "#month-series-label", "#time-series-label"].forEach((selector) => {
    const node = document.querySelector(selector);
    if (node) {
      node.textContent = label;
      node.title = label;
    }
  });
  const insightViews = [
    ["#cycle-comparison", "#cycle-comparison-section", cycleComparisonSvg(points, series)],
    ["#month-to-month", "#month-to-month-section", monthToMonthGrid(points)],
    ["#time-spent", "#time-spent-section", timeSpentHistogram(points)],
  ];
  insightViews.forEach(([contentSelector, sectionSelector, markup]) => {
    const content = document.querySelector(contentSelector);
    const section = document.querySelector(sectionSelector);
    if (content) content.innerHTML = markup || "";
    if (section) section.hidden = !markup;
  });
}

function datedSeriesPoints(series) {
  return series.x.map((date, index) => ({
    date: new Date(date),
    value: toFiniteNumber(series.y[index]),
  })).filter((point) => Number.isFinite(point.date.getTime()) && Number.isFinite(point.value))
    .sort((left, right) => left.date - right.date);
}

function cycleComparisonSvg(points, series) {
  // Stacked cohort charts are flow compositions, not a single cycle metric.
  // BlockHorizon omits its cycle panel for these views.
  if (series?.stackgroup || series?.fill === "tonexty") return null;
  const halvings = ["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"].map((date) => new Date(`${date}T00:00:00Z`));
  const duration = 1460 * 24 * 60 * 60 * 1000;
  const latestDate = points.at(-1)?.date;
  if (!latestDate) return null;
  // BlockHorizon compares price as growth since each halving, rather than
  // putting nominal 2012 and 2024 dollars on one axis.  Other metrics retain
  // their native unit (for example drawdown percent or S2F error).
  const growthMode = /(^|[-_ ])price($|[-_ ])/i.test(series?.source_key || "")
    || /^btc price|^price \[usd\]$/i.test(series?.name || "");
  const valueAtOrBefore = (date, toleranceDays = 10) => {
    const target = date.getTime();
    for (let index = points.length - 1; index >= 0; index -= 1) {
      const point = points[index];
      const time = point.date.getTime();
      if (time > target) continue;
      return target - time <= toleranceDays * 86_400_000 ? point.value : null;
    }
    return null;
  };
  const cycles = halvings.map((start, index) => {
    const next = halvings[index + 1] || new Date(start.getTime() + duration);
    const end = new Date(Math.min(next.getTime(), latestDate.getTime(), start.getTime() + duration));
    const days = Math.floor((end.getTime() - start.getTime()) / 86_400_000);
    if (days < 90) return null;
    const baseline = growthMode ? valueAtOrBefore(start, 20) : 1;
    if (!Number.isFinite(baseline) || baseline <= 0) return null;
    const samples = [];
    for (let day = 0; day <= days; day += 7) {
      const value = valueAtOrBefore(new Date(start.getTime() + day * 86_400_000));
      if (Number.isFinite(value)) samples.push({ offset: day * 86_400_000, value: growthMode ? value / baseline : value });
    }
    return samples.length > 8 ? samples : null;
  }).filter(Boolean);
  if (!cycles.length) return null;
  const values = cycles.flatMap((cycle) => cycle.map((point) => point.value));
  const positive = values.every((value) => value > 0);
  const scaleValues = positive ? values.map((value) => Math.log10(value)) : values;
  // Match the source module's robust 1st–99th percentile scale: an isolated
  // early-cycle spike should not flatten every other halving trajectory.
  const minimum = quantile(scaleValues, 0.01);
  const maximum = quantile(scaleValues, 0.99);
  const span = maximum - minimum || 1;
  const chartWidth = 300;
  const chartHeight = 118;
  const left = 36;
  const top = 8;
  const bottom = 20;
  const toScale = (value) => positive ? Math.log10(value) : value;
  const projectY = (value) => {
    const normalized = clamp((toScale(value) - minimum) / span, 0, 1);
    return chartHeight - bottom - normalized * (chartHeight - top - bottom);
  };
  const projectX = (offset) => left + (Math.min(duration, Math.max(0, offset)) / duration) * (chartWidth - left - 2);
  const paths = cycles.map((cycle, index) => {
    const commands = cycle.map((point, pointIndex) => `${pointIndex ? "L" : "M"}${projectX(point.offset).toFixed(1)},${projectY(point.value).toFixed(1)}`);
    const current = index === cycles.length - 1;
    return `<path d="${commands.join(" ")}" class="cycle-line ${current ? "current" : ""}"/>`;
  }).join("");
  const formatTick = (value) => {
    if (growthMode) return `×${value >= 10 ? Math.round(value) : value.toFixed(1)}`;
    return formatMetricValue("value", value);
  };
  const lowValue = positive ? 10 ** minimum : minimum;
  const midValue = positive ? 10 ** (minimum + span / 2) : minimum + span / 2;
  const highValue = positive ? 10 ** maximum : maximum;
  const ticks = [highValue, midValue, lowValue];
  return `<svg class="cycle-comparison-svg" viewBox="0 0 ${chartWidth} ${chartHeight}" role="img" aria-label="Historical halving-cycle comparison">
    ${ticks.map((value) => `<line x1="${left}" x2="${chartWidth}" y1="${projectY(value).toFixed(1)}" y2="${projectY(value).toFixed(1)}" class="insight-gridline"/><text x="${left - 5}" y="${(projectY(value) + 3.5).toFixed(1)}" text-anchor="end">${escapeHtml(formatTick(value))}</text>`).join("")}
    ${paths}
    <circle cx="${projectX(cycles.at(-1).at(-1).offset).toFixed(1)}" cy="${projectY(cycles.at(-1).at(-1).value).toFixed(1)}" r="3.5" class="cycle-current-dot"/>
    <text x="${left}" y="${chartHeight - 3}">halving</text><text x="${left + (chartWidth - left) / 2}" y="${chartHeight - 3}" text-anchor="middle">+2y</text><text x="${chartWidth}" y="${chartHeight - 3}" text-anchor="end">+4y</text>
  </svg>`;
}

function monthToMonthGrid(points) {
  const rows = new Map();
  points.forEach((point) => {
    const year = point.date.getUTCFullYear();
    const month = point.date.getUTCMonth();
    if (!rows.has(year)) rows.set(year, Array.from({ length: 12 }, () => []));
    rows.get(year)[month].push(point.value);
  });
  const changes = [...rows.entries()].map(([year, months]) => ({
    year,
    values: months.map((values) => {
      if (values.length < 2) return null;
      const first = values[0];
      const lastValue = values.at(-1);
      if (!Number.isFinite(first) || first === 0 || !Number.isFinite(lastValue)) return null;
      return (lastValue - first) / Math.abs(first);
    }),
  })).filter((row) => row.values.some((value) => Number.isFinite(value))).slice(-14);
  if (!changes.length) return null;
  const cells = changes.map((row) => `<span class="month-year">${String(row.year).slice(-2)}</span>${row.values.map((value) => {
    if (!Number.isFinite(value)) return `<span class="month-cell empty"></span>`;
    const intensity = Math.min(1, Math.abs(value) / 0.35).toFixed(2);
    return `<span class="month-cell ${value < 0 ? "negative" : "positive"}" style="--intensity:${intensity}" title="${row.year}: ${signed(value * 100)}"></span>`;
  }).join("")}`).join("");
  return `<div class="month-grid" role="img" aria-label="Month-over-month change heatmap">
    <span></span>${["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"].map((month) => `<span class="month-name">${month}</span>`).join("")}
    ${cells}
  </div>`;
}

function timeSpentHistogram(points) {
  const values = points.map((point) => point.value).filter(Number.isFinite);
  if (values.length < 12) return null;
  const lower = quantile(values, 0.05);
  const upper = quantile(values, 0.95);
  if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper) return null;
  const bins = Array.from({ length: 16 }, () => 0);
  values.forEach((value) => {
    const ratio = Math.max(0, Math.min(0.999999, (value - lower) / (upper - lower)));
    bins[Math.floor(ratio * bins.length)] += 1;
  });
  const largest = Math.max(...bins, 1);
  const latest = values.at(-1);
  const marker = Math.max(0, Math.min(1, (latest - lower) / (upper - lower))) * 184 + 8;
  const bars = bins.map((count, index) => {
    const height = (count / largest) * 34;
    return `<rect x="${8 + index * 11.5}" y="${50 - height}" width="8" height="${height}" class="time-bar"/>`;
  }).join("");
  return `<svg class="time-spent-svg" viewBox="0 0 200 64" role="img" aria-label="Distribution of time spent at metric values">
    <line x1="8" x2="192" y1="50" y2="50" class="insight-gridline"/>
    ${bars}<line x1="${marker.toFixed(1)}" x2="${marker.toFixed(1)}" y1="8" y2="52" class="time-marker"/>
    <text x="${Math.max(8, Math.min(162, marker - 11)).toFixed(1)}" y="8" class="time-marker-label">today</text>
    <text x="8" y="62">${escapeHtml(formatMetricValue("value", lower))}</text><text x="164" y="62">${escapeHtml(formatMetricValue("value", upper))}</text>
  </svg>`;
}

function setChartSummary(text) {
  const summary = document.querySelector("#chart-summary");
  if (!summary) return;
  summary.textContent = text || "";
}

function renderChartAttribution(source) {
  const target = document.querySelector("#chart-attribution");
  if (!target) return;
  const explicit = Array.isArray(source?.attributions) ? source.attributions : [];
  const entries = explicit.length
    ? explicit
    : source?.source_url
      ? [{ kind: "Data", label: source.source_label || "Source", url: source.source_url }]
      : [];
  const links = entries.map((entry) => {
    const url = safeAttributionUrl(entry?.url);
    if (!url || !entry?.label) return "";
    const kind = entry.kind ? `${escapeHtml(entry.kind)}: ` : "";
    return `<span>${kind}<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(entry.label)}<span aria-hidden="true"> ↗</span></a></span>`;
  }).filter(Boolean);
  target.innerHTML = links.join('<span class="chart-attribution-separator" aria-hidden="true">·</span>');
  target.hidden = links.length === 0;
}

function safeAttributionUrl(value) {
  try {
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

const SHEET_ROW_LIMIT = 1000;

// Rows behind the sheet and its CSV export. A date or numeric range limits the
// rows to the chart's visible window; `null` keeps the complete history.
function dataSheetModel(payload, range = null) {
  const horizontal = payload.series.filter((series) => (
    series.orientation === "h"
    && Array.isArray(series.x)
    && Array.isArray(series.y)
    && series.x.length === series.y.length
  ));
  const columns = horizontal.length
    ? horizontal.map((series) => ({ name: series.name, template: series.hovertemplate, coordinates: series.y, values: series.x }))
    : payload.series.flatMap((series) => {
      if (series.type === "heatmap" || !Array.isArray(series.x)) return [];
      if (["candlestick", "ohlc"].includes(series.type)) {
        return ["open", "high", "low", "close"].filter((key) => (
          Array.isArray(series[key]) && series.x.length === series[key].length
        )).map((key) => ({
          name: `${series.name} · ${key[0].toUpperCase()}${key.slice(1)}`,
          formatName: `${series.name} price`,
          coordinates: series.x,
          values: series[key],
        }));
      }
      return Array.isArray(series.y) && series.x.length === series.y.length
        ? [{ name: series.name, template: series.hovertemplate, coordinates: series.x, values: series.y }]
        : [];
    });
  const orderedCoordinates = !horizontal.length && ["date", "number"].includes(payload.x_value_type);
  const coordinateKey = (value) => orderedCoordinates ? comparableX(value) : String(value);
  const coordinates = new Map();
  const lookups = columns.map((column) => new Map(column.coordinates.map((coordinate, index) => {
    const key = coordinateKey(coordinate);
    coordinates.set(key, coordinate);
    return [key, column.values[index]];
  })));
  let rowCoordinates = [...coordinates.values()];
  if (orderedCoordinates) rowCoordinates.sort((left, right) => comparableX(left) - comparableX(right));
  const bounds = orderedCoordinates && Array.isArray(range) ? range.map(comparableX).sort((a, b) => a - b) : null;
  if (bounds && bounds.every(Number.isFinite)) {
    rowCoordinates = rowCoordinates.filter((coordinate) => {
      const value = comparableX(coordinate);
      return value >= bounds[0] && value <= bounds[1];
    });
  }
  return {
    columns,
    coordinateLabel: horizontal.length || payload.x_value_type === "category" ? "Category" : payload.x_value_type === "date" ? "Date" : "X",
    dated: !horizontal.length && payload.x_value_type === "date",
    filtered: Boolean(bounds),
    rows: rowCoordinates.map((coordinate) => {
      const key = coordinateKey(coordinate);
      return { coordinate, values: lookups.map((lookup) => lookup.get(key)) };
    }),
  };
}

function terminalVisibleRange(payload) {
  const options = appState.chartOptions;
  if (!payload || !["date", "number"].includes(payload.x_value_type)) return null;
  if (options.customRange) return [`${options.customRange[0]}T00:00:00.000Z`, `${options.customRange[1]}T23:59:59.999Z`];
  if (options.range && options.range !== "all") return shortcutRange(payload, options.range);
  if (options.range === null) {
    const range = queryNode("#terminal-plot")?._fullLayout?.xaxis?.range;
    return Array.isArray(range) ? range.slice() : null;
  }
  return null;
}

function renderDataSheet(payload, range = terminalVisibleRange(payload)) {
  const sheet = document.querySelector("#data-sheet");
  const model = dataSheetModel(payload, range);
  if (!model.columns.length) {
    sheet.innerHTML = `<p class="empty-state">A tabular view is not available for this chart type.</p>`;
    return;
  }
  const shown = model.rows.slice(-SHEET_ROW_LIMIT);
  const headers = model.columns.map((column) => `<th>${escapeHtml(column.name)}</th>`).join("");
  const rows = shown.map(({ coordinate, values }) => {
    const cells = model.columns.map((column, index) => `<td>${escapeHtml(formatHoverMetricValue(column.formatName || column.name, values[index], column.template))}</td>`).join("");
    const label = model.dated ? shortDate(coordinate) : String(coordinate);
    return `<tr><td>${escapeHtml(label)}</td>${cells}</tr>`;
  }).reverse().join("");
  const count = new Intl.NumberFormat("en-US").format(model.rows.length);
  const scope = model.filtered ? "in the visible range" : "in full history";
  const summary = shown.length < model.rows.length
    ? `Showing the latest ${new Intl.NumberFormat("en-US").format(shown.length)} of ${count} rows ${scope}. The CSV includes every row.`
    : `${count} row${model.rows.length === 1 ? "" : "s"} ${scope}.`;
  sheet.innerHTML = `<div class="data-sheet-header"><p class="data-sheet-summary">${escapeHtml(summary)}</p><button type="button" class="toolbar-button" data-sheet-action="csv">⇩ Download CSV</button></div><table><caption class="visually-hidden">${escapeHtml(appState.currentChart?.title || "Chart data")}</caption><thead><tr><th>${model.coordinateLabel}</th>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
}

// Raw values (not display strings) so spreadsheets can calculate with them.
// Text cells that start like a formula are prefixed to stop CSV injection.
function dataSheetCsv(model) {
  const cell = (value) => {
    if (value === null || value === undefined) return "";
    let text = String(value);
    if (typeof value === "string" && /^[=+\-@\t\r]/.test(text) && !Number.isFinite(Number(text))) text = `'${text}`;
    return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  const header = [model.coordinateLabel, ...model.columns.map((column) => column.name)].map(cell).join(",");
  const lines = model.rows.map(({ coordinate, values }) => [coordinate, ...values.map((value) => {
    const number = toFiniteNumber(value);
    return Number.isFinite(number) ? number : null;
  })].map(cell).join(","));
  return `${[header, ...lines].join("\r\n")}\r\n`;
}

function downloadSheetCsv() {
  const payload = appState.currentPayload;
  if (!payload) return;
  const range = terminalVisibleRange(payload);
  const model = dataSheetModel(payload, range);
  if (!model.columns.length) return;
  const suffix = appState.chartOptions.customRange
    ? `-${appState.chartOptions.customRange.join("-to-")}`
    : appState.chartOptions.range && appState.chartOptions.range !== "all" ? `-${appState.chartOptions.range}` : "";
  const blob = new Blob([dataSheetCsv(model)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${appState.currentChart?.id || "chart"}${suffix}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  announceStatus(`Downloaded ${model.rows.length} rows as CSV`);
}

function setTableView(visible) {
  appState.chartOptions.table = Boolean(visible);
  setPressed(queryNode('[data-chart-action="table"]'), appState.chartOptions.table);
  const plot = queryNode("#terminal-plot");
  const sheet = queryNode("#data-sheet");
  if (plot) plot.hidden = appState.chartOptions.table;
  if (sheet) sheet.hidden = !appState.chartOptions.table;
  if (appState.chartOptions.table && appState.currentPayload) renderDataSheet(appState.currentPayload);
}

async function copyTerminalLink(button) {
  syncTerminalUrl();
  const href = window.location.href;
  let copied = false;
  try {
    await navigator.clipboard.writeText(href);
    copied = true;
  } catch {
    const field = document.createElement("textarea");
    field.value = href;
    field.setAttribute("readonly", "");
    field.className = "visually-hidden";
    document.body.append(field);
    field.select();
    try { copied = document.execCommand("copy"); } catch { copied = false; }
    field.remove();
    button?.focus();
  }
  announceStatus(copied ? "Link to this chart view copied" : "Could not copy automatically. Copy the address bar to share this view.");
  if (button && copied) {
    const label = button.dataset.label || button.textContent;
    button.dataset.label = label;
    button.textContent = "✓ Copied";
    window.setTimeout(() => { button.textContent = button.dataset.label; }, 1600);
  }
}

async function handleChartAction(action, button) {
  if (!appState.currentChart) return;
  if (action === "signals" && appState.currentPayload?.signal_view) {
    appState.chartOptions.signalView = !appState.chartOptions.signalView;
    button.classList.toggle("active", appState.chartOptions.signalView);
    button.setAttribute("aria-pressed", String(appState.chartOptions.signalView));
    if (appState.chartOptions.table) setTableView(false);
    syncTerminalUrl();
    await renderTerminalPlot();
  }
  if (action === "moving-average") {
    appState.chartOptions.movingAverage = !appState.chartOptions.movingAverage;
    setPressed(button, appState.chartOptions.movingAverage);
    syncTerminalUrl();
    if (appState.currentPayload) await renderTerminalPlot();
  }
  if (action === "halvings") {
    appState.chartOptions.halvings = !appState.chartOptions.halvings;
    setPressed(button, appState.chartOptions.halvings);
    syncTerminalUrl();
    if (appState.currentPayload) await renderTerminalPlot();
  }
  if (action === "grid") {
    appState.chartOptions.grid = !appState.chartOptions.grid;
    setPressed(button, appState.chartOptions.grid);
    syncTerminalUrl();
    if (appState.currentPayload) await renderTerminalPlot();
  }
  if (action === "table") {
    setTableView(!appState.chartOptions.table);
    syncTerminalUrl();
    announceChartStatus();
  }
  if (action === "pin") togglePinnedChart(button);
  if (action === "copy-link") await copyTerminalLink(button);
  if (action === "download" && appState.currentPayload) {
    if (appState.chartOptions.table) downloadSheetCsv();
    else {
      Plotly.downloadImage(document.querySelector("#terminal-plot"), {
        format: "png",
        filename: appState.currentChart.id,
        width: 1600,
        height: 900,
      });
    }
  }
}

function togglePinnedChart(button) {
  const id = appState.currentChart?.id;
  if (!appState.manifest?.charts.some(chart => chart.id === id)) return;
  const pins = readPinnedCharts();
  if (pins.has(id)) pins.delete(id);
  else pins.add(id);
  const status = document.querySelector("#pin-status");
  try {
    localStorage.setItem("fintech-pins", JSON.stringify([...pins]));
  } catch {
    if (status) status.textContent = "Could not save pins on this device. Check browser storage settings and try again.";
    announceStatus("Could not save pins on this device.");
    return;
  }
  if (status) status.textContent = "";
  button.classList.toggle("active", pins.has(id));
  button.setAttribute("aria-pressed", String(pins.has(id)));
  button.textContent = pins.has(id) ? "\u2316 Pinned" : "\u2316 Pin";
  renderSidebar();
  announceStatus(`${appState.currentChart.title || "Chart"} ${pins.has(id) ? "pinned" : "unpinned"}`);
}

function shortcutRange(payload, range) {
  const endpoint = payload?.x_value_type === "date" ? observedRangeEnd(payload) : null;
  if (endpoint === null || range === "all" || !TERMINAL_RANGES.includes(range)) return null;
  const end = new Date(endpoint);
  let start = new Date(end);
  if (range === "1m") start.setUTCMonth(start.getUTCMonth() - 1);
  if (range === "3m") start.setUTCMonth(start.getUTCMonth() - 3);
  if (range === "6m") start.setUTCMonth(start.getUTCMonth() - 6);
  if (range === "1y") start.setUTCFullYear(start.getUTCFullYear() - 1);
  if (range === "4y") start.setUTCFullYear(start.getUTCFullYear() - 4);
  if (range === "ytd") start = new Date(Date.UTC(end.getUTCFullYear(), 0, 1));
  return [start.toISOString(), end.toISOString()];
}

function setChartRange(range) {
  if (!appState.currentPayload || !window.Plotly) return;
  const payload = appState.currentPayload;
  const selectedRange = shortcutRange(payload, range);
  appState.chartOptions.range = selectedRange ? range : "all";
  appState.chartOptions.customRange = null;
  updateRangeButtons();
  syncTerminalUrl();
  const target = document.querySelector("#terminal-plot");
  const navigation = target?._fintechNavigation;
  const transition = Promise.resolve(selectedRange
    ? navigation ? navigation.zoomTo(selectedRange, "shortcut") : Plotly.relayout(target, { "xaxis.range": selectedRange })
    : navigation ? navigation.reset("shortcut") : Plotly.relayout(target, { "xaxis.autorange": true }));
  appState.chartOptions.rangeTransition = transition;
  void transition.then(() => {
    if (appState.currentPayload !== payload) return;
    if (appState.chartOptions.table) renderDataSheet(payload);
    announceChartStatus();
  }, () => {});
  return transition;
}

function observedRangeEnd(payload) {
  const today = new Date();
  today.setUTCHours(23, 59, 59, 999);
  const prices = payload.series.filter((series) => (
    ["candlestick", "ohlc"].includes(series.type)
    || series.source_key === "price"
    || /^(btc\s+)?price$/i.test(String(series.name || "").trim())
  ));
  const latestObservation = (seriesList) => {
    let latest = null;
    seriesList.forEach((series) => {
      const values = seriesValueArray(series);
      (series.x || []).forEach((coordinate, index) => {
        const timestamp = new Date(coordinate).getTime();
        if (!Number.isFinite(timestamp) || timestamp > today.getTime()) return;
        if (values.length && !Number.isFinite(toFiniteNumber(values[index]))) return;
        if (latest === null || timestamp > latest) latest = timestamp;
      });
    });
    return latest;
  };
  // Model traces may project years beyond the observed market. Shortcuts
  // should stay anchored to the data a viewer can actually compare today.
  return latestObservation(prices) ?? latestObservation(payload.series);
}

function toggleChartScale() {
  const payload = appState.currentPayload;
  if (!payload?.allow_scale_toggle) return;
  appState.chartOptions.scale = appState.chartOptions.scale === "log" ? "linear" : "log";
  updateScaleButton();
  syncTerminalUrl();
  renderTerminalPlot();
}

function updateScaleButton() {
  const button = document.querySelector("#scale-toggle");
  if (!button || !appState.currentPayload) return;
  button.disabled = !appState.currentPayload.allow_scale_toggle;
  // A fixed label with a pressed state reads consistently: "Log scale, pressed".
  button.textContent = "log";
  setPressed(button, appState.chartOptions.scale === "log");
}

function movingAverage(values, windowSize) {
  const output = [];
  let total = 0;
  const queue = [];
  values.forEach((raw) => {
    const value = toFiniteNumber(raw);
    queue.push(value);
    total += Number.isFinite(value) ? value : 0;
    if (queue.length > windowSize) {
      const removed = queue.shift();
      total -= Number.isFinite(removed) ? removed : 0;
    }
    output.push(queue.length === windowSize && queue.every(Number.isFinite) ? total / windowSize : null);
  });
  return output;
}

function primaryValues(series) {
  if (series?.type === "heatmap") return [];
  if (series?.orientation === "h" && Array.isArray(series.x)) {
    return series.x.map(toFiniteNumber).filter(Number.isFinite);
  }
  for (const key of ["y", "close", "open", "high", "low"]) {
    if (Array.isArray(series?.[key])) return series[key].map(toFiniteNumber).filter(Number.isFinite);
  }
  return [];
}

// Percentages and ratios move in points: a drawdown from -33% to -41% is
// -8pp, not "+24%", and a Sharpe ratio crossing zero has no meaningful
// percentage change. Relative change is reserved for strictly positive levels.
function seriesChangeMode(series) {
  if (!series) return "relative";
  const name = String(series.name || "").toLowerCase();
  const template = String(series.hovertemplate || "");
  if (/}\s*(%|pp\b)/i.test(template) || /percent|%|\bshare\b|drawdown|return|volatility/.test(name)) return "points";
  if (/ratio|multiple|mvrv|nupl|z[\s-]?score|sharpe|sortino|oscillator|\bscore\b|\bindex\b|error/.test(name) || /}\s*x\b/i.test(template)) return "absolute";
  const values = primaryValues(series);
  return values.length && values.every((value) => value > 0) ? "relative" : "absolute";
}

function seriesWindowChange(series, window, { anchor = null, mode = seriesChangeMode(series) } = {}) {
  if (!Array.isArray(series?.x) || !Array.isArray(series?.y)) return null;
  const limit = Number.isFinite(Number(anchor)) && anchor !== null ? Number(anchor) : Infinity;
  const points = datedSeriesPoints(series).filter((point) => point.date.getTime() <= limit);
  const latest = points.at(-1);
  if (!latest || points.length < 2) return null;
  const target = window === "ytd"
    ? Date.UTC(latest.date.getUTCFullYear(), 0, 1)
    : latest.date.getTime() - Number(window) * 86_400_000;
  const previous = points.find((point) => point.date.getTime() >= target);
  if (!previous || previous === latest) return null;
  if (mode === "relative") {
    if (!(previous.value > 0) || !(latest.value > 0)) return null;
    return { mode, change: ((latest.value / previous.value) - 1) * 100 };
  }
  return { mode, change: latest.value - previous.value };
}

function formatSeriesChange(result) {
  const change = result?.change;
  if (!Number.isFinite(change)) return "—";
  if (result.mode === "relative") return signed(change);
  const sign = change > 0 ? "+" : change < 0 ? "-" : "";
  if (result.mode === "points") return `${sign}${Math.abs(change).toFixed(1)}pp`;
  return `${sign}${formatReadableNumber(Math.abs(change))}`;
}

function seriesLatestValue(series, anchor = null) {
  const values = seriesValueArray(series);
  const limit = Number.isFinite(Number(anchor)) && anchor !== null ? Number(anchor) : Infinity;
  for (let index = values.length - 1; index >= 0; index -= 1) {
    if (!Number.isFinite(toFiniteNumber(values[index]))) continue;
    if (Array.isArray(series.x) && Number.isFinite(limit) && series.orientation !== "h") {
      const time = comparableX(series.x[index]);
      if (Number.isFinite(time) && time > limit) continue;
    }
    return values[index];
  }
  return null;
}

// Units come from the series' own hover template, so the sidebar, readout,
// and data sheet show "$73,136" and "193%" exactly as the tooltip does.
function seriesDisplayValue(series, value) {
  const name = ["candlestick", "ohlc"].includes(series?.type) ? `${series.name} price` : series?.name;
  return formatHoverMetricValue(name, value, series?.hovertemplate || "");
}

const SAFE_COLOR_PATTERN = /^(#[0-9a-f]{3,8}|(rgb|hsl)a?\(\s*[-+\d.%\s,/deg]+\)|[a-z]{3,24})$/i;
const SERIES_PALETTE = ["#c85f3c", "#2863a7", "#16844d", "#c91f50", "#7c5ca8"];

// Upstream colours are data, not markup. Only plain CSS colour syntax survives;
// anything else falls back to the palette before it reaches a style attribute.
function safeCssColor(value, fallback) {
  if (typeof value !== "string") return fallback;
  const color = value.trim();
  if (!color || color.length > 64 || !SAFE_COLOR_PATTERN.test(color)) return fallback;
  if (typeof CSS !== "undefined" && typeof CSS.supports === "function" && !CSS.supports("color", color)) return fallback;
  return color;
}

function seriesColor(series, index) {
  const legacyMap = { "#f5c84b": "#c85f3c", "#55d6ff": "#2863a7", "#3ce38a": "#16844d", "#ff5f63": "#c91f50", "#ff9f43": "#d98945", "#ff5ccd": "#9d4c83", "#eef3f8": document.documentElement?.dataset?.theme === "dark" ? "#eef3f8" : "#393732" };
  const color = series?.line?.color || (typeof series?.marker?.color === "string" ? series.marker.color : null);
  const fallback = SERIES_PALETTE[Math.abs(Number(index) || 0) % SERIES_PALETTE.length];
  return safeCssColor(legacyMap[typeof color === "string" ? color.toLowerCase() : ""] || color, fallback);
}

async function renderSignalsPage() {
  const state = await loadSignalState();
  const categoryFilter = document.querySelector("#signal-category-filter");
  const phaseFilter = document.querySelector("#signal-phase-filter");
  const categories = [...new Set(state.signals.map((signal) => signal.category))].sort();
  categoryFilter.insertAdjacentHTML("beforeend", categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join(""));
  const refresh = () => updateSignalsPage(categoryFilter.value, phaseFilter.value);
  categoryFilter.addEventListener("change", refresh);
  phaseFilter.addEventListener("change", refresh);
  renderFreshness(document.querySelector("#signals-freshness"), state, { detail: true });
  renderSignalMethod(state);
  updateSignalsPage("all", "all");
}

function updateSignalsPage(category, phase) {
  const state = appState.signalState;
  const signals = appState.signals.filter((signal) => {
    const matchesCategory = category === "all" || signal.category === category;
    const matchesPhase = phase === "all" || signal.phase.key === phase;
    return matchesCategory && matchesPhase;
  });
  const indexRow = compositeSignal(state);
  renderSignalHeatmap(document.querySelector("#signal-page-heatmap"), indexRow && signals.length ? [indexRow, ...signals] : signals, 68);
  renderCycleSpectrum(signals, state);
  renderSignalSummary(signals, state);
  renderSignalTable(signals);
  renderSignalInsights(signals);
}

// The headline Cycle Index always comes from the canonical composite. Averages
// of whatever a filter happens to show are labelled as such, never as the index.
function compositeMembershipLabel(composite) {
  if (!composite) return "";
  const count = composite.membersUsed === composite.membersTotal
    ? `${composite.membersTotal}`
    : `${composite.membersUsed} of ${composite.membersTotal}`;
  return `${count} signals · equal weight`;
}

function shownAverageLabel(signals) {
  if (!signals.length) return "";
  const shown = average(signals.map((signal) => signal.score));
  return `Average of ${signals.length} shown: ${Math.round(shown)}`;
}

function renderCycleSpectrum(signals, state = appState.signalState) {
  const target = document.querySelector("#cycle-spectrum");
  target.classList.remove("loading-block");
  if (!signals.length) {
    target.innerHTML = `<p class="empty-state">No signals match these filters.</p>`;
    return;
  }
  const index = toFiniteNumber(state?.composite?.score);
  const dots = signals.map((signal, rowIndex) => {
    const score = clamp(signal.score, 0, 100);
    const height = 24 + (rowIndex % 5) * 13;
    const color = phaseColor(signal.phase.key);
    const membership = signal.composite ? "in Cycle Index" : "not in Cycle Index";
    return `
      <span class="spectrum-stem" style="left:clamp(36px, ${score}%, calc(100% - 36px)); --stem-height:${height}px"></span>
      <a class="spectrum-dot${signal.composite ? "" : " non-member"}" style="left:clamp(36px, ${score}%, calc(100% - 36px)); bottom:${35 + height}px; background:${color}" href="../charts/?chart=${encodeURIComponent(signal.chartId)}" title="${escapeHtml(signal.label)} · ${Math.round(score)} · ${membership}"></a>
    `;
  }).join("");
  const marker = Number.isFinite(index) ? `
    <span class="spectrum-index" style="left:clamp(36px, ${index}%, calc(100% - 36px))" title="Cycle Index ${Math.round(index)} · ${escapeHtml(compositeMembershipLabel(state.composite))}"></span>
    <span class="spectrum-index-label" style="left:clamp(48px, ${index}%, calc(100% - 48px))">INDEX ${Math.round(index)}</span>
  ` : "";
  target.innerHTML = `
    <div class="spectrum-track" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
    ${dots}
    ${marker}
    <div class="spectrum-labels"><span>Bottom</span><span>Bearish</span><span>Bullish</span><span>Top</span></div>
  `;
}

function renderSignalSummary(signals, state = appState.signalState) {
  const target = document.querySelector("#signal-summary");
  if (!signals.length) {
    target.innerHTML = `<p class="empty-state">No signal summary is available for the current filters.</p>`;
    return;
  }
  const counts = phaseCounts(signals);
  const composite = state?.composite;
  const index = toFiniteNumber(composite?.score);
  const bullish = signals.filter((signal) => signal.score >= 50).length;
  const withMomentum = signals.filter((signal) => Number.isFinite(signalDelta(signal, 30)));
  const rising = withMomentum.filter((signal) => signalDelta(signal, 30) > 0).length;
  const market = state?.market;
  const price = toFiniteNumber(market?.price);
  const indexCard = Number.isFinite(index)
    ? `<strong>${Math.round(index)}</strong><span class="summary-detail">${phaseFor(index).label} · ${escapeHtml(compositeMembershipLabel(composite))}</span><div class="position-meter" style="--position:${index}%"></div>`
    : `<strong>—</strong><span class="summary-detail">Unavailable: too few index signals have current data</span>`;
  target.innerHTML = `
    <article class="signal-summary-item"><small>Cycle Index</small>${indexCard}</article>
    <article class="signal-summary-item"><small>BTC price</small><strong>${Number.isFinite(price) ? formatUsd(price) : "Unavailable"}</strong>${Number.isFinite(price) ? sparklineSvg(market.recentPrices || []) : ""}</article>
    <article class="signal-summary-item"><small>Consensus</small><strong>${bullish}</strong><span class="summary-detail">/ ${signals.length} shown bullish</span><div class="metric-bar"><span style="width:${counts.bottom / signals.length * 100}%"></span><span style="width:${counts.bearish / signals.length * 100}%"></span><span style="width:${counts.bullish / signals.length * 100}%"></span><span style="width:${counts.top / signals.length * 100}%"></span></div></article>
    <article class="signal-summary-item"><small>30D momentum</small><strong>${withMomentum.length ? rising : "—"}</strong><span class="summary-detail">${withMomentum.length ? `/ ${withMomentum.length} rising` : "No 30-day history yet"}</span><div class="metric-bar"><span style="width:${withMomentum.length ? rising / withMomentum.length * 100 : 0}%; background:var(--green)"></span><span style="width:${withMomentum.length ? (withMomentum.length - rising) / withMomentum.length * 100 : 100}%; background:var(--surface-muted)"></span></div></article>
  `;
}

function signalMembershipNote(signal) {
  if (signal.composite) return "In Cycle Index";
  const exclusion = signal.exclusion || {};
  const twin = exclusion.of ? appState.signals.find((item) => item.id === exclusion.of)?.label || exclusion.of : "";
  const reason = {
    duplicate: twin ? `same quantity as ${twin}` : "duplicate quantity",
    structural_trend: "structural trend",
    non_directional: "not directional",
    short_horizon: "short horizon",
  }[exclusion.reason] || "not a member";
  return `Not in index: ${reason}`;
}

function renderSignalTable(signals) {
  const body = document.querySelector("#signal-table-body");
  const count = document.querySelector("#signal-table-count");
  count.textContent = [`${signals.length} signal${signals.length === 1 ? "" : "s"}`, shownAverageLabel(signals)].filter(Boolean).join(" · ");
  body.innerHTML = signals.map((signal) => {
    const deltas = [7, 30, 90, 365].map((days) => signalDelta(signal, days));
    const asOf = signal.date ? `as of ${formatDate(new Date(signal.date))}` : "";
    const stale = signal.stale ? ` <span class="stale-flag" title="Latest observation is ${signal.lagDays} days behind the newest data">stale</span>` : "";
    return `
      <tr data-chart-id="${escapeHtml(signal.chartId)}" data-signal-id="${escapeHtml(signal.id)}" tabindex="0">
        <td><strong>${escapeHtml(signal.label)}</strong><span class="summary-detail" title="${escapeHtml(signal.exclusion?.note || "")}">${escapeHtml(signal.category)} · ${escapeHtml(signalMembershipNote(signal))}${stale}</span></td>
        <td class="signal-value" title="${escapeHtml([formatSignalRaw(signal), asOf].filter(Boolean).join(" · "))}">${Math.round(signal.score)}</td>
        ${deltas.map((delta) => `<td class="signal-delta ${delta > 0 ? "positive" : delta < 0 ? "negative" : ""}"${Number.isFinite(delta) ? "" : ' title="Not enough scored history for this window"'}>${signedScore(delta)}</td>`).join("")}
        <td><span class="phase-pill ${signal.phase.className}">${signal.phase.label}</span></td>
        <td><div class="position-meter" style="--position:${signal.score}%" aria-label="Score ${Math.round(signal.score)} of 100"></div></td>
        <td>${sparklineSvg(signal.points.filter((point) => point.date >= oneYearBefore(last(signal.points).date)).map((point) => point.score), "signal-sparkline")}</td>
      </tr>
    `;
  }).join("") || `<tr><td colspan="9" class="empty-state">No signals match these filters.</td></tr>`;
  body.querySelectorAll("tr[data-chart-id]").forEach((row) => {
    const open = () => { window.location.href = `../charts/?chart=${encodeURIComponent(row.dataset.chartId)}`; };
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
    });
  });
}

function renderSignalInsights(signals) {
  const target = document.querySelector("#signal-insights");
  if (!signals.length) {
    target.innerHTML = "";
    return;
  }
  const byCategory = Object.groupBy
    ? Object.groupBy(signals, (signal) => signal.category)
    : signals.reduce((groups, signal) => {
      (groups[signal.category] ||= []).push(signal);
      return groups;
    }, {});
  const categoryRows = Object.entries(byCategory).map(([category, items]) => ({ category, score: average(items.map((item) => item.score)), count: items.length })).sort((a, b) => b.score - a.score);
  // A signal without 30 days of scored history has no 30-day move to rank.
  const movers = signals.map((signal) => ({ signal, delta: signalDelta(signal, 30) }))
    .filter(({ delta }) => Number.isFinite(delta))
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 5);
  const moverRows = movers.map(({ signal, delta }) => `<div class="insight-row"><span>${escapeHtml(signal.label)}</span><strong class="${delta < 0 ? "negative" : ""}">${signedScore(delta)}</strong></div>`).join("")
    || `<p class="empty-state">No shown signal has 30 days of scored history yet.</p>`;
  target.innerHTML = `
    <article class="insight-card"><h3>Category pulse</h3><div class="insight-list">${categoryRows.map((item) => `<div class="insight-row"><span>${escapeHtml(item.category)} · average of ${item.count} signal${item.count === 1 ? "" : "s"}</span><strong>${Math.round(item.score)} ${phaseFor(item.score).label}</strong></div>`).join("")}</div></article>
    <article class="insight-card"><h3>30D movers</h3><div class="insight-list">${moverRows}</div></article>
  `;
}

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${formatDate(date)}, ${shortTime(date)} UTC`;
}

// "Published" is when the site data was built; "Data through" is the newest
// observation inside it. They differ, so they are never merged into "Updated".
function renderFreshness(target, state, options = {}) {
  if (!target) return;
  const published = formatDateTime(appState.manifest?.generated_at);
  const parts = [published ? `Published ${published}` : "Publication time unavailable"];
  if (state?.dataThrough) parts.push(`Data through ${formatDate(new Date(state.dataThrough))}`);
  const stale = (state?.signals || []).filter((signal) => signal.stale);
  const unavailable = state?.unavailable || [];
  const names = (items) => (options.detail ? `: ${items.map((item) => item.label).join(", ")}` : "");
  if (stale.length) parts.push(`${stale.length} signal${stale.length === 1 ? "" : "s"} stale${names(stale)}`);
  if (unavailable.length) parts.push(`${unavailable.length} signal${unavailable.length === 1 ? "" : "s"} unavailable${names(unavailable)}`);
  target.textContent = parts.join(" · ");
  target.title = [
    ...stale.map((signal) => `${signal.label}: latest observation ${signal.date}, ${signal.lagDays} days behind`),
    ...unavailable.map((item) => `${item.label}: ${item.reason}`),
  ].join("\n");
  target.classList.toggle("has-data-warning", Boolean(stale.length || unavailable.length));
}

function renderSignalMethod(state) {
  const version = document.querySelector("#signal-method-version");
  const membership = document.querySelector("#signal-method-membership");
  const method = state?.method;
  if (version) version.textContent = method ? `Method v${method.version}${state.source === "fallback" ? " · computed in this browser" : ""}` : "";
  if (!membership || !method) return;
  const label = (id) => state.signals.find((signal) => signal.id === id)?.label
    || state.unavailable.find((item) => item.id === id)?.label
    || id;
  const reasons = {
    duplicate: "Same quantity as another member",
    structural_trend: "Structural trend",
    non_directional: "Not directional",
    short_horizon: "Short horizon",
  };
  const members = method.composite?.members || [];
  const excluded = method.composite?.excluded || [];
  membership.innerHTML = `
    <div>
      <h3>In the Cycle Index (${members.length}, equal weight)</h3>
      <ul>${members.map((id) => `<li>${escapeHtml(label(id))}</li>`).join("")}</ul>
    </div>
    <div>
      <h3>Shown but not counted (${excluded.length})</h3>
      <ul>${excluded.map((item) => `<li><strong>${escapeHtml(label(item.id))}</strong> — ${escapeHtml(reasons[item.reason] || "Not a member")}${item.of ? ` (${escapeHtml(label(item.of))})` : ""}. ${escapeHtml(item.note || "")}</li>`).join("")}</ul>
    </div>
  `;
}

async function renderAlertsPage() {
  const state = await loadSignalState();
  alertSession.seenAt = readAlertsSeenAt();
  const select = document.querySelector("#alert-signal");
  select.innerHTML = [
    `<option value="">Choose a signal…</option>`,
    ...state.signals.map((signal) => `<option value="${escapeHtml(signal.id)}">${escapeHtml(signal.label)}</option>`),
    ...state.unavailable.map((item) => `<option value="" disabled>${escapeHtml(item.label)} (unavailable)</option>`),
  ].join("");
  applyAlertRequest(state);

  const form = document.querySelector("#alert-form");
  form.addEventListener("input", updateAlertPreview);
  form.addEventListener("change", updateAlertPreview);
  form.addEventListener("submit", saveAlertFromForm);
  document.querySelector("#clear-alert-form").addEventListener("click", resetAlertForm);
  document.querySelector("#new-alert-button").addEventListener("click", () => {
    form.scrollIntoView({ behavior: "smooth", block: "start" });
    select.focus();
  });
  updateAlertPreview();
  renderAlertRules();
  updateAlertBadge(0);
}

// Resolve ?signal= / ?chart= to a signal. When the request cannot be honoured
// the form stays on "Choose a signal" and says why; it never substitutes a
// different signal.
function resolveAlertRequest(state, params = initialParams) {
  const signalId = params.get("signal");
  const chartId = params.get("chart");
  if (!signalId && !chartId) return { signalId: "", notice: "" };
  const signal = signalId
    ? state.signals.find((item) => item.id === signalId)
    : state.signals.find((item) => item.chartId === chartId);
  if (signal) return { signalId: signal.id, notice: "" };
  const missing = signalId
    ? state.unavailable.find((item) => item.id === signalId)
    : state.unavailable.find((item) => item.chartId === chartId);
  if (missing) {
    return { signalId: "", notice: `${missing.label} is unavailable in the latest data (${missing.reason}), so it was not selected. Choose another signal, or try again after the next data refresh.` };
  }
  if (signalId) return { signalId: "", notice: `There is no cycle signal named “${signalId}”. Choose a signal below.` };
  const title = chartById(chartId)?.title || chartId;
  return { signalId: "", notice: `${title} does not have a cycle score, so an alert cannot watch it directly. Choose one of the scored signals below.` };
}

function applyAlertRequest(state = appState.signalState) {
  const request = resolveAlertRequest(state);
  const select = document.querySelector("#alert-signal");
  if (select) select.value = request.signalId;
  const notice = document.querySelector("#alert-request-notice");
  if (notice) {
    notice.textContent = request.notice;
    notice.hidden = !request.notice;
  }
  return request;
}

function saveAlertFromForm(event) {
  event.preventDefault();
  const signalId = document.querySelector("#alert-signal").value;
  if (!appState.signals.some((signal) => signal.id === signalId)) {
    const status = document.querySelector("#alert-save-status");
    if (status) status.textContent = "Choose a signal before saving this alert.";
    return;
  }
  const operator = document.querySelector("#alert-operator").value;
  const threshold = clamp(Number(document.querySelector("#alert-threshold").value), 0, 100);
  const cadence = document.querySelector("#alert-cadence").value;
  const label = document.querySelector("#alert-label").value.trim();
  const rules = readAlertRules();
  rules.unshift({
    id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
    signalId,
    operator,
    threshold,
    cadence,
    label,
    enabled: true,
    createdAt: new Date().toISOString(),
  });
  if (!writeAlertRules(rules)) return;
  resetAlertForm();
  renderAlertRules();
}

function resetAlertForm() {
  const form = document.querySelector("#alert-form");
  form.reset();
  applyAlertRequest();
  document.querySelector("#alert-threshold").value = "75";
  updateAlertPreview();
}

function alertOperatorPhrase(operator) {
  return {
    above: "is above",
    below: "is below",
    "crosses-above": "crosses above",
    "crosses-below": "crosses below",
  }[operator] || String(operator).replaceAll("-", " ");
}

function updateAlertPreview() {
  const preview = document.querySelector("#alert-preview");
  if (!preview) return;
  const signal = appState.signals.find((item) => item.id === document.querySelector("#alert-signal")?.value);
  if (!signal) {
    preview.textContent = "Choose a signal to preview this rule.";
    return;
  }
  const operator = alertOperatorPhrase(document.querySelector("#alert-operator").value);
  const threshold = clamp(Number(document.querySelector("#alert-threshold").value), 0, 100);
  preview.innerHTML = `<strong>${escapeHtml(signal.label)}</strong> is currently ${Math.round(signal.score)} (${signal.phase.label}). This rule will trigger when its cycle score ${escapeHtml(operator)} ${threshold}. Rules are checked when you open the site.`;
}

function alertIsLevelRule(rule) {
  return rule.operator === "above" || rule.operator === "below";
}

function alertLevelMet(rule, score) {
  if (rule.operator === "above") return score > rule.threshold;
  if (rule.operator === "below") return score < rule.threshold;
  return false;
}

// Check one rule against the current score. Scores are only comparable within
// one scoring method, so an observation saved under another method version is
// replaced (re-baselined) without firing.
function checkAlertRule(rule, signal, methodVersion, now) {
  const idle = { rule, fired: false, rebaselined: false };
  if (!rule.enabled || (rule.cadence === "once" && rule.triggeredAt)) return idle;
  const current = signal?.score;
  if (!Number.isFinite(current)) return idle;
  const level = alertIsLevelRule(rule);
  const met = level ? alertLevelMet(rule, current) : undefined;
  const observed = { ...rule, lastScore: current, methodVersion };
  if (level) observed.conditionMet = met;
  else delete observed.conditionMet;
  if (Number.isFinite(rule.lastScore) && rule.methodVersion !== methodVersion) {
    return { rule: { ...observed, rebaselinedAt: now }, fired: false, rebaselined: true };
  }
  const previous = rule.lastScore;
  const fired = level
    ? met && rule.conditionMet !== true
    : Number.isFinite(previous) && (rule.operator === "crosses-above"
      ? previous <= rule.threshold && current > rule.threshold
      : rule.operator === "crosses-below" && previous >= rule.threshold && current < rule.threshold);
  if (!fired) return { rule: observed, fired: false, rebaselined: false };
  return {
    rule: { ...observed, firedAt: now, ...(rule.cadence === "once" ? { triggeredAt: now, enabled: false } : {}) },
    fired: true,
    rebaselined: false,
  };
}

function evaluateAlert(rule) {
  const signal = appState.signals.find((item) => item.id === rule.signalId);
  return checkAlertRule(rule, signal, appState.signalState?.method?.version, new Date().toISOString()).fired;
}

// Run every saved rule once against the loaded signals and persist the new
// observations. This runs on every page so a rule can fire wherever the site
// is opened; if the browser refuses the write, nothing is treated as saved.
function evaluateAlertRules(state = appState.signalState) {
  const rules = readAlertRules();
  const now = new Date().toISOString();
  const version = state?.method?.version;
  const signals = state?.signals || appState.signals || [];
  const results = rules.map((rule) => checkAlertRule(rule, signals.find((item) => item.id === rule.signalId), version, now));
  const next = results.map((result) => result.rule);
  const changed = JSON.stringify(next) !== JSON.stringify(rules);
  const saved = !changed || writeAlertRules(next);
  return { rules: saved ? next : rules, results, saved };
}

async function checkAlertsInBackground() {
  try {
    if (!readAlertRules().length) return;
    const state = await loadSignalState();
    const { rules } = evaluateAlertRules(state);
    const seenAt = readAlertsSeenAt();
    updateAlertBadge(rules.filter((rule) => rule.firedAt && rule.firedAt > seenAt).length);
  } catch (error) {
    console.warn("Alert check unavailable", error);
  }
}

function updateAlertBadge(count) {
  const link = document.querySelector?.('.terminal-nav a[href$="alerts/"]');
  if (!link) return;
  let badge = link.querySelector(".nav-badge");
  if (!count) {
    badge?.remove();
    link.removeAttribute("title");
    return;
  }
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "nav-badge";
    link.append(badge);
  }
  const summary = `${count} alert${count === 1 ? "" : "s"} fired since you last opened Alerts`;
  badge.textContent = String(count);
  badge.setAttribute("aria-label", summary);
  link.title = `${summary} · checked when you open the site`;
}

// Every saved firing on screen has now been shown to the visitor, so it must
// not come back as an unseen count on another page. This runs on each render
// of the Alerts page, including after a rule is created or re-armed; the
// in-page highlight keeps using the visit's original `alertSession.seenAt`.
function acknowledgeDisplayedAlerts(rules) {
  const latest = rules.reduce((newest, rule) => (rule.firedAt && rule.firedAt > newest ? rule.firedAt : newest), "");
  if (!latest || latest <= readAlertsSeenAt()) return;
  const now = new Date().toISOString();
  writeAlertsSeenAt(now > latest ? now : latest);
}

function renderAlertRules() {
  const outcome = evaluateAlertRules();
  outcome.results.forEach((result) => { if (result.fired) alertSession.fired.add(result.rule.id); });
  const rules = outcome.rules;
  // `rules` holds only what was actually saved, so an unsaved firing is not acknowledged.
  acknowledgeDisplayedAlerts(rules);
  const list = document.querySelector("#alert-list");
  const view = rules.map((rule) => {
    const signal = appState.signals.find((item) => item.id === rule.signalId);
    const fresh = alertSession.fired.has(rule.id) || Boolean(rule.firedAt && rule.firedAt > alertSession.seenAt);
    const met = rule.enabled && alertIsLevelRule(rule) && Number.isFinite(signal?.score) && alertLevelMet(rule, signal.score);
    return { rule, signal, fresh, met };
  });
  const active = rules.filter((rule) => rule.enabled).length;
  const triggered = view.filter((item) => item.fresh || item.met).length;
  document.querySelector("#alert-count").textContent = `${rules.length} alert${rules.length === 1 ? "" : "s"}`;
  document.querySelector("#alert-overview").innerHTML = `
    <article class="alert-overview-item"><div><small>Active rules</small><strong>${active}</strong></div><span class="overview-icon" aria-hidden="true">♧</span></article>
    <article class="alert-overview-item"><div><small>Conditions met</small><strong>${triggered}</strong></div><span class="overview-icon" aria-hidden="true">●</span></article>
    <article class="alert-overview-item"><div><small>Last checked</small><strong>${shortTime(new Date())}</strong></div><span class="overview-icon" aria-hidden="true">↻</span></article>
  `;

  if (!rules.length) {
    list.innerHTML = `<div class="alert-empty"><div><strong>No alert rules yet</strong><p>Create a rule to watch one of the normalized cycle signals. Rules stay private in this browser.</p></div></div>`;
    return;
  }

  list.innerHTML = view.map(({ rule, signal, fresh, met }) => {
    const missing = appState.signalState?.unavailable?.find((item) => item.id === rule.signalId);
    const title = rule.label || signal?.label || (missing ? `${missing.label} (unavailable)` : "Unknown signal");
    const status = fresh ? "Triggered since your last visit" : rule.triggeredAt ? "Completed" : met ? "Condition met" : rule.enabled ? "Watching" : "Paused";
    return `
      <article class="alert-rule ${fresh || met ? "triggered" : ""}">
        <span class="alert-rule-status" title="${status}"></span>
        <div class="alert-rule-copy"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(alertRuleText(rule, signal))}</span></div>
        <div class="alert-rule-actions">
          <label class="switch-control" title="Enable or pause alert"><input type="checkbox" aria-label="Enable ${escapeHtml(title)} alert" data-alert-toggle="${escapeHtml(rule.id)}" ${rule.enabled ? "checked" : ""}><span class="switch-track"></span></label>
          <button type="button" data-alert-delete="${escapeHtml(rule.id)}" aria-label="Delete ${escapeHtml(title)}">Delete</button>
        </div>
      </article>
    `;
  }).join("");

  list.querySelectorAll("[data-alert-toggle]").forEach((control) => {
    control.addEventListener("change", () => {
      const next = readAlertRules().map((rule) => {
        if (rule.id !== control.dataset.alertToggle) return rule;
        const updated = { ...rule, enabled: control.checked };
        if (control.checked) {
          // Re-arming starts a fresh watch: forget the earlier observation.
          ["triggeredAt", "firedAt", "lastScore", "methodVersion", "conditionMet", "rebaselinedAt"].forEach((key) => delete updated[key]);
        }
        return updated;
      });
      if (!writeAlertRules(next)) { control.checked = !control.checked; return; }
      if (control.checked) alertSession.fired.delete(control.dataset.alertToggle);
      renderAlertRules();
    });
  });
  list.querySelectorAll("[data-alert-delete]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!writeAlertRules(readAlertRules().filter((rule) => rule.id !== button.dataset.alertDelete))) return;
      renderAlertRules();
    });
  });
}

function alertRuleText(rule, signal) {
  const current = signal ? Math.round(signal.score) : "—";
  const state = rule.triggeredAt
    ? "Completed — toggle on to re-arm"
    : rule.cadence === "once" ? "once" : "every time the site is opened";
  const rebaselined = rule.rebaselinedAt && !rule.triggeredAt
    ? ` · re-baselined for scoring method v${rule.methodVersion}; review this threshold`
    : "";
  return `Score ${alertOperatorPhrase(rule.operator)} ${rule.threshold} · now ${current} · ${state}${rebaselined}`;
}

function readAlertRules() {
  try {
    const value = JSON.parse(localStorage.getItem(ALERT_RULES_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function writeAlertRules(rules) {
  const status = document.querySelector?.("#alert-save-status");
  try {
    localStorage.setItem(ALERT_RULES_KEY, JSON.stringify(rules));
    if (status) status.textContent = "";
    return true;
  } catch {
    if (status) status.textContent = "Alert changes could not be saved in this browser. Completion and observations are not persisted; retry when browser storage is available.";
    return false;
  }
}

function readAlertsSeenAt() {
  try {
    return localStorage.getItem(ALERT_SEEN_KEY) || "";
  } catch {
    return "";
  }
}

function writeAlertsSeenAt(value) {
  try {
    localStorage.setItem(ALERT_SEEN_KEY, value);
    return true;
  } catch {
    return false;
  }
}

// Score change over a look-back window. The site build only fills a window
// when scored history actually reaches back that far; otherwise it is null and
// shown as unavailable rather than measured from the first observation.
function signalDelta(signal, days) {
  const change = signal?.changes?.[days];
  return typeof change === "number" && Number.isFinite(change) ? change : null;
}

function oneYearBefore(date) {
  const target = new Date(date);
  target.setUTCFullYear(target.getUTCFullYear() - 1);
  return target.toISOString();
}

function phaseColor(key) {
  return { bottom: "#2863a7", bearish: "#9fc3ea", bullish: "#ee9fb5", top: "#c91f50" }[key] || "#98958e";
}

function formatSignalRaw(signal) {
  const value = toFiniteNumber(signal.rawValue);
  if (!Number.isFinite(value)) return "Unavailable";
  const decimals = Number.isInteger(signal.decimals) ? signal.decimals : (Math.abs(value) >= 100 ? 0 : 2);
  if (signal.unit === "multiple") return `${value.toFixed(decimals)}x`;
  if (signal.unit === "percent") return `${value.toFixed(decimals)}%`;
  if (signal.unit === "band_position") return `${(value * 100).toFixed(0)}% of band`;
  if (signal.unit === "days") return `${Math.round(value)} days`;
  if (signal.unit === "sat_per_vbyte") return `${value.toFixed(decimals)} sat/vB`;
  if (signal.unit === "usd") return formatUsd(value);
  return value.toFixed(decimals);
}

function signedScore(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const rounded = Math.round(value);
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

function formatMetricValue(name, value) {
  const number = toFiniteNumber(value);
  if (!Number.isFinite(number)) return "—";
  const label = String(name || "").toLowerCase();
  if (label.includes("price") || label.includes("usd") || label.includes("cost basis")) return formatReadableUsd(number);
  if (label.includes("percent") || label.includes("return") || label.includes("drawdown") || label.includes("volatility") || label.includes("share")) return `${number.toFixed(1)}%`;
  return formatReadableNumber(number);
}

function formatHoverMetricValue(name, value, sourceTemplate = "") {
  const number = toFiniteNumber(value);
  if (!Number.isFinite(number)) return "—";
  const label = String(name || "").toLowerCase();
  const template = String(sourceTemplate || "");
  const isCurrency = label.includes("price")
    || label.includes("usd")
    || label.includes("cost basis")
    || label.includes("hashprice")
    || template.includes("$%{");
  if (isCurrency) return formatReadableUsd(number);
  const formatted = formatReadableNumber(number);
  if (/}\s*pp\b/i.test(template)) return `${formatted} pp`;
  if (label.includes("percent")
      || label.includes("return")
      || label.includes("drawdown")
      || label.includes("volatility")
      || label.includes("share")
      || /}\s*%/.test(template)) return `${formatted}%`;
  if (label.includes("[btc]") || /}\s*btc\b/i.test(template)) return `${formatted} BTC`;
  if (/}\s*sat\/vb\b/i.test(template)) return `${formatted} sat/vB`;
  if (/}\s*sats?\b/i.test(template)) return `${formatted} sats`;
  if (label.includes("days") || /}\s*days?\b/i.test(template)) return `${formatted} days`;
  if (label.includes("multiple") || /}\s*x\b/i.test(template)) return `${formatted}x`;
  return formatted;
}

function formatReadableUsd(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (Math.abs(number) >= 1_000_000) {
    const sign = number < 0 ? "-" : "";
    return `${sign}$${formatReadableNumber(Math.abs(number))}`;
  }
  return formatUsd(number);
}

function formatReadableNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const absolute = Math.abs(number);
  const unit = [
    [1_000_000_000_000, "T"],
    [1_000_000_000, "B"],
    [1_000_000, "M"],
    [1_000, "K"],
  ].find(([threshold]) => absolute >= threshold);
  if (unit) {
    const [threshold, suffix] = unit;
    return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(number / threshold)}${suffix}`;
  }
  if (absolute >= 100) return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(number);
  if (absolute >= 10) return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(number);
  if (absolute >= 1) return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(number);
  if (absolute === 0) return "0";
  return new Intl.NumberFormat("en-US", { maximumSignificantDigits: 3 }).format(number);
}

function shortDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value ?? "");
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "2-digit", timeZone: "UTC" }).format(date);
}

function shortTime(date) {
  return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }).format(date);
}

// The manifest names the artifact it was built with. Without that entry the
// artifact is looked for beside the manifest.
function signalsArtifactPath(manifest = appState.manifest) {
  const declared = manifest?.signals?.path;
  if (typeof declared === "string" && declared) return assetPath(declared);
  return pageConfig.manifestPath.replace(/[^/]*$/, SIGNALS_ARTIFACT_NAME);
}

// Reject anything that is not a complete, current artifact so the caller can
// fall back to scoring chart payloads instead of rendering half a page.
function signalsArtifactProblem(artifact, manifest = appState.manifest) {
  if (!artifact || typeof artifact !== "object") return "not an object";
  if (artifact.schema_version !== SIGNALS_ARTIFACT_SCHEMA) return `unsupported schema ${artifact.schema_version}`;
  if (!Number.isFinite(artifact.method?.version) || !Array.isArray(artifact.method?.phases)) return "missing method";
  if (!Array.isArray(artifact.history?.dates)) return "missing history dates";
  if (!Array.isArray(artifact.signals) || !Array.isArray(artifact.unavailable)) return "missing signals";
  if (!artifact.signals.length) return "no signals";
  const dates = artifact.history.dates.length;
  const broken = artifact.signals.find((signal) => (
    typeof signal?.id !== "string"
    || typeof signal.chart_id !== "string"
    || !Number.isFinite(signal.score)
    || !Array.isArray(signal.history?.scores)
    || signal.history.scores.length !== dates
  ));
  if (broken) return `invalid signal ${broken?.id ?? ""}`.trim();
  // The artifact carries no clock reading. It is identified by a fingerprint
  // of its inputs, and the manifest it was published with repeats that
  // fingerprint, so an artifact left over from another build is rejected.
  if (typeof artifact.source_fingerprint !== "string" || !artifact.source_fingerprint) return "missing source fingerprint";
  const expected = manifest?.signals?.source_fingerprint;
  if (expected && expected !== artifact.source_fingerprint) return "built from different data than the published manifest";
  return "";
}

let signalStatePromise = null;

// One compact request replaces a full chart payload per signal. The per-chart
// path remains only as a fallback for a missing or invalid artifact.
function loadSignalState() {
  signalStatePromise ||= (async () => {
    let state = null;
    try {
      // A manifest that records "no artifact" means the build could not make one.
      if (appState.manifest?.signals === null) throw new Error("the site build did not publish a signal artifact");
      const artifact = await fetchJson(signalsArtifactPath());
      const problem = signalsArtifactProblem(artifact);
      if (problem) throw new Error(problem);
      state = hydrateSignalState(artifact, "artifact");
    } catch (error) {
      console.warn("Signal artifact unavailable; scoring chart payloads in the browser instead.", error);
      state = hydrateSignalState(await buildSignalsFromCharts(), "fallback");
    }
    appState.signalState = state;
    appState.signals = state.signals;
    return state;
  })().catch((error) => {
    signalStatePromise = null;
    throw error;
  });
  return signalStatePromise;
}

async function buildSignals() {
  return (await loadSignalState()).signals;
}

async function buildSignalsFromCharts() {
  const definitions = await fetchJson(assetPath(SIGNAL_DEFINITIONS_PATH));
  const chartIds = [...new Set([
    ...definitions.signals.map((definition) => definition.chart_id),
    definitions.market?.chart_id,
  ].filter(Boolean))];
  const payloads = new Map(await Promise.all(chartIds.map(async (chartId) => {
    try {
      return [chartId, await getPayload(chartId)];
    } catch (error) {
      console.warn(`Signal chart unavailable: ${chartId}`, error);
      return [chartId, null];
    }
  })));
  return buildSignalsArtifact(definitions, (chartId) => payloads.get(chartId) ?? null);
}

function hydrateSignalState(artifact, source) {
  const dates = artifact.history.dates;
  // `samples` keeps every weekly sample, including unavailable (null) ones, so
  // a gap in the data stays a gap. `points` is the scored subset.
  const samples = (history) => dates.map((date, index) => ({
    date,
    value: history?.values?.[index] ?? null,
    score: history?.scores?.[index] ?? null,
  }));
  const scored = (items) => items.filter((point) => Number.isFinite(point.score));
  const method = artifact.method;
  const phase = (score) => phaseFor(score, method.phases);
  const signals = artifact.signals.map((signal) => ({
    id: signal.id,
    chartId: signal.chart_id,
    label: signal.label,
    category: signal.category,
    source: signal.source,
    unit: signal.unit,
    decimals: signal.decimals,
    invert: Boolean(signal.invert),
    score: signal.score,
    rawValue: signal.value,
    date: signal.date,
    phase: phase(signal.score),
    changes: signal.changes || {},
    stale: Boolean(signal.stale),
    lagDays: signal.lag_days,
    composite: Boolean(signal.composite),
    exclusion: signal.exclusion || null,
    firstDate: signal.first_date,
    observations: signal.observations,
    samples: samples(signal.history),
    points: scored(samples(signal.history)),
  }));
  const composite = artifact.composite ? {
    id: artifact.composite.id,
    label: artifact.composite.label,
    chartId: artifact.composite.chart_id,
    date: artifact.composite.date,
    score: artifact.composite.score,
    phase: Number.isFinite(artifact.composite.score) ? phase(artifact.composite.score) : null,
    changes: artifact.composite.changes || {},
    membersTotal: artifact.composite.members_total,
    membersUsed: artifact.composite.members_used,
    missingMembers: artifact.composite.missing_members || [],
    staleMembers: artifact.composite.stale_members || [],
    samples: samples(artifact.composite.history),
    points: scored(samples(artifact.composite.history)),
  } : null;
  const market = artifact.market ? {
    date: artifact.market.date,
    price: artifact.market.price,
    change30dPct: artifact.market.change_30d_pct,
    average200d: artifact.market.average_200d,
    distance200dPct: artifact.market.distance_200d_pct,
    recentPrices: artifact.market.recent?.prices || [],
    recentRatios: artifact.market.recent?.ratios || [],
  } : null;
  return {
    source,
    sourceFingerprint: artifact.source_fingerprint ?? null,
    dataThrough: artifact.data_through,
    method,
    signals,
    composite,
    market,
    unavailable: (artifact.unavailable || []).map((item) => ({
      id: item.id,
      chartId: item.chart_id,
      label: item.label,
      composite: Boolean(item.composite),
      reason: item.reason,
    })),
  };
}

// The canonical Cycle Index as a heatmap/table row.
function compositeSignal(state) {
  const composite = state?.composite;
  if (!composite || !Number.isFinite(composite.score)) return null;
  return {
    id: composite.id,
    chartId: composite.chartId,
    label: composite.label,
    category: "Composite",
    samples: composite.samples,
    points: composite.points,
    score: composite.score,
    rawValue: composite.score,
    phase: composite.phase,
    changes: composite.changes,
    composite: false,
  };
}

function buildDashboardSignalSet(state) {
  const signals = state?.signals || [];
  const members = signals.filter((signal) => signal.composite);
  const index = compositeSignal(state);
  if (index) return [index, ...members];
  return members.length ? members : signals;
}

// ---------------------------------------------------------------------------
// Browser port of web/signals_artifact.py. It is only used when signals.json
// is unavailable, and both implementations are pinned to the same golden
// fixture (web/tests/fixtures/signals), so keep the two in step.
// ---------------------------------------------------------------------------

function signalDay(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  const time = Date.UTC(year, month - 1, day);
  const check = new Date(time);
  if (check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) return null;
  return Math.round(time / 86400000);
}

function signalDate(day) {
  return new Date(day * 86400000).toISOString().slice(0, 10);
}

function signalNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

// One rounding rule for every published number: half away from zero on the
// exact value. toFixed and toPrecision both work that way, and the site build
// does the same with decimal arithmetic. Adding 0 turns -0 into 0.
function roundDecimals(value, decimals) {
  return Number(value.toFixed(decimals)) + 0;
}

function roundSignalScore(value) {
  return value === null || value === undefined ? null : roundDecimals(value, 1);
}

function roundSignificant(value, digits) {
  return value === null || value === undefined ? null : Number(value.toPrecision(digits)) + 0;
}

function selectSignalSeries(payload, selector) {
  if (!Array.isArray(payload?.series) || !selector || typeof selector !== "object") return null;
  return payload.series.find((series) => series && typeof series === "object" && (
    ("key" in selector && series.source_key === selector.key)
    || ("name" in selector && series.name === selector.name)
  )) || null;
}

function describeSignalSelector(selector) {
  if (selector && typeof selector === "object" && "key" in selector) return `source key '${selector.key}'`;
  if (selector && typeof selector === "object" && "name" in selector) return `series '${selector.name}'`;
  return "an unspecified series";
}

// Observation day -> value. A later duplicate date supersedes an earlier one;
// a missing or non-finite observation never erases a real one.
function signalSeriesByDay(series) {
  const byDay = new Map();
  if (!Array.isArray(series?.x) || !Array.isArray(series?.y)) return byDay;
  const length = Math.min(series.x.length, series.y.length);
  for (let index = 0; index < length; index += 1) {
    const day = signalDay(series.x[index]);
    const value = signalNumber(series.y[index]);
    if (day === null || value === null) continue;
    byDay.set(day, value);
  }
  return byDay;
}

function requiredSignalSeries(payload, selector, chartId) {
  const series = selectSignalSeries(payload, selector);
  if (!series) throw new Error(`${describeSignalSelector(selector)} is missing from chart '${chartId}'`);
  return signalSeriesByDay(series);
}

function sortedDays(byDay) {
  return [...byDay.keys()].sort((left, right) => left - right);
}

// Derived indicators are joined on the observation date, never on array
// position, so a shifted, missing or duplicated row cannot pair a numerator
// with another day's denominator.
function resolveSignalObservations(definition, payload) {
  const chartId = definition.chart_id;
  if (!payload || typeof payload !== "object") throw new Error(`chart data for '${chartId}' is unavailable`);
  const source = definition.input || {};
  const days = [];
  const values = [];
  if (source.type === "series") {
    const series = requiredSignalSeries(payload, source.series, chartId);
    sortedDays(series).forEach((day) => { days.push(day); values.push(series.get(day)); });
  } else if (source.type === "ratio") {
    const numerator = requiredSignalSeries(payload, source.numerator, chartId);
    const denominator = requiredSignalSeries(payload, source.denominator, chartId);
    sortedDays(numerator).forEach((day) => {
      const divisor = denominator.get(day);
      if (divisor === undefined || divisor === 0) return;
      days.push(day);
      values.push(numerator.get(day) / divisor);
    });
  } else if (source.type === "band_position") {
    const value = requiredSignalSeries(payload, source.value, chartId);
    const lower = requiredSignalSeries(payload, source.lower, chartId);
    const upper = requiredSignalSeries(payload, source.upper, chartId);
    sortedDays(value).forEach((day) => {
      const low = lower.get(day);
      const high = upper.get(day);
      if (low === undefined || high === undefined || high === low) return;
      days.push(day);
      values.push((value.get(day) - low) / (high - low));
    });
  } else {
    throw new Error(`unsupported input type '${source.type}'`);
  }
  return { days, values };
}

function lowerBound(sorted, value) {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (sorted[middle] < value) low = middle + 1;
    else high = middle;
  }
  return low;
}

function upperBound(sorted, value) {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (sorted[middle] <= value) low = middle + 1;
    else high = middle;
  }
  return low;
}

// Point-in-time percentile rank: each observation is ranked (ties at mid-rank)
// against the observations up to and including its own date only.
function expandingSignalScores(days, values, scoring, invert = false) {
  const minDays = scoring.min_history_days ?? 0;
  const minObservations = scoring.min_observations ?? 1;
  const ordered = [];
  const firstDay = days[0] ?? 0;
  return values.map((value, index) => {
    ordered.splice(upperBound(ordered, value), 0, value);
    const count = ordered.length;
    if (days[index] - firstDay < minDays || count < minObservations) return null;
    const below = lowerBound(ordered, value);
    const equal = upperBound(ordered, value) - below;
    const rank = 100 * (below + 0.5 * equal) / count;
    return invert ? 100 - rank : rank;
  });
}

// Index of the latest observation on or before `target` that is still recent
// enough to stand in for it; null when the window is not covered.
function asOfIndex(days, target, carryForwardDays) {
  const index = upperBound(days, target) - 1;
  if (index < 0 || target - days[index] > carryForwardDays) return null;
  return index;
}

function buildSignalMarket(market, payloadFor, carryForwardDays) {
  if (!market || typeof market !== "object") return null;
  let prices;
  let averages;
  try {
    const payload = payloadFor(market.chart_id);
    if (!payload || typeof payload !== "object") return null;
    prices = requiredSignalSeries(payload, market.price, market.chart_id);
    averages = requiredSignalSeries(payload, market.average, market.chart_id);
  } catch {
    return null;
  }
  const days = sortedDays(prices);
  if (!days.length) return null;
  const latestDay = days[days.length - 1];
  const price = prices.get(latestDay);
  const average = averages.get(latestDay);
  const monthIndex = asOfIndex(days, latestDay - 30, carryForwardDays);
  const monthPrice = monthIndex === null ? null : prices.get(days[monthIndex]);
  const recentDays = days.slice(-(market.recent_observations ?? 60));
  return {
    date: signalDate(latestDay),
    price: roundDecimals(price, 2),
    change_30d_pct: monthPrice ? roundDecimals((price / monthPrice - 1) * 100, 2) : null,
    average_200d: average === undefined ? null : roundDecimals(average, 2),
    distance_200d_pct: average ? roundDecimals((price / average - 1) * 100, 2) : null,
    recent: {
      dates: recentDays.map(signalDate),
      prices: recentDays.map((day) => roundDecimals(prices.get(day), 2)),
      ratios: recentDays.map((day) => (averages.get(day) ? roundDecimals(prices.get(day) / averages.get(day), 4) : null)),
    },
  };
}

function buildSignalsArtifact(definitions, loadPayload) {
  const method = definitions.method;
  const { scoring, phases } = method;
  const windows = method.change_windows_days;
  const stepDays = method.history.step_days;
  const carry = method.history.carry_forward_days;
  const digits = method.history.value_significant_digits;
  const sourceRules = method.freshness.sources;
  const compositeConfig = method.composite;

  const resolved = [];
  const unavailable = [];
  definitions.signals.forEach((definition) => {
    try {
      const { days, values } = resolveSignalObservations(definition, loadPayload(definition.chart_id));
      if (!days.length) throw new Error("no finite observations");
      const scores = expandingSignalScores(days, values, scoring, Boolean(definition.invert));
      if (scores[scores.length - 1] === null) throw new Error("history is shorter than the scoring minimum");
      resolved.push({ definition, days, values, scores });
    } catch (error) {
      unavailable.push({
        id: definition.id,
        chart_id: definition.chart_id,
        label: definition.label,
        composite: Boolean(definition.composite),
        reason: error.message,
      });
    }
  });

  const market = buildSignalMarket(definitions.market, loadPayload, carry);
  const latestDays = resolved.map((item) => item.days[item.days.length - 1]);
  if (market) latestDays.push(signalDay(market.date));
  const dataThrough = latestDays.length ? Math.max(...latestDays) : null;

  const grid = [];
  if (resolved.length) {
    const firstScored = Math.min(...resolved.map((item) => item.days[item.scores.findIndex((score) => score !== null)]));
    for (let day = dataThrough; day >= firstScored; day -= stepDays) grid.push(day);
    grid.reverse();
  }

  const sample = (item, key, target) => {
    const index = asOfIndex(item.days, target, carry);
    return index === null ? null : item[key][index];
  };

  const signals = resolved.map((item) => {
    const { definition, days, values, scores } = item;
    const latestDay = days[days.length - 1];
    const latestScore = scores[scores.length - 1];
    const changes = {};
    windows.forEach((window) => {
      const earlier = sample(item, "scores", latestDay - window);
      changes[String(window)] = earlier === null ? null : roundSignalScore(latestScore - earlier);
    });
    const lagDays = dataThrough - latestDay;
    const staleAfter = sourceRules[definition.source]?.stale_after_days ?? 2;
    const score = roundSignalScore(latestScore);
    return {
      id: definition.id,
      chart_id: definition.chart_id,
      label: definition.label,
      category: definition.category,
      source: definition.source ?? null,
      unit: definition.unit ?? null,
      decimals: definition.decimals ?? null,
      invert: Boolean(definition.invert),
      value: roundDecimals(values[values.length - 1], 6),
      date: signalDate(latestDay),
      score,
      phase: phaseFor(score, phases).key,
      changes,
      lag_days: lagDays,
      stale: lagDays > staleAfter,
      composite: Boolean(definition.composite),
      exclusion: definition.exclusion ?? null,
      first_date: signalDate(days[0]),
      observations: days.length,
      history: {
        scores: grid.map((day) => roundSignalScore(sample(item, "scores", day))),
        values: grid.map((day) => roundSignificant(sample(item, "values", day), digits)),
      },
    };
  });

  const members = resolved.filter((item) => item.definition.composite);
  const memberIds = definitions.signals.filter((definition) => definition.composite).map((definition) => definition.id);
  const compositeAt = (target) => {
    let total = 0;
    const used = [];
    members.forEach((item) => {
      const score = sample(item, "scores", target);
      if (score === null) return;
      total += score;
      used.push(item.definition.id);
    });
    if (!used.length || used.length < compositeConfig.min_members) return { score: null, used };
    return { score: total / used.length, used };
  };

  let composite = null;
  if (dataThrough !== null) {
    const current = compositeAt(dataThrough);
    const changes = {};
    windows.forEach((window) => {
      const earlier = compositeAt(dataThrough - window).score;
      changes[String(window)] = current.score === null || earlier === null ? null : roundSignalScore(current.score - earlier);
    });
    const score = roundSignalScore(current.score);
    composite = {
      id: compositeConfig.id,
      label: compositeConfig.label,
      chart_id: compositeConfig.chart_id ?? null,
      date: signalDate(dataThrough),
      score,
      phase: score === null ? null : phaseFor(score, phases).key,
      changes,
      members_total: memberIds.length,
      members_used: current.used.length,
      missing_members: memberIds.filter((id) => !current.used.includes(id)),
      stale_members: signals.filter((signal) => signal.composite && signal.stale).map((signal) => signal.id),
      history: { scores: grid.map((day) => roundSignalScore(compositeAt(day).score)) },
    };
  }

  const publishedMethod = JSON.parse(JSON.stringify(method));
  publishedMethod.composite.members = memberIds;
  publishedMethod.composite.excluded = definitions.signals
    .filter((definition) => !definition.composite)
    .map((definition) => ({ id: definition.id, ...(definition.exclusion || {}) }));
  return {
    schema_version: SIGNALS_ARTIFACT_SCHEMA,
    // Only the site build fingerprints its inputs; this copy is never published.
    source_fingerprint: null,
    data_through: dataThrough === null ? null : signalDate(dataThrough),
    method: publishedMethod,
    market,
    composite,
    history: { dates: grid.map(signalDate) },
    signals,
    unavailable,
  };
}

// Raw-value change over a look-back window, or NaN when the published history
// does not reach back that far.
function rawSignalDelta(signal, days) {
  const points = (signal?.points || []).filter((point) => Number.isFinite(toFiniteNumber(point.value)));
  if (!points.length) return NaN;
  const latest = last(points);
  const target = signalDay(latest.date) - days;
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const day = signalDay(points[index].date);
    if (day > target) continue;
    return target - day > 14 ? NaN : Number(latest.value) - Number(points[index].value);
  }
  return NaN;
}

function recentSignalValues(signal, days) {
  if (!signal?.points?.length) return [];
  const latest = new Date(last(signal.points).date);
  const cutoff = new Date(latest);
  cutoff.setUTCDate(cutoff.getUTCDate() - days);
  return signal.points
    .filter((point) => new Date(point.date) >= cutoff)
    .map((point) => toFiniteNumber(point.value))
    .filter(Number.isFinite);
}

function renderSignalHeatmap(target, signals, columns = 56, options = {}) {
  if (!target) return;
  target.classList.remove("loading-block");
  if (!signals.length) {
    target.innerHTML = `<p class="empty-state">No signal history matches these filters.</p>`;
    return;
  }
  const cutoff = options.startDate ? new Date(options.startDate).getTime() : -Infinity;
  // A cell shows the latest sample at or before its date. Unavailable samples
  // are kept in the series so they end the preceding score, and no sample is
  // carried further than the method's carry-forward limit.
  const maxAge = (appState.signalState?.method?.history?.carry_forward_days ?? 14) * 86400000;
  const visibleSignals = signals.map((signal) => {
    const samples = (signal.samples || signal.points || [])
      .map((point) => ({ ...point, timestamp: new Date(point.date).getTime() }))
      .filter((point) => Number.isFinite(point.timestamp))
      .sort((left, right) => left.timestamp - right.timestamp);
    return { ...signal, samples, scored: samples.filter((point) => Number.isFinite(point.score)) };
  });
  const histories = visibleSignals.filter((signal) => signal.scored.length);
  const start = Math.max(cutoff, Math.min(...histories.map((signal) => signal.scored[0].timestamp)));
  const end = Math.max(...histories.map((signal) => last(signal.scored).timestamp));
  if (!histories.length || start > end) {
    target.innerHTML = `<p class="empty-state">No signal history matches these filters.</p>`;
    return;
  }
  const dates = Array.from({ length: columns }, (_, index) => start + (end - start) * index / Math.max(1, columns - 1));
  const rows = visibleSignals.map((signal) => {
    let pointIndex = -1;
    const cells = dates.map((timestamp) => {
      while (pointIndex + 1 < signal.samples.length && signal.samples[pointIndex + 1].timestamp <= timestamp) pointIndex += 1;
      const point = signal.samples[pointIndex];
      const covered = Boolean(point)
        && Number.isFinite(point.score)
        && timestamp - point.timestamp <= maxAge
        && timestamp <= last(signal.scored)?.timestamp;
      const dateLabel = formatDate(new Date(timestamp));
      const detail = covered
        ? `${Math.round(point.score)} · as of ${formatDate(new Date(point.timestamp))}`
        : "No data";
      return `<span class="heatmap-cell${covered ? ` ${phaseFor(point.score).className}` : ""}" title="${escapeHtml(signal.label)} · ${escapeHtml(dateLabel)} · ${escapeHtml(detail)}"></span>`;
    }).join("");
    return `<span class="heatmap-label" title="${escapeHtml(signal.label)}">${escapeHtml(signal.label)}</span>${cells}`;
  }).join("");
  const yearRow = dates.map((timestamp, index) => {
    const show = index % 8 === 0;
    return `<span class="heatmap-year">${show ? new Date(timestamp).getUTCFullYear() : ""}</span>`;
  }).join("");
  target.innerHTML = `<div class="heatmap-table" style="--heatmap-columns:${columns}">${rows}<span></span>${yearRow}</div>`;
}

// BlockHorizon's public signal palette; 512 RGB samples, interpolated in RGB.
// Source: https://charts.blockhorizon.io/assets/index-Deq0WvUO.js (Cz / sv).
const SIGNAL_PALETTE = "0106f5020af5030ef5030ef50412f50516f5061af5061af5081ef50a22f50c26f50c26f50e2af5102ff51233f51538f51538f5173cf51840f51a44f51d49f51d49f51f4df52152f52356f62356f6255af6275df62962f62b66f62b66f62d6af62f6ef63172f63172f63376f6367bf6387ff73a84f73a84f73c88f73e8cf74090f74090f74295f74499f8469df848a0f848a0f84ba5f84da9f84fadf850b1f950b1f952b5f954b9f957bef957bef959c2f95bc7fa5dcbfa5dcbfa5fcffa61d3fa63d8fb65dcfb65dcfb68e1fb6ae4fc6ce8fc6eecfc6eecfc70f1fc72f5fd72f5fd73f8fd74fafd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfd75fbfb75fbfb75fbf875fbf575fbf175fbf175fbed75fbea75fbe575fbe275fbe275fbde75fbda75fbd675fbd675fbd275fbce75fbca75fbc775fbc775fbc375fbbf75fbbb75fbb775fbb775fbb375fbb075fbac75fbac75fba975fba675fba175fba175fb9e75fb9b75fb9775fb9375fb9375fb9075fb8c75fb8975fb8675fb8675fb8375fb7f75fb7c75fb7c75fb7875fb7575fb7275fb7275fb7075fb6d75fb6a75fb6875fb6875fb6575fb6275fb6075fb5e75fb5e75fb5c75fb5a75fb5875fb5875fb5675fb5475fb5375fb5375fb5175fb5075fb4f75fb4e75fb4e75fb4e75fb4d75fb4d75fb4c75fb4c75fb4c75fb4c75fb4c75fb4c76fb4c76fb4c76fb4c76fb4c76fb4c76fb4c77fb4c77fb4c77fb4c77fb4c77fb4c78fb4c78fb4c78fb4c78fb4c79fb4c79fb4c79fb4c7afb4c7afb4c7bfb4c7bfb4c7bfb4c7cfb4c7cfb4c7dfb4c7dfb4c7efb4c7efb4c7ffb4c7ffb4c80fb4c80fb4c81fb4d82fb4d82fb4d82fc4d83fc4d84fc4d85fc4d85fc4d86fc4d86fc4d88fc4d88fc4d89fc4d89fc4d8afc4d8afc4d8bfc4d8cfc4d8dfc4d8efc4d8efc4d90fc4d91fc4d92fc4d93fc4d93fc4d94fc4d95fc4d97fc4d97fc4d98fc4e99fc4e9afc4e9afc4e9bfc4e9dfc4e9efc4e9ffc4e9ffc4ea1fc4ea2fc4ea3fc4ea4fc4ea4fc4ea6fc4ea8fc4ea8fc4ea8fc4eaafc4eabfc4facfc4faefc4faefc4fb0fc4fb1fd4fb2fd4fb2fd4fb4fd4fb6fd4fb7fd4fb7fd4fb9fd4fbafd4fbbfd4fbdfd50bdfd50befd50c0fd50c2fd50c3fd50c3fd50c5fd50c6fd50c8fd50c8fd50c9fd50cbfd50ccfd50ccfd50cefd51d0fd51d2fd51d3fd51d3fd51d5fe51d7fe51d9fe51dafe51dafe51dcfe52ddfe52dffe52dffe52e0fe52e2fe52e3fe52e3fe52e5fe52e7fe52e9fe53ebfe53ebfe53ecfe53effe53f0fe53f2ff53f2ff53f4ff53f5ff54f7ff54f7ff54f9ff54faff54fcff54fdff54fdff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54ffff54fffe54fffe54fffe54fffc53fefa53fef852fef852fdf652fdf351fdf250fdf250fcef50fcee4ffcec4ffbea4efbea4efbe84dfbe64dfae44cfae24cfae24cfadf4bf9dd4af9db4af9db4af9da49f8d748f8d548f8d347f8d347f7d147f7d046f7ce46f7ce46f7cb45f6c944f6c744f6c543f6c543f5c242f5c142f5bf41f5bf41f5bd41f4bb40f4b940f4b73ff4b73ff4b53ff3b23ef3b13df3af3df3af3df3ad3cf2aa3cf2a83bf2a83bf2a63bf2a43af1a23af1a23af1a139f19f39f19d38f19b38f19b38f09937f09737f09536f09336f09336f09135ef8f35ef8d34ef8d34ef8b34ef8a33ef8833ef8833ef8632ee8332ee8131ee8031ee8031ee7e31ee7b30ee7930ed782fed782fed762fed742eed722eed722eed712eed6f2ded6c2ded6c2ded6b2cec692cec672cec662bec662bec642bec622bec612aec612aec5f2aec5e2aec5b29ec5a29ec5a29eb5829eb5628eb5428eb5328eb5328eb5128eb5027eb4e27eb4e27eb4d27eb4c27eb4a26eb4a26eb4926eb4826eb4626eb4426eb4426ea4325ea4225ea4125ea4025ea4025ea3f25ea3e25ea3c24ea3c24ea3b24ea3b24ea3a24ea3a24ea3924ea3824ea3724ea3724ea3724ea3624ea3624ea3524ea3524ea3524ea3423ea3423ea5149";

function signalColor(ratio) {
  const at = clamp(ratio, 0, 1) * (SIGNAL_PALETTE.length / 6 - 1);
  const low = Math.floor(at);
  const high = Math.ceil(at);
  const rgb = [0, 2, 4].map((offset) => {
    const start = parseInt(SIGNAL_PALETTE.slice(low * 6 + offset, low * 6 + offset + 2), 16);
    const end = parseInt(SIGNAL_PALETTE.slice(high * 6 + offset, high * 6 + offset + 2), 16);
    const value = start + (end - start) * (at - low);
    const floor = Math.floor(value);
    return value - floor === 0.5 ? floor + floor % 2 : Math.round(value);
  });
  return `#${rgb.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function chartDisplaySeries(payload, options = {}, sourceSeries = payload.series) {
  const config = options.signalView && payload.signal_view;
  if (!config) return sourceSeries;
  const price = sourceSeries.find((series) => series.source_key === "price");
  const metric = sourceSeries.find((series) => series.source_key === config.series_key);
  if (!price || !metric || !Array.isArray(price.x) || !Array.isArray(price.y)
      || !Array.isArray(metric.x) || !Array.isArray(metric.y)) return sourceSeries;
  const metricByDate = new Map(metric.x.map((date, index) => [comparableX(date), toFiniteNumber(metric.y[index])]));
  const metricValues = price.x.map((date) => {
    const value = metricByDate.get(comparableX(date));
    return Number.isFinite(value) ? value : null;
  });
  const values = price.x.map((date, index) => {
    const metricValue = metricByDate.get(comparableX(date));
    if (!Number.isFinite(metricValue)) return null;
    const priceValue = toFiniteNumber(price.y[index]);
    return config.mode === "error"
      ? (metricValue > 0 && Number.isFinite(priceValue) ? priceValue / metricValue : null)
      : metricValue;
  });
  const colors = values.map((value) => value === null ? "rgba(0,0,0,0)"
    : signalColor((value - config.min) / (config.max - config.min)));
  // Display mode changes only the picture. Original arrays continue to drive
  // tables, performance modules, alerts, and sidebar metric readings.
  const signalPrice = {
    ...price,
    axis: "y",
    mode: "markers",
    marker: { color: colors, size: 8, line: { width: 0 } },
    signal_metric_name: metric.name,
    signal_metric_values: metricValues,
  };
  return [signalPrice, ...sourceSeries.filter((series) => series !== price && series !== metric && !series.source_key)];
}

function chartDisplayLayout(payload, options = {}) {
  const layout = deepMerge({}, payload.layout || {});
  if (options.signalView && payload.signal_view) {
    delete layout.yaxis2;
    layout.yaxis = { ...layout.yaxis, title: "BTC price (USD)", tickprefix: "$" };
  }
  return layout;
}

function chartValueZoneShapes(payload, options = {}) {
  if (options.signalView || !Array.isArray(payload.value_zones)) return [];
  return payload.value_zones.flatMap((zone) => {
    const series = payload.series.find((item) => item.source_key === zone.seriesKey);
    const values = (series?.y || []).map(toFiniteNumber).filter(Number.isFinite);
    if (!values.length) return [];
    const low = Math.min(...values);
    const high = Math.max(...values);
    const padding = Math.max((high - low) * .06, .01);
    const common = { type: "rect", xref: "paper", x0: 0, x1: 1, yref: series.axis || series.yaxis || "y", line: { width: 0 }, layer: "below" };
    const bands = [];
    if (Number.isFinite(zone.greenBelow)) bands.push({ ...common, y0: Math.min(low - padding, zone.greenBelow), y1: zone.greenBelow, fillcolor: "rgba(74,222,128,0.08)" });
    if (Number.isFinite(zone.redAbove)) bands.push({ ...common, y0: zone.redAbove, y1: Math.max(high + padding, zone.redAbove), fillcolor: "rgba(248,113,113,0.08)" });
    return bands;
  });
}

async function renderPlot(target, payload, options = {}) {
  if (!window.Plotly || !target) return;
  const renderId = (target._fintechRenderId || 0) + 1;
  target._fintechRenderId = renderId;
  await cleanupChartInteractions(target);
  if (target._fintechRenderId !== renderId) return;
  const dark = document.documentElement.dataset.theme === "dark";
  const colorMap = {
    "#f5c84b": "#c85f3c",
    "#55d6ff": "#2863a7",
    "#3ce38a": "#16844d",
    "#ff5f63": "#c91f50",
    "#ff9f43": "#d98945",
    "#ff5ccd": "#9d4c83",
    "#eef3f8": dark ? "#eef3f8" : "#393732",
    "#000000": dark ? "#eef3f8" : "#393732",
    "rgba(238,243,248,0.62)": dark ? "rgba(238,243,248,0.62)" : "rgba(57,55,50,0.46)",
  };
  const lightSequentialScale = [
    [0, "#f7f5f0"],
    [0.22, "#f0ded5"],
    [0.48, "#dfa993"],
    [0.72, "#c96f50"],
    [0.9, "#b4472f"],
    [1, "#8f291f"],
  ];
  const lightDivergingScale = [
    [0, "#b63f38"],
    [0.38, "#e8aaa0"],
    [0.5, "#f7f5f0"],
    [0.62, "#a9d4bd"],
    [1, "#167247"],
  ];
  const mapColor = (color) => typeof color === "string" ? (colorMap[color.toLowerCase()] || color) : color;
  const sourceSeries = chartDisplaySeries(payload, options, options.series || payload.series);
  const displaySeries = sourceSeries
    .slice(0, options.compact ? 4 : sourceSeries.length)
    .flatMap(expandGradientLine);
  const traces = displaySeries.map((series) => {
    const { axis, ...trace } = series;
    const next = { ...trace, yaxis: axis || trace.yaxis || "y" };
    if (options.maxPoints && !trace.signal_metric_values && !trace.meta?.fintechHelper
        && Array.isArray(trace.x) && !trace.x.includes(null)) {
      const step = Math.max(1, Math.ceil(trace.x.length / options.maxPoints));
      const sourceLength = trace.x.length;
      ["x", "y", "open", "high", "low", "close", "text"].forEach((key) => {
        if (Array.isArray(next[key])) next[key] = next[key].filter((_, index) => index % step === 0 || index === next[key].length - 1);
      });
      if (Array.isArray(next.marker?.color) && next.marker.color.length === sourceLength) {
        next.marker = {
          ...next.marker,
          color: next.marker.color.filter((_, index) => index % step === 0 || index === sourceLength - 1),
        };
      }
    }
    if (next.line?.color) next.line = { ...next.line, color: mapColor(next.line.color) };
    if (next.marker?.color) {
      const markerColor = Array.isArray(next.marker.color)
        ? next.marker.color.map(mapColor)
        : mapColor(next.marker.color);
      next.marker = { ...next.marker, color: markerColor };
    }
    if (next.fillcolor) next.fillcolor = mapColor(next.fillcolor);
    if (next.increasing?.line?.color) {
      next.increasing = { ...next.increasing, line: { ...next.increasing.line, color: mapColor(next.increasing.line.color) } };
    }
    if (next.decreasing?.line?.color) {
      next.decreasing = { ...next.decreasing, line: { ...next.decreasing.line, color: mapColor(next.decreasing.line.color) } };
    }
    if (next.type === "heatmap" && !dark) {
      next.colorscale = next.zmid !== undefined ? lightDivergingScale : lightSequentialScale;
      if (next.zmid !== undefined && Array.isArray(next.z)) {
        const magnitudes = next.z.flat().map(toFiniteNumber).filter(Number.isFinite).map(Math.abs);
        const cap = quantile(magnitudes, 0.95);
        if (Number.isFinite(cap) && cap > 0) {
          next.zmin = -cap;
          next.zmax = cap;
          next.zauto = false;
        }
      }
    }
    if (next.hoverinfo === "skip") delete next.hovertemplate;
    else {
      next.hovertemplate = next.hovertemplate || "%{x}<br>%{y}<extra>%{fullData.name}</extra>";
      applyReadableHover(next);
    }
    return next;
  }).flatMap(withFinancialHover);
  const baseLayout = {
    autosize: true,
    dragmode: "zoom",
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, sans-serif", color: dark ? "#aaa69d" : "#6f6d67", size: 11 },
    margin: options.compact ? { l: 56, r: 28, t: 18, b: 42 } : { l: 68, r: 44, t: 28, b: 70 },
    hovermode: "x unified",
    hoverdistance: -1,
    spikedistance: -1,
    hoverlabel: {
      align: "left",
      bgcolor: dark ? "#1f211f" : "#ffffff",
      bordercolor: dark ? "#565852" : "#d5d3cc",
      font: {
        family: "IBM Plex Mono, monospace",
        color: dark ? "#f2f1ec" : "#34332f",
        size: options.compact ? 10 : 11,
      },
      namelength: -1,
    },
    showlegend: true,
    legend: { orientation: "h", x: 0, y: 1.08, font: { size: 10 } },
    xaxis: { gridcolor: dark ? "#34332e" : "#e8e6df", zerolinecolor: dark ? "#4b4941" : "#c9c6be", rangeslider: { visible: false } },
    yaxis: { gridcolor: dark ? "#34332e" : "#e8e6df", zerolinecolor: dark ? "#4b4941" : "#c9c6be", automargin: true },
  };
  let layout = deepMerge(baseLayout, chartDisplayLayout(payload, options));
  if (options.layout) Object.assign(layout, deepMerge(layout, options.layout));
  const valueZones = chartValueZoneShapes(payload, options);
  if (valueZones.length) layout.shapes = [...(layout.shapes || []), ...valueZones];
  const remapLayoutColors = (value) => {
    if (Array.isArray(value)) return value.map(remapLayoutColors);
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.entries(value).map(([key, nested]) => [key, remapLayoutColors(nested)]));
    }
    return mapColor(value);
  };
  layout = remapLayoutColors(layout);
  if (payload.x_value_type === "category") layout.xaxis = { ...layout.xaxis, type: "category" };
  if (payload.x_value_type === "number") layout.xaxis = { ...layout.xaxis, type: "linear" };
  if (payload.x_value_type === "date") layout.xaxis = { ...layout.xaxis, hoverformat: "%b %-d, %Y" };
  const categoricalY = traces.some((trace) => (
    (trace.type === "heatmap" || trace.orientation === "h")
    && Array.isArray(trace.y)
    && trace.y.some((value) => typeof value === "string")
  ));
  if (categoricalY) layout.yaxis = { ...layout.yaxis, type: "category" };
  const spikeColor = dark ? "rgba(238,243,248,0.58)" : "rgba(47,46,42,0.58)";
  Object.keys(layout).filter((key) => /^xaxis\d*$/.test(key) || /^yaxis\d*$/.test(key)).forEach((key) => {
    const axis = layout[key];
    if (!axis || axis.type === "category") return;
    const primaryAxis = key === "xaxis" || key === "yaxis";
    Object.assign(axis, {
      showspikes: primaryAxis,
      spikecolor: spikeColor,
      spikedash: "dot",
      spikethickness: 1,
      spikesnap: "cursor",
      spikemode: "across",
    });
  });
  if (options.compact) {
    delete layout.xaxis?.rangeselector;
    if (layout.legend) layout.legend.y = 1.12;
  }
  if (options.grid === false) {
    Object.keys(layout).filter((key) => key.startsWith("xaxis") || key.startsWith("yaxis")).forEach((key) => {
      layout[key].gridcolor = "rgba(0,0,0,0)";
    });
  }
  const animatedControls = !categoricalY && ["date", "number"].includes(payload.x_value_type) && Boolean(Plotly.Icons);
  return Plotly.newPlot(target, traces, layout, {
    responsive: true,
    displaylogo: false,
    displayModeBar: !options.compact,
    scrollZoom: !options.compact && categoricalY,
    doubleClick: "reset+autosize",
    showAxisDragHandles: false,
    showAxisRangeEntryBoxes: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d", ...(animatedControls ? ["zoomIn2d", "zoomOut2d", "resetScale2d", "autoScale2d"] : [])],
    modeBarButtonsToAdd: animatedControls ? [
      {name: "Zoom in", icon: Plotly.Icons.zoom_plus, click: plot => plot._fintechNavigation?.zoomBy(0.5)},
      {name: "Zoom out", icon: Plotly.Icons.zoom_minus, click: plot => plot._fintechNavigation?.zoomBy(2)},
      {name: "Fit visible data", icon: Plotly.Icons.autoscale, click: plot => plot._fintechNavigation?.fit()},
      {name: "Reset axes", icon: Plotly.Icons.home, click: plot => plot._fintechNavigation?.reset()},
    ] : [],
  }).then(async (plot) => {
    if (target._fintechRenderId !== renderId) return plot;
    const priceTicks = priceAxisTickUpdates(target);
    if (Object.keys(priceTicks).length) await Plotly.relayout(target, priceTicks);
    if (target._fintechRenderId !== renderId) return plot;
    if (!options.compact) {
      installPriceScaleControls(target);
      bindChartHoverDetails(target, payload);
    }
    installAxisBadges(target);
    installSeriesValueBadges(target);
    installChartNavigation(target, options);
    return plot;
  });
}

function cleanupChartInteractions(target) {
  const cleanup = target?._fintechChartCleanup;
  if (!cleanup) return target?._fintechCleanupPromise;
  target._fintechChartCleanup = null;
  const pending = Promise.resolve(cleanup()).finally(() => {
    if (target._fintechCleanupPromise === pending) target._fintechCleanupPromise = null;
  });
  target._fintechCleanupPromise = pending;
  return pending;
}

function withFinancialHover(trace, index) {
  if (!["candlestick", "ohlc"].includes(trace.type) || trace.hoverinfo === "skip") return [trace];
  // Plotly 2.x gives every candle the same infinite hit distance when
  // hoverdistance=-1, selecting the last one. A scatter trace uses nearest-x
  // hit testing, including the gaps between downsampled candles.
  const legendgroup = trace.legendgroup || `financial-${index}`;
  const candle = { ...trace, legendgroup, hoverinfo: "skip" };
  delete candle.hovertemplate;
  const hover = {
    type: "scatter",
    mode: "markers",
    name: trace.name,
    legendgroup,
    showlegend: false,
    visible: trace.visible,
    xaxis: trace.xaxis,
    yaxis: trace.yaxis,
    x: trace.x,
    y: trace.close,
    marker: { size: 0, opacity: 0, color: trace.increasing?.line?.color || "#16844d" },
    customdata: trace.x.map((_, point) => (
      ["open", "high", "low", "close"].map(key => formatHoverMetricValue("Price USD", trace[key]?.[point]))
    )),
    hovertemplate: "Open: %{customdata[0]}<br>High: %{customdata[1]}<br>Low: %{customdata[2]}<br>Close: %{customdata[3]}<extra>%{fullData.name}</extra>",
  };
  return [candle, hover];
}

function installChartNavigation(target, options = {}) {
  const layout = target?._fullLayout;
  if (!layout?.xaxis || !target.addEventListener || !["date", "linear", "log"].includes(layout.xaxis.type)) return;
  // Category comparisons keep Plotly's native interaction. Time-series charts
  // select dates horizontally and fit each numeric pane to the visible data.
  if (layout.yaxis?.type === "category" || layout.xaxis.fixedrange) return;
  const initial = {};
  Object.keys(layout).filter(key => /^[xy]axis\d*$/.test(key)).forEach(key => {
    if (Array.isArray(layout[key].range)) initial[key] = layout[key].range.slice();
  });
  let closed = false;
  let ownUpdate = false;
  let animationId = 0;
  let settleAnimation = null;
  let gesture = null;
  const selection = document.createElement("div");
  selection.className = "chart-zoom-selection";
  selection.hidden = true;
  selection.setAttribute("aria-hidden", "true");
  const resetButton = document.createElement("button");
  resetButton.type = "button";
  resetButton.className = "chart-reset-zoom";
  resetButton.textContent = "Reset zoom";
  resetButton.hidden = true;
  target.append(selection, resetButton);
  target.tabIndex = 0;
  const axisNumber = value => target._fullLayout.xaxis.type === "date" ? new Date(value).getTime() : Number(value);
  const axisValue = value => target._fullLayout.xaxis.type === "date" ? new Date(value).toISOString() : value;
  const rangeChanged = range => {
    const tolerance = target._fullLayout.xaxis.type === "date" ? 1 : Math.abs(Number(initial.xaxis[1]) - Number(initial.xaxis[0])) * 1e-9;
    return range?.some((value, index) => Math.abs(axisNumber(value) - axisNumber(initial.xaxis[index])) > tolerance);
  };
  const notifyViewport = (source) => {
    if (closed || typeof options.onViewportChange !== "function") return;
    const range = target._fullLayout?.xaxis?.range?.slice();
    try {
      options.onViewportChange({source, range, full: !rangeChanged(range)});
    } catch (error) {
      console.warn("Chart viewport listener failed", error);
    }
  };
  const animate = (ranges, source = "user") => {
    if (closed) return Promise.resolve();
    const id = ++animationId;
    if (settleAnimation) settleAnimation();
    const superseded = new Promise(resolve => {settleAnimation = resolve;});
    const duration = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? 0 : 350;
    const nextLayout = Object.fromEntries(Object.entries(ranges).map(([key, range]) => [key, {
      range,
      autorange: false,
      ...(key.startsWith("yaxis") ? priceAxisTickOptions(target._fullLayout[key], range) : {}),
    }]));
    ownUpdate = true;
    resetButton.hidden = !rangeChanged(ranges.xaxis || target._fullLayout.xaxis.range);
    const update = duration
      ? Plotly.animate(target, {layout: nextLayout}, {transition: {duration, easing: "cubic-out"}, frame: {duration, redraw: false}, mode: "immediate"})
      : Plotly.relayout(target, Object.fromEntries(Object.entries(nextLayout).flatMap(([key, attributes]) =>
        Object.entries(attributes).map(([attribute, value]) => [`${key}.${attribute}`, value]))));
    return Promise.race([Promise.resolve(update), superseded]).catch(error => {
      if (!closed && id === animationId && error) throw error;
    }).finally(() => {
      if (id === animationId) {
        ownUpdate = false;
        settleAnimation = null;
        notifyViewport(source);
      }
    });
  };
  const zoomTo = (range, source = "user") => {
    const limits = initial.xaxis.map(axisNumber);
    let [start, end] = range.map(axisNumber).sort((left, right) => left - right);
    const minimum = target._fullLayout.xaxis.type === "date" ? 86400000 : Math.abs(limits[1] - limits[0]) / 100000;
    if (end - start < minimum) {
      const center = (start + end) / 2;
      start = center - minimum / 2;
      end = center + minimum / 2;
    }
    const span = Math.min(end - start, Math.abs(limits[1] - limits[0]));
    start = clamp(start, Math.min(...limits), Math.max(...limits) - span);
    const selected = [axisValue(start), axisValue(start + span)];
    if (limits[0] > limits[1]) selected.reverse();
    return animate({xaxis: selected, ...visibleChartYRanges(target, selected)}, source);
  };
  const reset = (source = "user") => animate(initial, source);
  const zoomBy = (factor, fraction = 0.5) => {
    const range = target._fullLayout.xaxis.range.map(axisNumber);
    const anchor = range[0] + (range[1] - range[0]) * fraction;
    return zoomTo(range.map(value => axisValue(anchor + (value - anchor) * factor)));
  };
  const fit = () => animate(visibleChartYRanges(target, target._fullLayout.xaxis.range), "fit");
  target._fintechNavigation = {zoomTo, reset, zoomBy, fit};
  const clearSelection = () => {
    if (gesture && target.hasPointerCapture?.(gesture.id)) target.releasePointerCapture(gesture.id);
    gesture = null;
    selection.hidden = true;
    target.classList.remove("chart-selecting");
  };
  const plotPoint = event => {
    const bounds = target.getBoundingClientRect();
    const axis = target._fullLayout.xaxis;
    const size = target._fullLayout._size;
    return {x: event.clientX - bounds.left - axis._offset, y: event.clientY - bounds.top - size.t, axis, size};
  };
  const onDown = event => {
    if (event.button !== 0 || event.shiftKey || event.ctrlKey || event.metaKey || event.pointerType === "touch"
        || target._fullLayout.dragmode !== "zoom" || !event.target.closest?.(".nsewdrag")) return;
    const point = plotPoint(event);
    event.preventDefault();
    event.stopPropagation();
    target.focus({preventScroll: true});
    gesture = {id: event.pointerId, start: clamp(point.x, 0, point.axis._length), end: point.x};
    target.setPointerCapture(event.pointerId);
  };
  const onMove = event => {
    if (!gesture || event.pointerId !== gesture.id) return;
    const {axis, size, x} = plotPoint(event);
    gesture.end = clamp(x, 0, axis._length);
    const width = Math.abs(gesture.end - gesture.start);
    if (width < 3) return;
    target.classList.add("chart-selecting");
    selection.hidden = false;
    selection.style.left = `${axis._offset + Math.min(gesture.start, gesture.end)}px`;
    selection.style.top = `${size.t}px`;
    selection.style.width = `${width}px`;
    selection.style.height = `${size.h}px`;
  };
  const onUp = event => {
    if (!gesture || event.pointerId !== gesture.id) return;
    const {axis} = plotPoint(event);
    const pixels = [gesture.start, gesture.end].sort((left, right) => left - right);
    clearSelection();
    if (pixels[1] - pixels[0] >= 8) {
      const range = pixels.map(pixel => axis.p2r(pixel));
      zoomTo(range).catch(() => {});
    }
  };
  const onDoubleClick = event => {
    const {x, y, axis, size} = plotPoint(event);
    if (x < 0 || x > axis._length || y < 0 || y > size.h || event.target.closest?.(".modebar, .legend, button")) return;
    event.preventDefault();
    event.stopPropagation();
    reset().catch(() => {});
  };
  const onKey = event => {
    if (event.target !== target) return;
    if (event.key === "Escape") {
      if (gesture) clearSelection();
      else reset().catch(() => {});
    } else if (["+", "="].includes(event.key)) zoomBy(0.65).catch(() => {});
    else if (event.key === "-") zoomBy(1.5).catch(() => {});
    else if (event.key === "0") reset().catch(() => {});
    else return;
    event.preventDefault();
  };
  const onRelayout = update => {
    if (closed || ownUpdate) return;
    const xChanged = Object.keys(update || {}).some(key => key.startsWith("xaxis.range") || key === "xaxis.autorange");
    if (!xChanged) {
      if (Object.keys(update || {}).some(key => /^yaxis\d*\.range/.test(key))) {
        const ticks = priceAxisTickUpdates(target);
        if (Object.keys(ticks).length) {
          ownUpdate = true;
          Plotly.relayout(target, ticks).finally(() => {ownUpdate = false;});
        }
      }
      return;
    }
    const range = target._fullLayout.xaxis.range.slice();
    const fitted = visibleChartYRanges(target, range);
    resetButton.hidden = !rangeChanged(range);
    ownUpdate = true;
    Plotly.relayout(target, {
      ...Object.fromEntries(Object.entries(fitted).map(([key, values]) => [`${key}.range`, values])),
      ...priceAxisTickUpdates(target, fitted),
    })
      .finally(() => {
        ownUpdate = false;
        notifyViewport("user");
      });
  };
  const onReset = () => reset().catch(() => {});
  target.addEventListener("pointerdown", onDown, true);
  target.addEventListener("pointermove", onMove, true);
  target.addEventListener("pointerup", onUp, true);
  target.addEventListener("pointercancel", clearSelection);
  target.addEventListener("dblclick", onDoubleClick, true);
  target.addEventListener("keydown", onKey);
  resetButton.addEventListener("click", onReset);
  target.on?.("plotly_relayout", onRelayout);
  const priorCleanup = target._fintechChartCleanup;
  target._fintechChartCleanup = () => {
    closed = true;
    clearSelection();
    const frozenAxes = Object.fromEntries(Object.keys(initial).map(key => [key, {range: target._fullLayout[key].range.slice()}]));
    const stopping = ownUpdate
      ? Plotly.animate(target, {layout: frozenAxes}, {mode: "immediate", transition: {duration: 0}, frame: {duration: 0, redraw: false}}).catch(() => {})
      : Promise.resolve();
    if (settleAnimation) settleAnimation();
    target.removeEventListener("pointerdown", onDown, true);
    target.removeEventListener("pointermove", onMove, true);
    target.removeEventListener("pointerup", onUp, true);
    target.removeEventListener("pointercancel", clearSelection);
    target.removeEventListener("dblclick", onDoubleClick, true);
    target.removeEventListener("keydown", onKey);
    target.removeListener?.("plotly_relayout", onRelayout);
    selection.remove();
    resetButton.remove();
    target._fintechNavigation = null;
    const prior = typeof priorCleanup === "function" ? priorCleanup() : null;
    return Promise.all([stopping, prior]);
  };
}

function priceAxisTickUpdates(target, ranges = {}) {
  const updates = {};
  Object.entries(target?._fullLayout || {}).forEach(([key, axis]) => {
    if (!/^yaxis\d*$/.test(key)) return;
    const options = priceAxisTickOptions(axis, ranges[key] || axis.range);
    Object.entries(options).forEach(([property, value]) => {updates[`${key}.${property}`] = value;});
  });
  return updates;
}

function installPriceScaleControls(target) {
  const fullLayout = target?._fullLayout;
  if (!fullLayout?._size) return;
  target.classList.add("premium-chart");
  const cleanups = [];
  const resizeObserver = new ResizeObserver(() => positionScaleRails(target));
  resizeObserver.observe(target);
  cleanups.push(() => resizeObserver.disconnect());

  Object.keys(fullLayout).filter((name) => /^yaxis\d*$/.test(name)).forEach((axisName) => {
    const axis = target._fullLayout?.[axisName];
    if (!axis || axis.type === "category" || axis.fixedrange) return;
    const side = axis.side === "right" ? "right" : "left";
    const rail = document.createElement("div");
    rail.className = `chart-scale-rail chart-scale-rail-${side}`;
    rail.dataset.axis = axisName;
    rail.setAttribute("aria-hidden", "true");
    rail.title = "Drag to scale · double-click to reset";
    target.appendChild(rail);

    const initialRange = Array.isArray(axis.range) ? axis.range.slice() : null;
    let gesture = null;
    let pendingRange = null;
    let frame = 0;
    const applyPendingRange = () => {
      frame = 0;
      if (!pendingRange) return;
      const range = pendingRange;
      pendingRange = null;
      Plotly.relayout(target, { [`${axisName}.range`]: range }).catch(() => {});
    };
    const queueRange = (range) => {
      pendingRange = range;
      if (!frame) frame = requestAnimationFrame(applyPendingRange);
    };
    const scaledRange = (range, factor) => {
      if (!Array.isArray(range) || range.length < 2) return null;
      const start = Number(range[0]);
      const end = Number(range[1]);
      if (!Number.isFinite(start) || !Number.isFinite(end) || start === end) return null;
      const center = (start + end) / 2;
      const halfSpan = ((end - start) / 2) * clamp(factor, 0.08, 12);
      return [center - halfSpan, center + halfSpan];
    };
    const onPointerDown = (event) => {
      if (event.button !== 0) return;
      const current = target._fullLayout?.[axisName]?.range;
      if (!Array.isArray(current)) return;
      event.preventDefault();
      event.stopPropagation();
      gesture = { pointerId: event.pointerId, startY: event.clientY, range: current.slice() };
      rail.classList.add("active");
      rail.setPointerCapture(event.pointerId);
    };
    const onPointerMove = (event) => {
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      event.preventDefault();
      const factor = Math.exp((event.clientY - gesture.startY) / 180);
      const range = scaledRange(gesture.range, factor);
      if (range) queueRange(range);
    };
    const endGesture = (event) => {
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      gesture = null;
      rail.classList.remove("active");
      if (rail.hasPointerCapture(event.pointerId)) rail.releasePointerCapture(event.pointerId);
    };
    const onWheel = (event) => {
      const current = target._fullLayout?.[axisName]?.range;
      const range = scaledRange(current, Math.exp(event.deltaY / 500));
      if (!range) return;
      event.preventDefault();
      event.stopPropagation();
      queueRange(range);
    };
    const onDoubleClick = (event) => {
      if (!initialRange) return;
      event.preventDefault();
      event.stopPropagation();
      queueRange(initialRange.slice());
    };
    rail.addEventListener("pointerdown", onPointerDown);
    rail.addEventListener("pointermove", onPointerMove);
    rail.addEventListener("pointerup", endGesture);
    rail.addEventListener("pointercancel", endGesture);
    rail.addEventListener("wheel", onWheel, { passive: false });
    rail.addEventListener("dblclick", onDoubleClick);
    cleanups.push(() => {
      if (frame) cancelAnimationFrame(frame);
      rail.remove();
    });
  });

  positionScaleRails(target);
  const afterPlot = () => positionScaleRails(target);
  if (typeof target.on === "function") {
    target.on("plotly_afterplot", afterPlot);
    cleanups.push(() => target.removeListener?.("plotly_afterplot", afterPlot));
  }
  const priorCleanup = target._fintechChartCleanup;
  target._fintechChartCleanup = () => {
    if (typeof priorCleanup === "function") priorCleanup();
    cleanups.forEach((cleanup) => cleanup());
    target.classList.remove("premium-chart");
  };
}

function positionScaleRails(target) {
  const size = target?._fullLayout?._size;
  if (!size) return;
  target.querySelectorAll(".chart-scale-rail").forEach((rail) => {
    const axis = target._fullLayout[rail.dataset.axis];
    if (!axis) return;
    const side = axis.side === "right" ? "right" : "left";
    rail.style.top = `${axis._offset}px`;
    rail.style.height = `${axis._length}px`;
    rail.style.width = `${Math.max(28, side === "left" ? size.l : size.r)}px`;
    rail.style[side] = "0";
  });
}

function yAxisAtPixel(layout, pixel) {
  for (const [name, axis] of Object.entries(layout || {})) {
    if (!/^yaxis\d*$/.test(name) || axis.overlaying || axis.type === "category") continue;
    if (!Number.isFinite(axis._offset) || !Number.isFinite(axis._length) || axis._length <= 0) continue;
    if (pixel >= axis._offset && pixel <= axis._offset + axis._length) return { name, axis };
  }
  return null;
}

function installAxisBadges(target) {
  const fullLayout = target?._fullLayout;
  if (!fullLayout?._size || !fullLayout.xaxis || !fullLayout.yaxis
      || fullLayout.xaxis.type === "category") return;
  const xBadge = document.createElement("span");
  const yBadge = document.createElement("span");
  xBadge.className = "chart-axis-badge chart-axis-badge-x";
  yBadge.className = "chart-axis-badge chart-axis-badge-y";
  xBadge.setAttribute("aria-hidden", "true");
  yBadge.setAttribute("aria-hidden", "true");
  target.append(xBadge, yBadge);

  const hideBadges = () => {
    xBadge.classList.remove("visible");
    yBadge.classList.remove("visible");
  };
  const onPointerMove = (event) => {
    const layout = target._fullLayout;
    const size = layout?._size;
    if (!size) return;
    const bounds = target.getBoundingClientRect();
    const xaxis = layout.xaxis;
    const plotX = event.clientX - bounds.left - xaxis._offset;
    const chartY = event.clientY - bounds.top;
    const selected = yAxisAtPixel(layout, chartY);
    if (plotX < 0 || plotX > xaxis._length || !selected) {
      hideBadges();
      return;
    }
    const xValue = xaxis.p2d?.(plotX);
    const yValue = selected.axis.p2d?.(chartY - selected.axis._offset);
    xBadge.textContent = xaxis.type === "date"
      ? formatCrosshairDate(xValue)
      : formatCrosshairValue(xValue, xaxis);
    yBadge.textContent = formatCrosshairValue(yValue, selected.axis);
    yBadge.dataset.axis = selected.name;
    xBadge.style.left = `${xaxis._offset + plotX}px`;
    xBadge.style.top = `${size.t + size.h + 8}px`;
    yBadge.style.left = `${xaxis._offset}px`;
    yBadge.style.top = `${chartY}px`;
    xBadge.classList.add("visible");
    yBadge.classList.add("visible");
  };
  target.addEventListener("pointermove", onPointerMove);
  target.addEventListener("pointerleave", hideBadges);
  const priorCleanup = target._fintechChartCleanup;
  target._fintechChartCleanup = () => {
    target.removeEventListener("pointermove", onPointerMove);
    target.removeEventListener("pointerleave", hideBadges);
    xBadge.remove();
    yBadge.remove();
    if (typeof priorCleanup === "function") priorCleanup();
  };
}

function formatCrosshairDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value ?? "");
  const parts = new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  }).formatToParts(date);
  const part = (type) => parts.find((item) => item.type === type)?.value || "";
  return `${part("day")} ${part("month")} '${part("year")}`;
}

function formatCrosshairValue(value, axis) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${axis?.tickprefix || ""}${formatReadableNumber(number)}${axis?.ticksuffix || ""}`;
}

function bindChartHoverDetails(target, payload) {
  if (typeof target?.on !== "function" || payload.x_value_type !== "date") return;
  let restoreTimer = 0;
  const onHover = (event) => {
    clearTimeout(restoreTimer);
    const xValue = event?.points?.find((point) => point.x !== undefined)?.x;
    if (xValue !== undefined) updateHoveredSeriesDetails(payload, xValue);
  };
  const onUnhover = () => {
    clearTimeout(restoreTimer);
    restoreTimer = window.setTimeout(() => updateHoveredSeriesDetails(payload, null), 80);
  };
  target.on("plotly_hover", onHover);
  target.on("plotly_unhover", onUnhover);
  const priorCleanup = target._fintechChartCleanup;
  target._fintechChartCleanup = () => {
    clearTimeout(restoreTimer);
    if (typeof target.removeListener === "function") {
      target.removeListener("plotly_hover", onHover);
      target.removeListener("plotly_unhover", onUnhover);
    }
    if (typeof priorCleanup === "function") priorCleanup();
  };
}

function applyReadableHover(series) {
  const sourceTemplate = series.hovertemplate || "";
  if (series.type === "heatmap" && Array.isArray(series.z)) {
    series.customdata = series.z.map((row) => (
      Array.isArray(row) ? row.map((value) => formatHoverMetricValue(series.name, value, sourceTemplate)) : row
    ));
    series.hovertemplate = "%{x}<br>%{y}<br>%{customdata}<extra></extra>";
    return;
  }
  if (!["scatter", "scattergl", "bar"].includes(series.type)) return;
  const values = series.orientation === "h" ? series.x : series.y;
  if (!Array.isArray(values)) return;
  series.hovertext = values.map((value, index) => {
    const reading = formatHoverMetricValue(series.name, value, sourceTemplate);
    if (!series.signal_metric_name) return reading;
    const metricValue = series.signal_metric_values?.[index];
    return `${reading}<br>${escapeHtml(series.signal_metric_name)}: ${formatHoverMetricValue(series.signal_metric_name, metricValue)}`;
  });
  series.hovertemplate = "%{hovertext}<extra>%{fullData.name}</extra>";
}

function updateHoveredSeriesDetails(payload, xValue) {
  const dateNode = document.querySelector("#series-date");
  const referenceSeries = payload.series.find((series) => Array.isArray(series.x) && series.x.length);
  const referenceIndex = xValue === null ? -1 : nearestSeriesIndex(referenceSeries, xValue);
  const anchor = payload.x_value_type === "date" ? observedRangeEnd(payload) : null;
  const referenceDate = referenceIndex >= 0 ? referenceSeries.x[referenceIndex] : anchor ?? referenceSeries?.x?.at(-1);
  if (dateNode) dateNode.textContent = referenceDate ? shortDate(referenceDate) : "Latest";
  document.querySelectorAll("#series-list .series-row[data-series-index]").forEach((row) => {
    const series = payload.series[Number(row.dataset.seriesIndex)];
    const valueNode = row.querySelector(".series-value");
    if (!series || !valueNode) return;
    const index = xValue === null ? -1 : nearestSeriesIndex(series, xValue);
    const values = seriesValueArray(series);
    const rawValue = index >= 0 ? values[index] : seriesLatestValue(series, anchor);
    valueNode.textContent = seriesDisplayValue(series, rawValue);
  });
}

function readoutSeries(payload) {
  return (payload?.series || []).filter((series) => (
    series?.type !== "heatmap"
    && series?.hoverinfo !== "skip"
    && !series?.meta?.fintechHelper
    && series?.orientation !== "h"
    && Array.isArray(series?.x)
    && series.x.length
  )).slice(0, 6);
}

function inspectorReferenceSeries(payload) {
  const candidates = readoutSeries(payload);
  return candidates.find((series) => ["candlestick", "ohlc"].includes(series.type) || series.source_key === "price" || /^(btc\s+)?price$/i.test(String(series.name || "").trim()))
    || (payload?.x_value_type === "date" ? detailSeries(payload) : null)
    || candidates[0]
    || null;
}

// Nearest observation, but only when it is close to the inspected coordinate:
// a series that ended years earlier should read "—", not its final value.
function seriesIndexNear(series, xValue) {
  const index = nearestSeriesIndex(series, xValue);
  if (index < 0) return -1;
  const coordinates = series.x.map(comparableX).filter(Number.isFinite);
  const span = coordinates.length > 1 ? Math.abs(coordinates.at(-1) - coordinates[0]) / (coordinates.length - 1) : 0;
  const tolerance = Math.max(span * 2, 1.5 * 86_400_000);
  return Math.abs(comparableX(series.x[index]) - comparableX(xValue)) <= tolerance ? index : -1;
}

function chartReadout(payload, xValue) {
  const label = payload?.x_value_type === "date"
    ? formatDate(new Date(comparableX(xValue)))
    : formatReadableNumber(comparableX(xValue));
  const items = readoutSeries(payload).map((series, index) => {
    const pointIndex = seriesIndexNear(series, xValue);
    const values = seriesValueArray(series);
    const value = pointIndex >= 0 ? values[pointIndex] : null;
    return { name: String(series.name || `Series ${index + 1}`), value: seriesDisplayValue(series, value), color: seriesColor(series, index) };
  });
  return { label, items };
}

function renderChartReadout(payload, xValue, { latest = false } = {}) {
  const node = queryNode("#chart-readout");
  if (!node) return "";
  if (xValue === null || xValue === undefined || !Number.isFinite(comparableX(xValue))) {
    node.innerHTML = "";
    return "";
  }
  const { label, items } = chartReadout(payload, xValue);
  node.innerHTML = `<time>${latest ? "Latest · " : ""}${escapeHtml(label)}</time>${items.map((item) => (
    `<span class="chart-readout-item"><i style="background:${escapeHtml(item.color)}" aria-hidden="true"></i>${escapeHtml(item.name)} <strong>${escapeHtml(item.value)}</strong></span>`
  )).join("")}`;
  return `${label}: ${items.map((item) => `${item.name} ${item.value}`).join(", ")}`;
}

// Keyboard (←/→) and touch scrubbing share one inspected position. The readout
// sits above the plot so a finger never covers it; the range is not changed.
function installTerminalInspector(target, payload) {
  if (typeof target?.addEventListener !== "function" || !target._fullLayout?.xaxis) return;
  target.classList.toggle("touch-inspect", touchInspectActive());
  const reference = inspectorReferenceSeries(payload);
  const coordinates = reference && ["date", "number"].includes(payload.x_value_type)
    ? [...new Map(reference.x.map((value) => [comparableX(value), value])).entries()]
      .filter(([time]) => Number.isFinite(time)).sort((a, b) => a[0] - b[0])
    : [];
  const anchor = payload.x_value_type === "date" ? observedRangeEnd(payload) : null;
  const latestIndex = () => {
    for (let index = coordinates.length - 1; index >= 0; index -= 1) {
      if (anchor === null || coordinates[index][0] <= anchor) return index;
    }
    return coordinates.length - 1;
  };
  let pinned = -1;
  const showLatest = () => {
    if (!coordinates.length) return renderChartReadout(payload, null);
    return renderChartReadout(payload, coordinates[latestIndex()][1], { latest: true });
  };
  const show = (index, { announce = false } = {}) => {
    if (!coordinates[index]) return;
    pinned = index;
    const [time, value] = coordinates[index];
    const text = renderChartReadout(payload, value);
    target.dataset.inspectX = String(value);
    try {
      window.Plotly?.Fx?.hover?.(target, { xval: payload.x_value_type === "date" ? time : value });
    } catch {
      // Hover labels are decorative here; the readout above carries the value.
    }
    if (announce) announceStatus(text, 120);
  };
  const visibleBounds = () => {
    const range = (target._fullLayout?.xaxis?.range || []).map(comparableX).filter(Number.isFinite).sort((a, b) => a - b);
    return range.length === 2 ? range : [-Infinity, Infinity];
  };
  const nearestIndex = (time) => {
    let best = -1;
    coordinates.forEach(([value], index) => {
      if (best < 0 || Math.abs(value - time) < Math.abs(coordinates[best][0] - time)) best = index;
    });
    return best;
  };
  const onKey = (event) => {
    if (event.target !== target || !coordinates.length || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const [low, high] = visibleBounds();
    const visible = coordinates.map(([time], index) => (time >= low && time <= high ? index : -1)).filter((index) => index >= 0);
    if (!visible.length) return;
    event.preventDefault();
    // Without a pinned point the readout already shows the latest visible
    // observation, so the first arrow press steps away from it.
    const latest = latestIndex();
    const current = visible.includes(pinned) ? pinned : visible.includes(latest) ? latest : visible.at(-1);
    let next;
    if (event.key === "Home") next = visible[0];
    else if (event.key === "End") next = visible.at(-1);
    else {
      const position = visible.indexOf(current) + (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 10 : 1);
      next = visible[clamp(position, 0, visible.length - 1)];
    }
    show(next, { announce: true });
  };
  let touch = null;
  const touchIndex = (event) => {
    const axis = target._fullLayout?.xaxis;
    if (!axis?.p2d) return -1;
    const bounds = target.getBoundingClientRect();
    const pixel = event.clientX - bounds.left - axis._offset;
    if (pixel < 0 || pixel > axis._length) return -1;
    return nearestIndex(comparableX(axis.p2d(pixel)));
  };
  const onTouchDown = (event) => {
    if (event.pointerType !== "touch" || !touchInspectActive() || !coordinates.length) return;
    if (!event.target.closest?.(".nsewdrag")) return;
    const index = touchIndex(event);
    if (index < 0) return;
    touch = event.pointerId;
    show(index);
  };
  const onTouchMove = (event) => {
    if (touch === null || event.pointerId !== touch) return;
    const index = touchIndex(event);
    if (index >= 0 && index !== pinned) show(index);
  };
  const onTouchEnd = (event) => {
    if (touch !== null && event.pointerId === touch) touch = null;
  };
  let hoverTimer = 0;
  const onHover = (event) => {
    clearTimeout(hoverTimer);
    const xValue = event?.points?.find((point) => point.x !== undefined)?.x;
    if (xValue !== undefined && touch === null) renderChartReadout(payload, xValue);
  };
  const onUnhover = () => {
    clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(() => {
      if (pinned >= 0 && coordinates[pinned]) renderChartReadout(payload, coordinates[pinned][1]);
      else showLatest();
    }, 120);
  };
  target.addEventListener("keydown", onKey);
  target.addEventListener("pointerdown", onTouchDown, true);
  target.addEventListener("pointermove", onTouchMove, true);
  target.addEventListener("pointerup", onTouchEnd, true);
  target.addEventListener("pointercancel", onTouchEnd, true);
  target.on?.("plotly_hover", onHover);
  target.on?.("plotly_unhover", onUnhover);
  showLatest();
  const priorCleanup = target._fintechChartCleanup;
  target._fintechChartCleanup = () => {
    clearTimeout(hoverTimer);
    target.removeEventListener("keydown", onKey);
    target.removeEventListener("pointerdown", onTouchDown, true);
    target.removeEventListener("pointermove", onTouchMove, true);
    target.removeEventListener("pointerup", onTouchEnd, true);
    target.removeEventListener("pointercancel", onTouchEnd, true);
    target.removeListener?.("plotly_hover", onHover);
    target.removeListener?.("plotly_unhover", onUnhover);
    delete target.dataset.inspectX;
    return typeof priorCleanup === "function" ? priorCleanup() : undefined;
  };
}

function nearestSeriesIndex(series, xValue) {
  const values = series?.x;
  if (!Array.isArray(values) || !values.length) return -1;
  const target = comparableX(xValue);
  if (!Number.isFinite(target)) return -1;
  let low = 0;
  let high = values.length - 1;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (comparableX(values[middle]) < target) low = middle + 1;
    else high = middle;
  }
  if (low === 0) return 0;
  const previous = comparableX(values[low - 1]);
  const current = comparableX(values[low]);
  return Math.abs(target - previous) <= Math.abs(current - target) ? low - 1 : low;
}

function comparableX(value) {
  if (value === null || value === undefined || value === "") return NaN;
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return numeric;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : NaN;
}

function seriesValueArray(series) {
  if (series?.orientation === "h" && Array.isArray(series.x)) return series.x;
  for (const key of ["y", "close", "open", "high", "low"]) {
    if (Array.isArray(series?.[key])) return series[key];
  }
  return [];
}

function expandGradientLine(series) {
  const values = series.marker?.color;
  const scale = series.marker?.colorscale;
  const pointColors = series.value_colored_line && Array.isArray(values)
    && values.every((value) => typeof value === "string");
  if (!Array.isArray(values) || (!pointColors && !Array.isArray(scale))
      || !Array.isArray(series.x) || !Array.isArray(series.y)) {
    return [series];
  }
  if (values.length !== series.y.length || series.x.length !== series.y.length) return [series];
  if (series.mode === "markers" || (!pointColors && values.some((value) => value !== null && typeof value !== "number"))) return [series];

  const lower = Number(series.marker.cmin);
  const upper = Number(series.marker.cmax);
  if (!pointColors && (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper)) return [series];

  const bucketCount = 24;
  const buckets = (pointColors ? [...new Set(values)] : Array.from({ length: bucketCount }, (_, index) => gradientColor(scale, (index + 0.5) / bucketCount)))
    .map((color) => ({ color, x: [], y: [] }));
  const byColor = new Map(buckets.map((bucket) => [bucket.color, bucket]));
  for (let index = 0; index < series.y.length - 1; index += 1) {
    const start = toFiniteNumber(series.y[index]);
    const end = toFiniteNumber(series.y[index + 1]);
    if (![start, end].every(Number.isFinite)) continue;
    if (series.x[index] === null || series.x[index + 1] === null) continue;
    let bucket;
    if (pointColors) bucket = byColor.get(values[index]);
    else {
      const colorStart = toFiniteNumber(values[index]);
      const colorEnd = toFiniteNumber(values[index + 1]);
      if (![colorStart, colorEnd].every(Number.isFinite)) continue;
      const ratio = clamp(((colorStart + colorEnd) / 2 - lower) / (upper - lower), 0, 1);
      bucket = buckets[Math.min(bucketCount - 1, Math.floor(ratio * bucketCount))];
    }
    bucket.x.push(series.x[index], series.x[index + 1], null);
    bucket.y.push(start, end, null);
  }

  const visibleBuckets = buckets.filter((bucket) => bucket.x.length);
  const { marker: _marker, ...lineSeries } = series;
  const legendgroup = series.legendgroup || `value-line-${series.source_key || series.name}`;
  const coloredSegments = visibleBuckets.map((bucket, index) => ({
    ...lineSeries,
    legendgroup,
    x: bucket.x,
    y: bucket.y,
    mode: "lines",
    line: { ...series.line, color: bucket.color, width: Math.max(1.5, series.line?.width || 1.8) },
    hoverinfo: "skip",
    showlegend: index === 0 && series.showlegend !== false,
  }));
  const hoverCarrier = {
    ...lineSeries,
    legendgroup,
    meta: { ...series.meta, fintechHelper: true },
    marker: series.marker,
    x: series.x,
    y: series.y,
    mode: "lines",
    fill: "none",
    line: { color: "rgba(0,0,0,0)", width: 10 },
    showlegend: false,
  };
  return [...coloredSegments, hoverCarrier];
}

function gradientColor(scale, ratio) {
  const stops = scale
    .map(([position, color]) => [Number(position), String(color)])
    .filter(([position, color]) => Number.isFinite(position) && /^#[0-9a-f]{6}$/i.test(color))
    .sort((left, right) => left[0] - right[0]);
  if (!stops.length) return "#c85f3c";
  const upperIndex = stops.findIndex(([position]) => position >= ratio);
  if (upperIndex < 0) return stops.at(-1)[1];
  if (upperIndex === 0) return stops[0][1];
  const [startAt, startColor] = stops[upperIndex - 1];
  const [endAt, endColor] = stops[upperIndex];
  const mix = endAt === startAt ? 1 : (ratio - startAt) / (endAt - startAt);
  const start = startColor.slice(1).match(/.{2}/g).map((part) => parseInt(part, 16));
  const end = endColor.slice(1).match(/.{2}/g).map((part) => parseInt(part, 16));
  const rgb = start.map((channel, index) => Math.round(channel + ((end[index] - channel) * mix)));
  return `#${rgb.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function sampleEvenly(values, count) {
  if (values.length <= count) return values;
  return Array.from({ length: count }, (_, index) => values[Math.round(index * (values.length - 1) / (count - 1))]);
}

// Phase buckets come from the published scoring method; the defaults mirror
// web/assets/signal-definitions.json for use before the signals have loaded.
function phaseFor(score, phases = appState.signalState?.method?.phases || DEFAULT_SIGNAL_PHASES) {
  const phase = phases.find((item) => item.below === null || item.below === undefined || score < item.below)
    || phases[phases.length - 1];
  return { key: phase.key, label: phase.label, className: `phase-${phase.key}` };
}

function phaseCounts(signals) {
  return signals.reduce((counts, signal) => {
    counts[signal.phase.key] += 1;
    return counts;
  }, { bottom: 0, bearish: 0, bullish: 0, top: 0 });
}

function phaseCountLabel(counts) {
  return `Bottom ${counts.bottom}, bearish ${counts.bearish}, bullish ${counts.bullish}, top ${counts.top}`;
}

function sparklineSvg(values, className = "") {
  const finite = values.map(Number).filter(Number.isFinite);
  if (finite.length < 2) return "";
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const span = max - min || 1;
  const points = finite.map((value, index) => `${(index / (finite.length - 1) * 100).toFixed(1)},${(25 - ((value - min) / span * 23)).toFixed(1)}`).join(" ");
  return `<svg class="${className}" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true"><polyline points="${points}"></polyline></svg>`;
}

async function getPayload(chartId) {
  if (appState.payloadCache.has(chartId)) return appState.payloadCache.get(chartId);
  const chart = chartById(chartId);
  if (!chart?.data_path) throw new Error(`No interactive data for ${chartId}`);
  const promise = fetchJson(assetPath(chart.data_path)).then(normalizePayload).catch((error) => {
    if (appState.payloadCache.get(chartId) === promise) appState.payloadCache.delete(chartId);
    throw error;
  });
  appState.payloadCache.set(chartId, promise);
  return promise;
}

function normalizePayload(payload) {
  if (payload?.id !== "never-look-back-price") return payload;
  return {
    ...payload,
    series: payload.series.map((series) => {
      if (!String(series.name || "").toLowerCase().includes("never look back") || !Array.isArray(series.y)) return series;
      let floor = null;
      return {
        ...series,
        y: series.y.map((raw) => {
          const value = toFiniteNumber(raw);
          if (Number.isFinite(value) && value > 0) floor = floor === null ? value : Math.max(floor, value);
          return floor;
        }),
      };
    }),
  };
}

function chartById(chartId) {
  return appState.manifest?.charts.find((chart) => chart.id === chartId);
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`Could not load ${path}`);
  return response.json();
}

function numericSeries(series) {
  return (series?.y || []).map(toFiniteNumber).filter(Number.isFinite);
}

function toFiniteNumber(value) {
  if (typeof value !== "number" && typeof value !== "string") return NaN;
  if (typeof value === "string" && !value.trim()) return NaN;
  const number = Number(value);
  return Number.isFinite(number) ? number : NaN;
}

function quantile(values, q) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return NaN;
  const position = (sorted.length - 1) * q;
  const base = Math.floor(position);
  const rest = position - base;
  return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base];
}

function deepMerge(target, source) {
  const output = { ...target };
  Object.entries(source || {}).forEach(([key, value]) => {
    output[key] = value && typeof value === "object" && !Array.isArray(value)
      ? deepMerge(output[key] || {}, value)
      : value;
  });
  return output;
}

function formatUsd(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const absolute = Math.abs(number);
  const maximumFractionDigits = absolute >= 100 ? 0 : absolute >= 1 ? 2 : absolute >= 0.01 ? 4 : 8;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits }).format(number);
}

function formatDate(date) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
}

function signed(value, digits = 1) {
  const number = Number(value);
  return `${number >= 0 ? "+" : ""}${number.toFixed(digits)}%`;
}

function average(values) {
  const finite = values.map(Number).filter(Number.isFinite);
  return finite.reduce((sum, value) => sum + value, 0) / (finite.length || 1);
}

function last(values) { return values?.[values.length - 1]; }

function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

function assetPath(path) {
  if (!path || /^(https?:)?\/\//.test(path) || path.startsWith("/") || path.startsWith("data:")) return path || "";
  return `${pageConfig.assetPrefix}${path}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderFatalError(error) {
  console.error(error);
  const workspace = document.querySelector("main") || document.body;
  workspace.innerHTML = `<div class="error-state"><strong>Dashboard data unavailable.</strong><br>${escapeHtml(error.message)}</div>`;
}

function visibleChartYRanges(target, xRange) {
  const layout = target?._fullLayout || target?.layout || {};
  const xAxis = layout.xaxis || {};
  if (!Array.isArray(xRange) || xRange.length !== 2 || ["category", "multicategory"].includes(xAxis.type)) return {};
  const bounds = xRange.map((value) => visibleChartAxisNumber(value, xAxis, true));
  if (!bounds.every(Number.isFinite)) return {};
  const start = Math.min(...bounds);
  const end = Math.max(...bounds);
  const extents = new Map();
  const preserved = new Set();
  const result = {};
  const barmode = layout.barmode || target?.layout?.barmode;

  for (const trace of target?.data || []) {
    if (!trace || trace.visible === false || trace.visible === "legendonly" || trace.opacity === 0
      || trace.meta?.fintechHelper === true || (trace.xaxis && trace.xaxis !== "x")) continue;
    const type = trace.type || "scatter";
    if (!["scatter", "scattergl", "candlestick", "ohlc", "bar"].includes(type) || trace.orientation === "h") continue;
    const mode = trace.mode || "lines";
    if (mode === "none" && !trace.fill) continue;
    // Financial hit-test proxies have no painted geometry. Their closing price
    // must not replace a candle's actual high and low when fitting the scale.
    if (["scatter", "scattergl"].includes(type) && !mode.includes("lines")
      && (trace.marker?.opacity === 0 || trace.marker?.size === 0)) continue;
    const axisName = trace.yaxis && trace.yaxis !== "y" ? `yaxis${trace.yaxis.slice(1)}` : "yaxis";
    const axis = { ...(target?.layout?.[axisName] || {}), ...(layout[axisName] || {}) };
    if (axis.fixedrange || ![undefined, "linear", "log"].includes(axis.type) || !Array.isArray(trace.x)) continue;
    const configured = target?.layout?.[axisName] || {};
    const configuredRange = configured.range;
    const hasConfiguredRange = Array.isArray(configuredRange) && configuredRange.length === 2 && configuredRange.every(Number.isFinite);
    const fixedTicks = [undefined, "array"].includes(configured.tickmode)
      && Array.isArray(configured.tickvals) && configured.tickvals.length > 1 && configured.tickvals.every(Number.isFinite);
    const title = typeof axis.title === "object" ? axis.title?.text : axis.title;
    const completePercentage = /%|\bpercent\b/i.test(`${axis.ticksuffix || ""} ${title || ""}`)
      && hasConfiguredRange && Math.min(...configuredRange) === 0 && Math.max(...configuredRange) === 100;
    // Fixed sentiment ticks and complete percentage scales carry meaning beyond
    // their visible observations. Dollar ticks are generated for each viewport
    // and must never prevent the price scale from fitting the selected dates.
    if (axis.tickprefix !== "$" && hasConfiguredRange && (fixedTicks || completePercentage)) {
      preserved.add(axisName);
      continue;
    }
    if (trace.stackgroup || trace.fill === "toself"
      || (type === "bar" && ["stack", "relative"].includes(barmode))) {
      // Per-series extrema underestimate compositions. Keep their complete
      // rendered bounds until a stack-aware fit can account for every cohort.
      preserved.add(axisName);
      continue;
    }
    const extent = extents.get(axisName) || { min: Infinity, max: -Infinity, axis };
    const add = (value) => {
      if (Number.isFinite(value)) {
        extent.min = Math.min(extent.min, value);
        extent.max = Math.max(extent.max, value);
      }
    };
    const isFinancial = type === "candlestick" || type === "ohlc";
    const hasLines = ["scatter", "scattergl"].includes(type)
      && (mode.includes("lines") || trace.fill && trace.fill !== "none");
    let previous = null;
    for (let index = 0; index < trace.x.length; index += 1) {
      const x = visibleChartAxisNumber(trace.x[index], xAxis);
      if (isFinancial) {
        if (Number.isFinite(x) && x >= start && x <= end) {
          for (const key of ["low", "high", "open", "close"]) add(visibleChartAxisNumber(trace[key]?.[index], axis));
        }
        continue;
      }
      const rawY = visibleChartFiniteNumber(trace.y?.[index]);
      const y = visibleChartAxisNumber(rawY, axis);
      if (!Number.isFinite(x) || (type === "bar" ? !Number.isFinite(rawY) : !Number.isFinite(y))) {
        if (!trace.connectgaps) previous = null;
        continue;
      }
      if (x >= start && x <= end) {
        if (type === "bar") {
          const baseValue = Array.isArray(trace.base) ? trace.base[index] : trace.base;
          const base = baseValue === undefined ? 0 : visibleChartFiniteNumber(baseValue);
          add(visibleChartAxisNumber(base, axis));
          add(visibleChartAxisNumber(base + rawY, axis));
        } else add(y);
      }
      // A zoom can fall wholly between sparse observations. Include the line
      // where it crosses each edge, interpolating in the rendered axis space.
      if (hasLines && previous && previous.x !== x) {
        const left = Math.min(previous.x, x);
        const right = Math.max(previous.x, x);
        for (const edge of [start, end]) {
          if (edge >= left && edge <= right) {
            add(previous.y + (y - previous.y) * (edge - previous.x) / (x - previous.x));
          }
        }
      }
      previous = { x, y };
    }
    if (Number.isFinite(extent.min) && trace.fill === "tozeroy") add(visibleChartAxisNumber(0, axis));
    extents.set(axisName, extent);
  }

  for (const [name, extent] of extents) {
    if (preserved.has(name) || !Number.isFinite(extent.min) || !Number.isFinite(extent.max)) continue;
    const span = extent.max - extent.min;
    const padding = (span || (extent.axis.type === "log" ? 1 : Math.max(Math.abs(extent.min), 1))) * 0.06;
    const range = [extent.min - padding, extent.max + padding];
    const previousRange = extent.axis.range;
    const reversed = Array.isArray(previousRange) && previousRange[0] > previousRange[1]
      || String(extent.axis.autorange).includes("reversed");
    result[name] = reversed ? range.reverse() : range;
  }
  for (const name of preserved) {
    const range = layout[name]?.range || target?.layout?.[name]?.range;
    if (Array.isArray(range) && range.length === 2 && range.every(Number.isFinite)) result[name] = range.slice();
  }
  return result;
}

function visibleChartFiniteNumber(value) {
  if (value === null || value === undefined || typeof value === "boolean" || (typeof value === "string" && !value.trim())) return NaN;
  return Number(value);
}

function visibleChartAxisNumber(value, axis, isRange = false) {
  if (value === null || value === undefined || typeof value === "boolean" || value === "") return NaN;
  if (axis.type === "date") {
    if (typeof value === "number") return value;
    // Plotly's timezone-free date strings represent UTC calendar values.
    const date = typeof value === "string" && /^\d{4}-\d\d-\d\d[ T]\d\d:\d\d/.test(value)
      && !/(Z|[+-]\d\d:?\d\d)$/i.test(value) ? `${value.replace(" ", "T")}Z` : value;
    return new Date(date).getTime();
  }
  const number = visibleChartFiniteNumber(value);
  return axis.type === "log" && !isRange ? (number > 0 ? Math.log10(number) : NaN) : number;
}

function priceAxisTickOptions(axis, range = axis?.range) {
  if (axis?.tickprefix !== "$" || !["linear", "log"].includes(axis.type)
    || !Array.isArray(range) || range.length !== 2 || !range.every(value => typeof value === "number" && Number.isFinite(value))) return {};
  const [lower, upper] = range.slice().sort((left, right) => left - right);
  const minimum = axis.type === "log" ? 10 ** lower : lower;
  const maximum = axis.type === "log" ? 10 ** upper : upper;
  if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || axis.type === "log" && minimum <= 0) return {};
  const count = Math.max(3, Math.min(9, Math.round((axis._length || 300) / 45)));
  const clean = value => value === 0 ? 0 : Number(value.toPrecision(14));
  let values = [];
  if (minimum === maximum) values = [clean(minimum)];
  else if (axis.type === "log" && upper - lower >= 0.75) {
    const candidates = [];
    if (upper - lower <= 2) {
      for (const multiples of [[1, 2, 5], [1, 2], [1, 5], [1]]) {
        const ticks = [];
        for (let exponent = Math.floor(lower); exponent <= Math.ceil(upper); exponent += 1) {
          for (const multiple of multiples) {
            const value = clean(multiple * 10 ** exponent);
            if (value >= minimum * (1 - 1e-12) && value <= maximum * (1 + 1e-12)) ticks.push(value);
          }
        }
        candidates.push(ticks);
      }
    } else {
      for (let stride = 1; stride <= Math.ceil(upper - lower); stride += 1) {
        const ticks = [];
        for (let exponent = Math.ceil(lower / stride) * stride; exponent <= upper + 1e-12; exponent += stride) {
          ticks.push(clean(10 ** exponent));
        }
        candidates.push(ticks);
      }
    }
    values = priceAxisBestTicks(candidates, count);
  } else {
    const span = maximum - minimum;
    if (!Number.isFinite(span) || span <= 0) return {};
    const exponent = Math.floor(Math.log10(span / (count - 1)));
    const candidates = [];
    for (let power = exponent - 1; power <= exponent + 1; power += 1) {
      for (const multiple of [1, 2, 2.5, 5]) {
        const step = multiple * 10 ** power;
        if (!Number.isFinite(step) || step <= 0) continue;
        const first = Math.ceil(minimum / step - 1e-10);
        const last = Math.floor(maximum / step + 1e-10);
        if (last - first > 8 || last < first) continue;
        candidates.push(Array.from({ length: last - first + 1 }, (_, index) => clean((first + index) * step)));
      }
    }
    values = priceAxisBestTicks(candidates, count);
  }
  values = [...new Set(values)].filter(Number.isFinite).sort((left, right) => left - right);
  if (!values.length) return {};
  const spacing = values.length > 1 ? Math.min(...values.slice(1).map((value, index) => value - values[index])) : Math.abs(values[0]) || 1;
  return { tickmode: "array", tickvals: values, ticktext: values.map(value => priceAxisTickLabel(value, spacing)) };
}

function priceAxisBestTicks(candidates, count) {
  // Prefer the intended density, retaining at least three labels where the
  // available nice increments allow it. Every label is a complete dollar value.
  return candidates.filter(values => values.length && values.length <= 9)
    .sort((left, right) => {
      const score = values => Math.abs(values.length - count) + (values.length < 3 ? 10 : 0);
      return score(left) - score(right);
    })[0] || [];
}

function priceAxisTickLabel(value, spacing) {
  const absolute = Math.abs(value);
  const units = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  const [divisor, suffix] = units.find(([threshold]) => absolute >= threshold) || [1, ""];
  const precision = Math.min(20, Math.max(0, Math.ceil(-Math.log10(spacing / divisor)) + 1));
  const number = (absolute / divisor).toLocaleString("en-US", { maximumFractionDigits: precision, useGrouping: true });
  return `${value < 0 ? "-" : ""}$${number}${suffix}`;
}

// Series values follow the nearest hovered observation; the existing black
// crosshair badges continue to show the pointer's independent coordinates.
function installSeriesValueBadges(target) {
  if (!target?._fullLayout?._size || typeof target.on !== "function") return;
  const badges = new Map();
  const hide = () => badges.forEach(badge => badge.classList.remove("visible"));
  const onHover = event => {
    hide();
    if (target.classList.contains("chart-selecting")) return;
    const layout = target._fullLayout;
    const usedAxes = new Set();
    for (const point of event?.points || []) {
      const trace = point.data || point.fullData || {};
      const fullTrace = point.fullData || trace;
      if ([false, "legendonly"].includes(fullTrace.visible) || [false, "legendonly"].includes(trace.visible)
          || !["scatter", "scattergl", "bar", "candlestick", "ohlc"].includes(trace.type || fullTrace.type)) continue;
      const reference = trace.yaxis || fullTrace.yaxis || point.yaxis?._id || "y";
      const axisName = reference === "y" ? "yaxis" : `yaxis${reference.slice(1)}`;
      const axis = layout[axisName];
      const value = visibleChartFiniteNumber(point.y ?? point.close);
      if (!axis || axis.visible === false || axis.showticklabels === false
          || !["linear", "log"].includes(axis.type) || usedAxes.has(axisName)
          || !Number.isFinite(value) || axis.type === "log" && value <= 0) continue;
      const pixel = axis.d2p?.(value);
      if (!Number.isFinite(pixel) || pixel < 0 || pixel > axis._length) continue;
      const xaxis = point.xaxis || layout.xaxis;
      if (!xaxis || !Number.isFinite(axis._offset)) continue;
      const side = axis.side === "right" ? "right" : "left";
      let badge = badges.get(axisName);
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "chart-series-value-badge";
        badge.setAttribute("aria-hidden", "true");
        badge.dataset.axis = axisName;
        badges.set(axisName, badge);
        target.appendChild(badge);
      }
      const price = trace.source_key === "price" || /^(?:BTC (?:price|OHLC)|Price(?: USD)?)$/i.test(trace.name || "");
      badge.textContent = formatCrosshairValue(value, {
        tickprefix: axis.tickprefix || trace.value_prefix || (price ? "$" : ""),
        ticksuffix: axis.ticksuffix || trace.value_suffix || "",
      });
      const color = seriesValueBadgeColor(point);
      badge.style.backgroundColor = color;
      badge.style.color = seriesValueBadgeTextColor(color);
      badge.dataset.side = side;
      badge.style.left = `${axis.anchor === "free" && Number.isFinite(axis.position)
        ? layout._size.l + axis.position * layout._size.w
        : xaxis._offset + (side === "right" ? xaxis._length : 0)}px`;
      badge.style.top = `${axis._offset + pixel}px`;
      badge.classList.add("visible");
      usedAxes.add(axisName);
    }
  };
  const events = { plotly_hover: onHover, plotly_unhover: hide, plotly_selecting: hide, plotly_relayout: hide };
  Object.entries(events).forEach(([name, listener]) => target.on(name, listener));
  target.addEventListener("pointerleave", hide);
  const priorCleanup = target._fintechChartCleanup;
  target._fintechChartCleanup = () => {
    Object.entries(events).forEach(([name, listener]) => target.removeListener?.(name, listener));
    target.removeEventListener("pointerleave", hide);
    badges.forEach(badge => badge.remove());
    badges.clear();
    if (typeof priorCleanup === "function") priorCleanup();
  };
}

function seriesValueBadgeColor(point) {
  const trace = point.data || point.fullData || {};
  const fullTrace = point.fullData || trace;
  const marker = { ...fullTrace.marker, ...trace.marker };
  const index = Number.isInteger(point.pointNumber) ? point.pointNumber : point.pointIndex;
  const markerValue = Array.isArray(marker.color) ? marker.color[index] : marker.color;
  if (typeof markerValue === "number" && Array.isArray(marker.colorscale)) {
    const min = Number(marker.cmin);
    const max = Number(marker.cmax);
    if (Number.isFinite(min) && Number.isFinite(max) && min < max) {
      return gradientColor(marker.colorscale, clamp((markerValue - min) / (max - min), 0, 1));
    }
  }
  const candidates = [point.color, trace.marker?.color !== undefined || String(trace.mode).includes("markers") ? markerValue : null,
    trace.line?.color, fullTrace.line?.color];
  return candidates.find(color => seriesValueBadgeRgb(color)) || "#c96442";
}

function seriesValueBadgeRgb(color) {
  if (typeof color !== "string") return null;
  const hex = color.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const value = hex[1].length === 3 ? hex[1].split("").map(channel => channel + channel).join("") : hex[1];
    return value.match(/../g).map(channel => parseInt(channel, 16));
  }
  const rgb = color.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/i);
  if (!rgb || rgb[4] !== undefined && Number(rgb[4]) < 0.35) return null;
  return rgb.slice(1, 4).map(channel => clamp(Number(channel), 0, 255));
}

function seriesValueBadgeTextColor(color) {
  const rgb = seriesValueBadgeRgb(color) || [201, 100, 66];
  const linear = rgb.map(channel => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  const luminance = linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
  return luminance > 0.179 ? "#1f211f" : "#ffffff";
}
