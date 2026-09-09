const appState = {
  manifest: null,
  payloadCache: new Map(),
  signals: [],
  activeChartId: null,
  currentChart: null,
  currentPayload: null,
  chartOptions: {
    movingAverage: false,
    halvings: false,
    grid: true,
    table: false,
    scale: null,
  },
};

const initialParams = new URLSearchParams(window.location.search);
const pageConfig = {
  view: document.body.dataset.view || "dashboard",
  manifestPath: document.body.dataset.manifest || "web/data/bitcoin/site-manifest.json",
  assetPrefix: document.body.dataset.assetPrefix || "",
  market: document.body.dataset.market || initialParams.get("market") || "bitcoin",
};

if (pageConfig.view === "charts" && pageConfig.market === "stocks") {
  pageConfig.manifestPath = `${pageConfig.assetPrefix}web/data/stocks/site-manifest.json`;
}

const POPULAR_IDS = [
  "price-prediction-models",
  "200-dma-200-wma",
  "mayer-multiple",
  "pi-cycle-top",
  "power-law-oscillator",
  "cycle-phase-dashboard",
  "monthly-yearly-returns",
  "drawdown-recovery-map",
];

const SIGNAL_DEFINITIONS = [
  { id: "trend", chartId: "200-dma-200-wma", label: "Price vs 200D average", category: "Trend", build: ratioSeries(0, 1) },
  { id: "mayer", chartId: "mayer-multiple", label: "Mayer Multiple", category: "Valuation", series: 0 },
  { id: "drawdown", chartId: "drawdown-recovery-map", label: "Drawdown from ATH", category: "Cycle", series: 0 },
  { id: "pi-cycle", chartId: "pi-cycle-top", label: "Pi Cycle spread", category: "Cycle", build: ratioSeries(1, 2) },
  { id: "power-law", chartId: "power-law-oscillator", label: "Power Law Oscillator", category: "Valuation", series: 0 },
  { id: "puell", chartId: "puell-multiple", label: "Puell Multiple", category: "Mining", series: 1 },
  { id: "volatility", chartId: "volatility-regimes", label: "Realized volatility", category: "Risk", series: 0 },
  { id: "bollinger", chartId: "bollinger-bands", label: "Bollinger position", category: "Trend", build: bandPositionSeries(0, 1, 2) },
  { id: "sharpe", chartId: "risk-adjusted-returns", label: "1Y Sharpe proxy", category: "Momentum", series: 0 },
  { id: "fees", chartId: "fee-pressure", label: "Fee pressure", category: "Mining", series: 0 },
  { id: "hashprice", chartId: "miner-hashprice", label: "Miner hashprice", category: "Mining", series: 1 },
  { id: "ath-age", chartId: "days-since-ath", label: "ATH recency", category: "Cycle", series: 1, invert: true },
];

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

function bindKeyboardSearch() {
  const search = document.querySelector("#sidebar-search");
  if (!search) return;
  search.addEventListener("input", () => renderSidebar(search.value.trim().toLowerCase()));
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement?.tagName !== "INPUT") {
      event.preventDefault();
      search.focus();
    }
  });
}

function renderSidebar(query = "") {
  const charts = appState.manifest.charts.filter((chart) => {
    const haystack = `${chart.title} ${chart.section} ${chart.description}`.toLowerCase();
    return !query || haystack.includes(query);
  }).sort((a, b) => a.title.localeCompare(b.title));
  const selectedPopular = POPULAR_IDS.map((id) => charts.find((chart) => chart.id === id)).filter(Boolean);
  const stockPopular = charts.filter((chart) => chart.title.startsWith("Popular Stocks") || chart.title.includes("Sector Performance"));
  const popularLayer = selectedPopular.length ? selectedPopular : (stockPopular.length ? stockPopular.slice(0, 8) : charts.slice(0, 8));
  const allList = document.querySelector("#all-chart-list");
  const popularList = document.querySelector("#popular-list");
  if (!allList || !popularList) return;

  popularList.classList.remove("skeleton-list");
  allList.classList.remove("skeleton-list");
  popularList.innerHTML = popularLayer.length
    ? popularLayer.map((chart) => sidebarChartLink(chart)).join("")
    : `<p class="empty-state">No popular charts match.</p>`;

  let lastLetter = "";
  allList.innerHTML = charts.map((chart) => {
    const letter = chart.title.charAt(0).toUpperCase();
    const heading = letter !== lastLetter
      ? `<div class="sidebar-section-label" data-letter="${escapeHtml(letter)}"><span class="visually-hidden">Charts beginning with ${escapeHtml(letter)}</span></div>`
      : "";
    lastLetter = letter;
    return `${heading}${sidebarChartLink(chart)}`;
  }).join("") || `<p class="empty-state">No charts match this search.</p>`;

  document.querySelector("#popular-count").textContent = String(popularLayer.length);
  document.querySelector("#all-count").textContent = String(charts.length);
}

function sidebarChartLink(chart) {
  const marketParam = pageConfig.market === "stocks" ? "market=stocks&" : "";
  const href = pageConfig.assetPrefix
    ? `${pageConfig.assetPrefix}charts/?${marketParam}chart=${encodeURIComponent(chart.id)}`
    : `charts/?${marketParam}chart=${encodeURIComponent(chart.id)}`;
  return `
    <a class="sidebar-chart-link ${chart.id === appState.activeChartId ? "active" : ""}" href="${href}" data-chart-id="${escapeHtml(chart.id)}">
      <span>${escapeHtml(chart.title)}</span>
      ${chart.kind === "interactive" ? `<span class="pin-mark" aria-label="Interactive">◔</span>` : ""}
    </a>
  `;
}

async function renderDashboard() {
  appState.signals = await buildSignals();
  await Promise.all([
    renderMetricRibbon(),
    renderSignalHeatmap(document.querySelector("#dashboard-signal-heatmap"), appState.signals, 56),
    renderDashboardCharts(),
  ]);
  const updated = new Date(appState.manifest.generated_at);
  document.querySelector("#dashboard-updated").textContent = `Updated ${formatDate(updated)}`;
  document.addEventListener("fintech-theme-change", renderDashboardCharts);
}

async function renderMetricRibbon() {
  const ribbon = document.querySelector("#metric-ribbon");
  const trend = await getPayload("200-dma-200-wma");
  const prices = numericSeries(trend.series[0]);
  const latestPrice = last(prices);
  const monthAgoPrice = prices[Math.max(0, prices.length - 31)];
  const change30 = ((latestPrice / monthAgoPrice) - 1) * 100;
  const ma200 = last(numericSeries(trend.series[1]));
  const distance = ((latestPrice / ma200) - 1) * 100;
  const cycleIndex = average(appState.signals.map((signal) => signal.score));
  const bullishCount = appState.signals.filter((signal) => signal.score >= 50).length;
  const phases = phaseCounts(appState.signals);
  const phase = phaseFor(cycleIndex);
  const recentPrice = trend.series[0].y.slice(-45);
  const recentAverage = trend.series[1].y.slice(-45);
  const recentRatios = recentPrice.map((value, index) => Number(value) / Number(recentAverage[index]));

  ribbon.innerHTML = `
    <article class="terminal-metric">
      <span class="terminal-metric-label">Bitcoin price</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${formatUsd(latestPrice)}</strong>
        <span class="terminal-metric-change ${change30 < 0 ? "negative" : ""}">${signed(change30)} 30d</span>
      </div>
      ${sparklineSvg(prices.slice(-45))}
    </article>
    <article class="terminal-metric">
      <span class="terminal-metric-label">Price vs 200D</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${signed(distance)}</strong>
        <span class="terminal-metric-change ${distance < 0 ? "negative" : ""}">${distance >= 0 ? "above trend" : "below trend"}</span>
      </div>
      ${sparklineSvg(recentRatios)}
    </article>
    <article class="terminal-metric">
      <span class="terminal-metric-label">Cycle index</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${Math.round(cycleIndex)}</strong>
        <span class="metric-phase">${phase.label}</span>
      </div>
      <div class="metric-bar" aria-hidden="true"><span style="width:25%"></span><span style="width:25%"></span><span style="width:25%"></span><span style="width:25%"></span></div>
    </article>
    <article class="terminal-metric">
      <span class="terminal-metric-label">Signal breadth</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${bullishCount}</strong>
        <span class="terminal-metric-change">/ ${appState.signals.length} bullish</span>
      </div>
      <div class="metric-bar" aria-label="${phaseCountLabel(phases)}">
        <span style="width:${phases.bottom / appState.signals.length * 100}%"></span>
        <span style="width:${phases.bearish / appState.signals.length * 100}%"></span>
        <span style="width:${phases.bullish / appState.signals.length * 100}%"></span>
        <span style="width:${phases.top / appState.signals.length * 100}%"></span>
      </div>
    </article>
  `;
}

async function renderDashboardCharts() {
  const grid = document.querySelector("#dashboard-chart-grid");
  const chartIds = ["price-prediction-models", "200-dma-200-wma", "mayer-multiple", "drawdown-recovery-map"];
  grid.innerHTML = chartIds.map((id) => {
    const chart = chartById(id);
    return `
      <article class="dashboard-chart-card">
        <div class="dashboard-card-heading">
          <strong>${escapeHtml(chart?.title || id)}</strong>
          <a href="charts/?chart=${encodeURIComponent(id)}" aria-label="Open ${escapeHtml(chart?.title || id)}">•••</a>
        </div>
        <div id="dashboard-plot-${escapeHtml(id)}" class="dashboard-mini-plot loading-block"></div>
      </article>
    `;
  }).join("");

  await Promise.all(chartIds.map(async (id) => {
    const payload = await getPayload(id);
    const target = document.querySelector(`#dashboard-plot-${CSS.escape(id)}`);
    target.classList.remove("loading-block");
    renderPlot(target, payload, { compact: true, maxPoints: 600 });
  }));
}

async function renderChartTerminal() {
  const marketSwitch = document.querySelector(".market-switch");
  if (marketSwitch) {
    marketSwitch.textContent = pageConfig.market === "stocks" ? "Bitcoin" : "Stocks";
    marketSwitch.href = pageConfig.market === "stocks" ? "./" : "?market=stocks";
  }

  bindChartToolbar();
  document.querySelectorAll(".sidebar-chart-link[data-chart-id]").forEach(bindChartLink);
  if (pageConfig.market !== "stocks") appState.signals = await buildSignals();
  const requestedId = initialParams.get("chart");
  const firstInteractive = appState.manifest.charts.find((chart) => chart.kind === "interactive" && chart.data_path);
  const firstChart = appState.manifest.charts.find((chart) => chart.id === requestedId)
    || appState.manifest.charts.find((chart) => chart.id === POPULAR_IDS[0])
    || firstInteractive
    || appState.manifest.charts[0];
  if (firstChart) await selectTerminalChart(firstChart.id, { updateUrl: false });

  document.addEventListener("fintech-theme-change", () => {
    if (appState.currentPayload && !appState.chartOptions.table) renderTerminalPlot();
  });
}

function bindChartLink(link) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
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
}

async function selectTerminalChart(chartId, options = {}) {
  const chart = chartById(chartId);
  if (!chart) return;
  appState.activeChartId = chart.id;
  appState.currentChart = chart;
  appState.currentPayload = null;
  appState.chartOptions.movingAverage = false;
  appState.chartOptions.halvings = false;
  appState.chartOptions.table = false;
  appState.chartOptions.scale = null;
  document.querySelectorAll("[data-chart-action]").forEach((button) => button.classList.remove("active"));
  document.querySelector('[data-chart-action="grid"]')?.classList.toggle("active", !appState.chartOptions.grid);
  const pinButton = document.querySelector('[data-chart-action="pin"]');
  if (pinButton) {
    const pinned = new Set(JSON.parse(localStorage.getItem("fintech-pins") || "[]")).has(chart.id);
    pinButton.classList.toggle("active", pinned);
    pinButton.textContent = pinned ? "⌖ Pinned" : "⌖ Pin";
  }
  document.querySelector("#terminal-plot")?.removeAttribute("hidden");
  document.querySelector("#data-sheet")?.setAttribute("hidden", "");

  const search = document.querySelector("#sidebar-search");
  renderSidebar(search?.value.trim().toLowerCase() || "");
  document.querySelectorAll(".sidebar-chart-link[data-chart-id]").forEach(bindChartLink);
  updateChartHeadings(chart);
  if (options.updateUrl !== false) {
    const url = new URL(window.location.href);
    url.searchParams.set("chart", chart.id);
    if (pageConfig.market === "stocks") url.searchParams.set("market", "stocks");
    history.replaceState(null, "", url);
  }

  const target = document.querySelector("#terminal-plot");
  target.innerHTML = "";
  target.classList.add("loading-block");

  if (!chart.data_path) {
    renderImageChart(chart, target);
    return;
  }

  try {
    const payload = await getPayload(chart.id);
    if (appState.activeChartId !== chart.id) return;
    appState.currentPayload = payload;
    appState.chartOptions.scale = payload.default_scale || payload.layout?.yaxis?.type || "linear";
    target.classList.remove("loading-block");
    await renderTerminalPlot();
    renderChartDetails(payload);
    renderDataSheet(payload);
    updateScaleButton();
  } catch (error) {
    target.classList.remove("loading-block");
    if (chart.image_path) renderImageChart(chart, target);
    else target.innerHTML = `<p class="error-state">${escapeHtml(error.message)}</p>`;
  }
}

function updateChartHeadings(chart) {
  ["#chart-title", "#chart-mobile-title"].forEach((selector) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = chart.title;
  });
  ["#chart-section", "#chart-mobile-section"].forEach((selector) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = pageConfig.market === "stocks" ? `Stocks · ${chart.section}` : chart.section;
  });
  const summary = document.querySelector("#chart-summary");
  if (summary) summary.textContent = chart.description;
  const alertLink = document.querySelector("#chart-alert-link");
  if (alertLink) {
    const definition = SIGNAL_DEFINITIONS.find((item) => item.chartId === chart.id);
    alertLink.href = definition ? `../alerts/?signal=${encodeURIComponent(definition.id)}` : "../alerts/";
  }
}

async function renderTerminalPlot() {
  const target = document.querySelector("#terminal-plot");
  const payload = appState.currentPayload;
  if (!target || !payload) return;
  target.innerHTML = "";
  const series = terminalSeries(payload);
  const layout = terminalLayout(payload);
  await renderPlot(target, payload, { series, layout, grid: appState.chartOptions.grid, maxPoints: 2200 });
  if (appState.chartOptions.scale && payload.layout?.yaxis !== undefined) {
    const updates = {};
    (payload.scale_axes || ["y"]).forEach((axis) => {
      updates[`${axis === "y" ? "yaxis" : `yaxis${axis.replace("y", "")}`}.type`] = appState.chartOptions.scale;
    });
    if (Object.keys(updates).length) Plotly.relayout(target, updates).catch(() => {});
  }
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
  const layout = {};
  if (appState.chartOptions.halvings && payload.x_value_type !== "number") {
    const existingShapes = payload.layout?.shapes || [];
    layout.shapes = [
      ...existingShapes,
      ...["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"].map((date) => ({
        type: "line",
        xref: "x",
        yref: "paper",
        x0: date,
        x1: date,
        y0: 0,
        y1: 1,
        line: { color: "#c85f3c", width: 1, dash: "dot" },
      })),
    ];
    layout.annotations = [
      ...(payload.layout?.annotations || []),
      ...["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"].map((date, index) => ({
        x: date,
        y: 0.02,
        xref: "x",
        yref: "paper",
        text: `Halving ${index + 1}`,
        showarrow: false,
        textangle: 90,
        font: { size: 9, color: "#98958e" },
      })),
    ];
  }
  return layout;
}

function renderImageChart(chart, target) {
  target.classList.remove("loading-block");
  target.innerHTML = chart.image_path
    ? `<img class="terminal-chart-image" src="${escapeHtml(assetPath(chart.image_path))}" alt="${escapeHtml(chart.title)}">`
    : `<p class="empty-state">This report does not have a browser-ready chart payload yet.</p>`;
  document.querySelector("#series-list").innerHTML = `<p class="empty-state">Generated report image</p>`;
  document.querySelector("#performance-list").innerHTML = "";
  document.querySelector("#chart-phase").innerHTML = `<span>Report</span><strong>Image view</strong>`;
}

function renderChartDetails(payload) {
  const seriesList = document.querySelector("#series-list");
  const performanceList = document.querySelector("#performance-list");
  const latestDate = payload.series.find((series) => Array.isArray(series.x))?.x?.at(-1);
  document.querySelector("#series-date").textContent = latestDate ? shortDate(latestDate) : "Latest";
  document.querySelector("#chart-summary").textContent = payload.summary_text || appState.currentChart.description;

  seriesList.innerHTML = payload.series.slice(0, 8).map((series, index) => {
    const values = primaryValues(series);
    const value = last(values);
    return `
      <div class="series-row">
        <span class="series-dot" style="background:${seriesColor(series, index)}"></span>
        <span class="series-name" title="${escapeHtml(series.name)}">${escapeHtml(series.name)}</span>
        <strong class="series-value">${formatMetricValue(series.name, value)}</strong>
      </div>
    `;
  }).join("");

  const base = payload.series.find((series) => primaryValues(series).length > 2);
  performanceList.innerHTML = base
    ? [[7, "1W"], [30, "1M"], [90, "3M"], [180, "6M"], [365, "1Y"]].map(([days, label]) => {
      const change = seriesReturn(base, days);
      const width = Math.min(50, Math.abs(change) / 2);
      return `
        <div class="performance-row ${change < 0 ? "negative" : ""}">
          <span>${label}</span>
          <span class="performance-bar"><span style="width:${width}%"></span></span>
          <strong class="performance-value">${signed(change)}</strong>
        </div>
      `;
    }).join("")
    : `<p class="empty-state">Performance comparison is unavailable for this chart type.</p>`;

  const signal = appState.signals.find((item) => item.chartId === appState.currentChart.id);
  const phaseBox = document.querySelector("#chart-phase");
  if (signal) phaseBox.innerHTML = `<span>Cycle signal</span><strong>${Math.round(signal.score)} · ${signal.phase.label}</strong>`;
  else phaseBox.innerHTML = `<span>Data status</span><strong>${formatDate(new Date(payload.updated_at || appState.manifest.generated_at))}</strong>`;
}

function renderDataSheet(payload) {
  const sheet = document.querySelector("#data-sheet");
  const compatible = payload.series.filter((series) => Array.isArray(series.x) && Array.isArray(series.y));
  if (!compatible.length) {
    sheet.innerHTML = `<p class="empty-state">A tabular view is not available for this chart type.</p>`;
    return;
  }
  const base = compatible[0];
  const start = Math.max(0, base.x.length - 250);
  const headers = compatible.map((series) => `<th>${escapeHtml(series.name)}</th>`).join("");
  const rows = base.x.slice(start).map((date, rowIndex) => {
    const sourceIndex = start + rowIndex;
    const values = compatible.map((series) => `<td>${escapeHtml(formatMetricValue(series.name, Number(series.y[sourceIndex])))}</td>`).join("");
    return `<tr><td>${escapeHtml(shortDate(date))}</td>${values}</tr>`;
  }).reverse().join("");
  sheet.innerHTML = `<table><thead><tr><th>Date</th>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
}

async function handleChartAction(action, button) {
  if (!appState.currentChart) return;
  if (action === "moving-average") {
    appState.chartOptions.movingAverage = !appState.chartOptions.movingAverage;
    button.classList.toggle("active", appState.chartOptions.movingAverage);
    if (appState.currentPayload) await renderTerminalPlot();
  }
  if (action === "halvings") {
    appState.chartOptions.halvings = !appState.chartOptions.halvings;
    button.classList.toggle("active", appState.chartOptions.halvings);
    if (appState.currentPayload) await renderTerminalPlot();
  }
  if (action === "grid") {
    appState.chartOptions.grid = !appState.chartOptions.grid;
    button.classList.toggle("active", !appState.chartOptions.grid);
    if (appState.currentPayload) await renderTerminalPlot();
  }
  if (action === "table") {
    appState.chartOptions.table = !appState.chartOptions.table;
    button.classList.toggle("active", appState.chartOptions.table);
    document.querySelector("#terminal-plot").hidden = appState.chartOptions.table;
    document.querySelector("#data-sheet").hidden = !appState.chartOptions.table;
  }
  if (action === "pin") togglePinnedChart(button);
  if (action === "download" && appState.currentPayload && !appState.chartOptions.table) {
    Plotly.downloadImage(document.querySelector("#terminal-plot"), {
      format: "png",
      filename: appState.currentChart.id,
      width: 1600,
      height: 900,
    });
  }
}

function togglePinnedChart(button) {
  const pins = new Set(JSON.parse(localStorage.getItem("fintech-pins") || "[]"));
  if (pins.has(appState.currentChart.id)) pins.delete(appState.currentChart.id);
  else pins.add(appState.currentChart.id);
  localStorage.setItem("fintech-pins", JSON.stringify([...pins]));
  button.classList.toggle("active", pins.has(appState.currentChart.id));
  button.textContent = pins.has(appState.currentChart.id) ? "⌖ Pinned" : "⌖ Pin";
}

function setChartRange(range) {
  if (!appState.currentPayload || !window.Plotly) return;
  document.querySelectorAll("[data-range]").forEach((button) => button.classList.toggle("active", button.dataset.range === range));
  const firstSeries = appState.currentPayload.series.find((series) => Array.isArray(series.x));
  if (!firstSeries?.x?.length || appState.currentPayload.x_value_type === "number" || range === "all") {
    Plotly.relayout(document.querySelector("#terminal-plot"), { "xaxis.autorange": true });
    return;
  }
  const end = new Date(last(firstSeries.x));
  let start = new Date(end);
  if (range === "1m") start.setUTCMonth(start.getUTCMonth() - 1);
  if (range === "3m") start.setUTCMonth(start.getUTCMonth() - 3);
  if (range === "6m") start.setUTCMonth(start.getUTCMonth() - 6);
  if (range === "1y") start.setUTCFullYear(start.getUTCFullYear() - 1);
  if (range === "4y") start.setUTCFullYear(start.getUTCFullYear() - 4);
  if (range === "ytd") start = new Date(Date.UTC(end.getUTCFullYear(), 0, 1));
  Plotly.relayout(document.querySelector("#terminal-plot"), { "xaxis.range": [start.toISOString(), end.toISOString()] });
}

function toggleChartScale() {
  const payload = appState.currentPayload;
  if (!payload?.allow_scale_toggle) return;
  appState.chartOptions.scale = appState.chartOptions.scale === "log" ? "linear" : "log";
  updateScaleButton();
  const update = {};
  (payload.scale_axes || ["y"]).forEach((axis) => {
    const layoutKey = axis === "y" ? "yaxis" : `yaxis${axis.replace("y", "")}`;
    update[`${layoutKey}.type`] = appState.chartOptions.scale;
  });
  Plotly.relayout(document.querySelector("#terminal-plot"), update);
}

function updateScaleButton() {
  const button = document.querySelector("#scale-toggle");
  if (!button || !appState.currentPayload) return;
  button.disabled = !appState.currentPayload.allow_scale_toggle;
  button.textContent = appState.chartOptions.scale || "linear";
  button.classList.toggle("active", appState.chartOptions.scale === "log");
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
  for (const key of ["y", "close", "open", "high", "low"]) {
    if (Array.isArray(series?.[key])) return series[key].map(toFiniteNumber).filter(Number.isFinite);
  }
  return [];
}

function seriesReturn(series, days) {
  const values = primaryValues(series);
  if (values.length < 2) return 0;
  const latest = last(values);
  let previous;
  if (Array.isArray(series.x) && series.x.length === (series.y || series.close || []).length) {
    const latestDate = new Date(last(series.x));
    const target = new Date(latestDate);
    target.setUTCDate(target.getUTCDate() - days);
    let index = series.x.findIndex((date) => new Date(date) >= target);
    if (index < 0) index = Math.max(0, values.length - days - 1);
    previous = Number((series.y || series.close)[index]);
  } else {
    previous = values[Math.max(0, values.length - days - 1)];
  }
  if (!Number.isFinite(previous) || previous === 0) return 0;
  return ((latest / previous) - 1) * 100;
}

function seriesColor(series, index) {
  const legacyMap = { "#f5c84b": "#c85f3c", "#55d6ff": "#2863a7", "#3ce38a": "#16844d", "#ff5f63": "#c91f50", "#ff9f43": "#d98945", "#ff5ccd": "#9d4c83" };
  const color = series.line?.color || (typeof series.marker?.color === "string" ? series.marker.color : null);
  return legacyMap[color] || color || ["#c85f3c", "#2863a7", "#16844d", "#c91f50", "#7c5ca8"][index % 5];
}

async function renderSignalsPage() {
  appState.signals = await buildSignals();
  const categoryFilter = document.querySelector("#signal-category-filter");
  const phaseFilter = document.querySelector("#signal-phase-filter");
  const categories = [...new Set(appState.signals.map((signal) => signal.category))].sort();
  categoryFilter.insertAdjacentHTML("beforeend", categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join(""));
  const refresh = () => updateSignalsPage(categoryFilter.value, phaseFilter.value);
  categoryFilter.addEventListener("change", refresh);
  phaseFilter.addEventListener("change", refresh);
  updateSignalsPage("all", "all");
}

function updateSignalsPage(category, phase) {
  const signals = appState.signals.filter((signal) => {
    const matchesCategory = category === "all" || signal.category === category;
    const matchesPhase = phase === "all" || signal.phase.key === phase;
    return matchesCategory && matchesPhase;
  });
  renderSignalHeatmap(document.querySelector("#signal-page-heatmap"), signals, 68);
  renderCycleSpectrum(signals);
  renderSignalSummary(signals);
  renderSignalTable(signals);
  renderSignalInsights(signals);
}

function renderCycleSpectrum(signals) {
  const target = document.querySelector("#cycle-spectrum");
  target.classList.remove("loading-block");
  if (!signals.length) {
    target.innerHTML = `<p class="empty-state">No signals match these filters.</p>`;
    return;
  }
  const index = average(signals.map((signal) => signal.score));
  const dots = signals.map((signal, rowIndex) => {
    const score = clamp(signal.score, 0, 100);
    const height = 24 + (rowIndex % 5) * 13;
    const color = phaseColor(signal.phase.key);
    return `
      <span class="spectrum-stem" style="left:clamp(36px, ${score}%, calc(100% - 36px)); --stem-height:${height}px"></span>
      <a class="spectrum-dot" style="left:clamp(36px, ${score}%, calc(100% - 36px)); bottom:${35 + height}px; background:${color}" href="../charts/?chart=${encodeURIComponent(signal.chartId)}" title="${escapeHtml(signal.label)} · ${Math.round(score)}"></a>
    `;
  }).join("");
  target.innerHTML = `
    <div class="spectrum-track" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
    ${dots}
    <span class="spectrum-index" style="left:clamp(36px, ${index}%, calc(100% - 36px))" title="Cycle index ${Math.round(index)}"></span>
    <span class="spectrum-index-label" style="left:clamp(48px, ${index}%, calc(100% - 48px))">INDEX ${Math.round(index)}</span>
    <div class="spectrum-labels"><span>Bottom</span><span>Bearish</span><span>Bullish</span><span>Top</span></div>
  `;
}

function renderSignalSummary(signals) {
  const target = document.querySelector("#signal-summary");
  if (!signals.length) {
    target.innerHTML = `<p class="empty-state">No signal summary is available for the current filters.</p>`;
    return;
  }
  const counts = phaseCounts(signals);
  const index = average(signals.map((signal) => signal.score));
  const bullish = signals.filter((signal) => signal.score >= 50).length;
  const rising = signals.filter((signal) => signalDelta(signal, 30) > 0).length;
  const trendSignal = appState.signals.find((signal) => signal.id === "trend");
  const priceSeries = trendSignal?.payload?.series?.[0];
  const price = last(primaryValues(priceSeries));
  target.innerHTML = `
    <article class="signal-summary-item"><small>Cycle index</small><strong>${Math.round(index)}</strong><span class="summary-detail">${phaseFor(index).label}</span><div class="position-meter" style="--position:${index}%"></div></article>
    <article class="signal-summary-item"><small>BTC price</small><strong>${formatUsd(price)}</strong>${sparklineSvg(primaryValues(priceSeries).slice(-60))}</article>
    <article class="signal-summary-item"><small>Consensus</small><strong>${bullish}</strong><span class="summary-detail">/ ${signals.length} bullish</span><div class="metric-bar"><span style="width:${counts.bottom / signals.length * 100}%"></span><span style="width:${counts.bearish / signals.length * 100}%"></span><span style="width:${counts.bullish / signals.length * 100}%"></span><span style="width:${counts.top / signals.length * 100}%"></span></div></article>
    <article class="signal-summary-item"><small>30D momentum</small><strong>${rising}</strong><span class="summary-detail">/ ${signals.length} rising</span><div class="metric-bar"><span style="width:${rising / signals.length * 100}%; background:var(--green)"></span><span style="width:${(signals.length - rising) / signals.length * 100}%; background:var(--surface-muted)"></span></div></article>
  `;
}

function renderSignalTable(signals) {
  const body = document.querySelector("#signal-table-body");
  const count = document.querySelector("#signal-table-count");
  count.textContent = `${signals.length} signal${signals.length === 1 ? "" : "s"}`;
  body.innerHTML = signals.map((signal) => {
    const deltas = [7, 30, 90, 365].map((days) => signalDelta(signal, days));
    return `
      <tr data-chart-id="${escapeHtml(signal.chartId)}" tabindex="0">
        <td><strong>${escapeHtml(signal.label)}</strong><span class="summary-detail">${escapeHtml(signal.category)}</span></td>
        <td class="signal-value" title="${escapeHtml(formatSignalRaw(signal))}">${Math.round(signal.score)}</td>
        ${deltas.map((delta) => `<td class="signal-delta ${delta > 0 ? "positive" : delta < 0 ? "negative" : ""}">${signedScore(delta)}</td>`).join("")}
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
  const movers = [...signals].map((signal) => ({ signal, delta: signalDelta(signal, 30) })).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 5);
  target.innerHTML = `
    <article class="insight-card"><h3>Category pulse</h3><div class="insight-list">${categoryRows.map((item) => `<div class="insight-row"><span>${escapeHtml(item.category)} · ${item.count} signals</span><strong>${Math.round(item.score)} ${phaseFor(item.score).label}</strong></div>`).join("")}</div></article>
    <article class="insight-card"><h3>30D movers</h3><div class="insight-list">${movers.map(({ signal, delta }) => `<div class="insight-row"><span>${escapeHtml(signal.label)}</span><strong class="${delta < 0 ? "negative" : ""}">${signedScore(delta)}</strong></div>`).join("")}</div></article>
  `;
}

async function renderAlertsPage() {
  appState.signals = await buildSignals();
  const select = document.querySelector("#alert-signal");
  select.innerHTML = appState.signals.map((signal) => `<option value="${escapeHtml(signal.id)}">${escapeHtml(signal.label)}</option>`).join("");
  const requestedSignal = initialParams.get("signal");
  if (requestedSignal && appState.signals.some((signal) => signal.id === requestedSignal)) select.value = requestedSignal;

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
}

function saveAlertFromForm(event) {
  event.preventDefault();
  const signalId = document.querySelector("#alert-signal").value;
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
  writeAlertRules(rules);
  resetAlertForm();
  renderAlertRules();
}

function resetAlertForm() {
  const form = document.querySelector("#alert-form");
  form.reset();
  const requestedSignal = initialParams.get("signal");
  if (requestedSignal && appState.signals.some((signal) => signal.id === requestedSignal)) document.querySelector("#alert-signal").value = requestedSignal;
  document.querySelector("#alert-threshold").value = "75";
  updateAlertPreview();
}

function updateAlertPreview() {
  const signal = appState.signals.find((item) => item.id === document.querySelector("#alert-signal")?.value) || appState.signals[0];
  if (!signal) return;
  const operator = document.querySelector("#alert-operator").value.replaceAll("-", " ");
  const threshold = clamp(Number(document.querySelector("#alert-threshold").value), 0, 100);
  const preview = document.querySelector("#alert-preview");
  preview.innerHTML = `<strong>${escapeHtml(signal.label)}</strong> is currently ${Math.round(signal.score)} (${signal.phase.label}). This rule will trigger when its cycle score ${escapeHtml(operator)} ${threshold}.`;
}

function renderAlertRules() {
  const rules = readAlertRules();
  const list = document.querySelector("#alert-list");
  const evaluated = rules.map((rule) => ({ ...rule, triggered: evaluateAlert(rule) }));
  const active = rules.filter((rule) => rule.enabled).length;
  const triggered = evaluated.filter((rule) => rule.enabled && rule.triggered).length;
  document.querySelector("#alert-count").textContent = `${rules.length} alert${rules.length === 1 ? "" : "s"}`;
  document.querySelector("#alert-overview").innerHTML = `
    <article class="alert-overview-item"><div><small>Active rules</small><strong>${active}</strong></div><span class="overview-icon" aria-hidden="true">♧</span></article>
    <article class="alert-overview-item"><div><small>Conditions met</small><strong>${triggered}</strong></div><span class="overview-icon" aria-hidden="true">●</span></article>
    <article class="alert-overview-item"><div><small>Last evaluated</small><strong>${shortTime(new Date())}</strong></div><span class="overview-icon" aria-hidden="true">↻</span></article>
  `;

  if (!rules.length) {
    list.innerHTML = `<div class="alert-empty"><div><strong>No alert rules yet</strong><p>Create a rule to watch one of the normalized cycle signals. Rules stay private in this browser.</p></div></div>`;
    return;
  }

  list.innerHTML = evaluated.map((rule) => {
    const signal = appState.signals.find((item) => item.id === rule.signalId);
    const title = rule.label || signal?.label || "Unknown signal";
    return `
      <article class="alert-rule ${rule.triggered && rule.enabled ? "triggered" : ""}">
        <span class="alert-rule-status" title="${rule.triggered ? "Condition met" : "Watching"}"></span>
        <div class="alert-rule-copy"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(alertRuleText(rule, signal))}</span></div>
        <div class="alert-rule-actions">
          <label class="switch-control" title="Enable or pause alert"><input type="checkbox" data-alert-toggle="${escapeHtml(rule.id)}" ${rule.enabled ? "checked" : ""}><span class="switch-track"></span></label>
          <button type="button" data-alert-delete="${escapeHtml(rule.id)}" aria-label="Delete ${escapeHtml(title)}">Delete</button>
        </div>
      </article>
    `;
  }).join("");

  list.querySelectorAll("[data-alert-toggle]").forEach((control) => {
    control.addEventListener("change", () => {
      const next = readAlertRules().map((rule) => rule.id === control.dataset.alertToggle ? { ...rule, enabled: control.checked } : rule);
      writeAlertRules(next);
      renderAlertRules();
    });
  });
  list.querySelectorAll("[data-alert-delete]").forEach((button) => {
    button.addEventListener("click", () => {
      writeAlertRules(readAlertRules().filter((rule) => rule.id !== button.dataset.alertDelete));
      renderAlertRules();
    });
  });
}

function evaluateAlert(rule) {
  if (!rule.enabled) return false;
  const signal = appState.signals.find((item) => item.id === rule.signalId);
  if (!signal) return false;
  const current = signal.score;
  const previous = scoreAtDaysAgo(signal, 1);
  if (rule.operator === "above") return current > rule.threshold;
  if (rule.operator === "below") return current < rule.threshold;
  if (rule.operator === "crosses-above") return previous <= rule.threshold && current > rule.threshold;
  if (rule.operator === "crosses-below") return previous >= rule.threshold && current < rule.threshold;
  return false;
}

function alertRuleText(rule, signal) {
  const current = signal ? Math.round(signal.score) : "—";
  return `Score ${String(rule.operator).replaceAll("-", " ")} ${rule.threshold} · now ${current} · ${rule.cadence === "once" ? "once" : "each refresh"}`;
}

function readAlertRules() {
  try {
    const value = JSON.parse(localStorage.getItem("fintech-alerts-v1") || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function writeAlertRules(rules) {
  localStorage.setItem("fintech-alerts-v1", JSON.stringify(rules));
}

function signalDelta(signal, days) {
  return signal.score - scoreAtDaysAgo(signal, days);
}

function scoreAtDaysAgo(signal, days) {
  const points = signal.points;
  if (!points.length) return 0;
  const latestDate = new Date(last(points).date);
  const target = new Date(latestDate);
  target.setUTCDate(target.getUTCDate() - days);
  for (let index = points.length - 1; index >= 0; index -= 1) {
    if (new Date(points[index].date) <= target) return points[index].score;
  }
  return points[0].score;
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
  const value = Number(signal.rawValue);
  if (!Number.isFinite(value)) return "Unavailable";
  if (["trend", "pi-cycle"].includes(signal.id)) return `${value.toFixed(2)}x`;
  if (signal.id === "bollinger") return `${(value * 100).toFixed(0)}% of band`;
  if (signal.id === "ath-age") return `${Math.round(value)} days`;
  if (["drawdown", "volatility", "sharpe"].includes(signal.id)) return `${value.toFixed(1)}%`;
  if (signal.id === "fees") return `${value.toFixed(2)} sat/vB`;
  return value.toFixed(Math.abs(value) >= 100 ? 0 : 2);
}

function signedScore(value) {
  const rounded = Math.round(value);
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

function formatMetricValue(name, value) {
  const number = toFiniteNumber(value);
  if (!Number.isFinite(number)) return "—";
  const label = String(name || "").toLowerCase();
  if (label.includes("price") || label.includes("usd") || label.includes("cost basis")) return formatUsd(number);
  if (label.includes("percent") || label.includes("return") || label.includes("drawdown") || label.includes("volatility") || label.includes("share")) return `${number.toFixed(1)}%`;
  if (Math.abs(number) >= 1000) return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(number);
  return number.toFixed(Math.abs(number) < 10 ? 2 : 1);
}

function shortDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value ?? "");
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "2-digit", timeZone: "UTC" }).format(date);
}

function shortTime(date) {
  return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }).format(date);
}

async function buildSignals() {
  const results = await Promise.all(SIGNAL_DEFINITIONS.map(async (definition) => {
    try {
      const payload = await getPayload(definition.chartId);
      const points = definition.build
        ? definition.build(payload)
        : seriesPoints(payload.series[definition.series || 0], definition.invert ? -1 : 1);
      const valid = points.filter((point) => Number.isFinite(point.value));
      const values = valid.map((point) => point.value);
      const low = quantile(values, 0.05);
      const high = quantile(values, 0.95);
      const scored = valid.map((point) => ({ ...point, score: normalizedScore(point.value, low, high) }));
      const current = last(scored);
      const sourceSeries = payload.series[definition.series || 0];
      return {
        ...definition,
        payload,
        points: scored,
        score: current?.score || 0,
        rawValue: definition.invert ? Math.abs(current?.value) : current?.value,
        unitName: sourceSeries?.name || definition.label,
        date: current?.date,
        phase: phaseFor(current?.score || 0),
      };
    } catch (error) {
      console.warn(`Signal unavailable: ${definition.id}`, error);
      return null;
    }
  }));
  return results.filter(Boolean);
}

function renderSignalHeatmap(target, signals, columns = 56) {
  if (!target) return;
  target.classList.remove("loading-block");
  if (!signals.length) {
    target.innerHTML = `<p class="empty-state">No signal history matches these filters.</p>`;
    return;
  }
  const sampled = signals.map((signal) => sampleEvenly(signal.points, columns));
  const labels = sampled[0] || [];
  const rows = signals.map((signal, rowIndex) => {
    const cells = sampled[rowIndex].map((point) => `
      <span class="heatmap-cell ${phaseFor(point.score).className}" title="${escapeHtml(signal.label)} · ${escapeHtml(formatDate(new Date(point.date)))} · ${Math.round(point.score)}"></span>
    `).join("");
    return `<span class="heatmap-label" title="${escapeHtml(signal.label)}">${escapeHtml(signal.label)}</span>${cells}`;
  }).join("");
  const yearRow = labels.map((point, index) => {
    const show = index % 8 === 0;
    return `<span class="heatmap-year">${show ? new Date(point.date).getUTCFullYear() : ""}</span>`;
  }).join("");
  target.innerHTML = `<div class="heatmap-table" style="grid-template-columns:minmax(150px, 190px) repeat(${columns}, minmax(7px, 1fr))">${rows}<span></span>${yearRow}</div>`;
}

function renderPlot(target, payload, options = {}) {
  if (!window.Plotly || !target) return;
  const colorMap = {
    "#f5c84b": "#c85f3c",
    "#55d6ff": "#2863a7",
    "#3ce38a": "#16844d",
    "#ff5f63": "#c91f50",
    "#ff9f43": "#d98945",
    "#ff5ccd": "#9d4c83",
  };
  const sourceSeries = options.series || payload.series;
  const traces = sourceSeries.slice(0, options.compact ? 4 : sourceSeries.length).map((series) => {
    const { axis, ...trace } = series;
    const next = { ...trace, yaxis: axis || trace.yaxis || "y" };
    if (options.maxPoints && Array.isArray(trace.x)) {
      const step = Math.max(1, Math.ceil(trace.x.length / options.maxPoints));
      ["x", "y", "open", "high", "low", "close", "text"].forEach((key) => {
        if (Array.isArray(next[key])) next[key] = next[key].filter((_, index) => index % step === 0 || index === next[key].length - 1);
      });
    }
    if (next.line?.color) next.line = { ...next.line, color: colorMap[next.line.color] || next.line.color };
    if (next.marker?.color && typeof next.marker.color === "string") next.marker = { ...next.marker, color: colorMap[next.marker.color] || next.marker.color };
    next.hovertemplate = next.hovertemplate || "%{x}<br>%{y}<extra>%{fullData.name}</extra>";
    return next;
  });
  const dark = document.documentElement.dataset.theme === "dark";
  const baseLayout = {
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, sans-serif", color: dark ? "#aaa69d" : "#6f6d67", size: 11 },
    margin: options.compact ? { l: 56, r: 28, t: 18, b: 42 } : { l: 68, r: 44, t: 28, b: 70 },
    hovermode: "x unified",
    showlegend: true,
    legend: { orientation: "h", x: 0, y: 1.08, font: { size: 10 } },
    xaxis: { gridcolor: dark ? "#34332e" : "#e8e6df", zerolinecolor: dark ? "#4b4941" : "#c9c6be", rangeslider: { visible: false } },
    yaxis: { gridcolor: dark ? "#34332e" : "#e8e6df", zerolinecolor: dark ? "#4b4941" : "#c9c6be", automargin: true },
  };
  const layout = deepMerge(baseLayout, payload.layout || {});
  if (options.layout) Object.assign(layout, deepMerge(layout, options.layout));
  if (options.compact) {
    delete layout.xaxis?.rangeselector;
    if (layout.legend) layout.legend.y = 1.12;
  }
  if (options.grid === false) {
    Object.keys(layout).filter((key) => key.startsWith("xaxis") || key.startsWith("yaxis")).forEach((key) => {
      layout[key].gridcolor = "rgba(0,0,0,0)";
    });
  }
  return Plotly.newPlot(target, traces, layout, {
    responsive: true,
    displaylogo: false,
    displayModeBar: !options.compact,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  });
}

function ratioSeries(numeratorIndex, denominatorIndex) {
  return (payload) => {
    const numerator = payload.series[numeratorIndex];
    const denominator = payload.series[denominatorIndex];
    return numerator.x.map((date, index) => ({
      date,
      value: toFiniteNumber(numerator.y[index]) / toFiniteNumber(denominator.y[index]),
    }));
  };
}

function bandPositionSeries(lowerIndex, upperIndex, priceIndex) {
  return (payload) => {
    const lower = payload.series[lowerIndex];
    const upper = payload.series[upperIndex];
    const price = payload.series[priceIndex];
    return price.x.map((date, index) => ({
      date,
      value: (toFiniteNumber(price.y[index]) - toFiniteNumber(lower.y[index])) / (toFiniteNumber(upper.y[index]) - toFiniteNumber(lower.y[index])),
    }));
  };
}

function seriesPoints(series, multiplier = 1) {
  return (series?.x || []).map((date, index) => ({ date, value: toFiniteNumber(series.y[index]) * multiplier }));
}

function sampleEvenly(values, count) {
  if (values.length <= count) return values;
  return Array.from({ length: count }, (_, index) => values[Math.round(index * (values.length - 1) / (count - 1))]);
}

function normalizedScore(value, low, high) {
  if (!Number.isFinite(value) || !Number.isFinite(low) || !Number.isFinite(high) || low === high) return 50;
  return clamp(((value - low) / (high - low)) * 100, 0, 100);
}

function phaseFor(score) {
  if (score < 25) return { key: "bottom", label: "Bottom", className: "phase-bottom" };
  if (score < 50) return { key: "bearish", label: "Bearish", className: "phase-bearish" };
  if (score < 75) return { key: "bullish", label: "Bullish", className: "phase-bullish" };
  return { key: "top", label: "Top", className: "phase-top" };
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
  const promise = fetchJson(assetPath(chart.data_path));
  appState.payloadCache.set(chartId, promise);
  return promise;
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
  return value === null || value === undefined || value === "" ? NaN : Number(value);
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
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
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
