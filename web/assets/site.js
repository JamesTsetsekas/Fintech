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
  "pb-various",
  "ohlc",
  "nupl",
  "pi-cycle-top",
  "mvrv-z-score",
  "circulating-supply",
  "difficulty",
  "pb-realized-prices",
];

const SIGNAL_DEFINITIONS = [
  { id: "nupl", chartId: "nupl", label: "NUPL (Net Unrealized Profit Loss)", category: "Valuation", seriesKey: "nupl" },
  { id: "utxos-profit", chartId: "percent-utxos-in-profit", label: "UTXOs in Profit (%)", category: "Profitability", seriesKey: "Percent UTXOs in profit" },
  { id: "thermocap", chartId: "market-cap-to-thermocap-ratio", label: "Market Cap To Thermocap Ratio", category: "Valuation", seriesKey: "Market cap to thermocap ratio" },
  { id: "sts-nupl", chartId: "sts-nupl", label: "NUPL Short Term Supply (STS)", category: "Cohorts", seriesKey: "sts_nupl" },
  { id: "lts-nupl", chartId: "lts-nupl", label: "NUPL Long Term Supply (LTS)", category: "Cohorts", seriesKey: "lts_nupl" },
  { id: "realized-price-sts", chartId: "realized-price-sts", label: "Realized Price - Short Term Supply (STS)", category: "Cost Basis", seriesKey: "Realized price STS", build: ratioByKeys("price", "Realized price STS") },
  { id: "balanced-price", chartId: "balanced-price", label: "Balanced Price", category: "Cost Basis", seriesKey: "balanced_price", build: ratioByKeys("price", "balanced_price") },
  { id: "sth-mvrv", chartId: "sth-mvrv", label: "MVRV Short Term Supply", category: "Cohorts", seriesKey: "sth_mvrv" },
  { id: "realized-price", chartId: "realized-price", label: "Realized Price", category: "Cost Basis", seriesKey: "realized_price", build: ratioByKeys("price", "realized_price") },
  { id: "mvrv", chartId: "mvrv", label: "MVRV (Market Value to Realized Value Ratio)", category: "Valuation", seriesKey: "mvrv" },
  { id: "adjusted-mvrv", chartId: "adjusted-mvrv", label: "MVRV Adjusted Ratio", category: "Valuation", seriesKey: "adjusted_mvrv" },
  { id: "supply-profit", chartId: "percent-supply-in-profit", label: "Supply in Profit (%)", category: "Profitability", seriesKey: "Percent supply in profit" },
  { id: "top-price", chartId: "top-price", label: "Top Price", category: "Cost Basis", seriesKey: "top_price", build: ratioByKeys("price", "top_price") },
  { id: "mvrv-z", chartId: "mvrv-z-score", label: "MVRV Z-Score", category: "Valuation", seriesKey: "mvrv_z_score" },
  { id: "delta-price", chartId: "delta-price", label: "Delta Price", category: "Cost Basis", seriesKey: "delta_price", build: ratioByKeys("price", "delta_price") },
  { id: "lth-mvrv", chartId: "lth-mvrv", label: "MVRV Long Term Supply", category: "Cohorts", seriesKey: "lth_mvrv" },
  { id: "realized-price-lts", chartId: "realized-price-lts", label: "Realized Price - Long Term Supply (LTS)", category: "Cost Basis", seriesKey: "Realized price LTS", build: ratioByKeys("price", "Realized price LTS") },
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

const REFERENCE_SIGNAL_IDS = [
  "nupl",
  "utxos-profit",
  "thermocap",
  "sts-nupl",
  "lts-nupl",
  "realized-price-sts",
  "balanced-price",
  "sth-mvrv",
  "realized-price",
  "mvrv",
  "adjusted-mvrv",
  "supply-profit",
  "top-price",
  "mvrv-z",
  "delta-price",
  "lth-mvrv",
  "realized-price-lts",
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
  const dashboardSignals = buildDashboardSignalSet(appState.signals);
  await Promise.all([
    renderMetricRibbon(dashboardSignals.slice(1)),
    renderSignalHeatmap(document.querySelector("#dashboard-signal-heatmap"), dashboardSignals, 92, { startDate: "2012-01-01" }),
    renderDashboardCharts(),
  ]);
  const updated = new Date(appState.manifest.generated_at);
  document.querySelector("#dashboard-updated").textContent = `Updated ${formatDate(updated)}`;
  document.addEventListener("fintech-theme-change", renderDashboardCharts);
}

async function renderMetricRibbon(referenceSignals = appState.signals) {
  const ribbon = document.querySelector("#metric-ribbon");
  const trend = await getPayload("200-dma-200-wma");
  const prices = numericSeries(trend.series[0]);
  const latestPrice = last(prices);
  const monthAgoPrice = prices[Math.max(0, prices.length - 31)];
  const change30 = ((latestPrice / monthAgoPrice) - 1) * 100;
  const ma200 = last(numericSeries(trend.series[1]));
  const distance = ((latestPrice / ma200) - 1) * 100;
  const supplySignal = referenceSignals.find((signal) => signal.id === "supply-profit");
  const supplyValue = Number(supplySignal?.rawValue);
  const supplyChange30 = rawSignalDelta(supplySignal, 30);
  const supplyHistory = recentSignalValues(supplySignal, 45);
  const cycleIndex = average(referenceSignals.map((signal) => signal.score));
  const bullishCount = referenceSignals.filter((signal) => signal.score >= 50).length;
  const phases = phaseCounts(referenceSignals);
  const phase = phaseFor(cycleIndex);
  const recentPrice = trend.series[0].y.slice(-45);
  const recentAverage = trend.series[1].y.slice(-45);
  const recentRatios = recentPrice.map((value, index) => Number(value) / Number(recentAverage[index]));

  ribbon.innerHTML = `
    <article class="terminal-metric has-sparkline">
      <span class="terminal-metric-label">Bitcoin price</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${formatUsd(latestPrice)}</strong>
        <span class="terminal-metric-change ${change30 < 0 ? "negative" : ""}">${change30 < 0 ? "↘" : "↗"} ${signed(change30)} 30d</span>
      </div>
      ${sparklineSvg(prices.slice(-45))}
    </article>
    <article class="terminal-metric has-sparkline">
      <span class="terminal-metric-label">Supply in profit</span>
      <div class="terminal-metric-row">
        <strong class="terminal-metric-value">${Number.isFinite(supplyValue) ? `${supplyValue.toFixed(1)}%` : signed(distance)}</strong>
        <span class="terminal-metric-change ${supplyChange30 < 0 ? "negative" : ""}">${Number.isFinite(supplyChange30) ? `${supplyChange30 < 0 ? "↘" : "↗"} ${supplyChange30 >= 0 ? "+" : ""}${supplyChange30.toFixed(1)}pp 30d` : (distance >= 0 ? "above trend" : "below trend")}</span>
      </div>
      ${sparklineSvg(supplyHistory.length ? supplyHistory : recentRatios)}
    </article>
    <article class="terminal-metric has-sparkline wide-only-metric">
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
        <span class="terminal-metric-change">/ ${referenceSignals.length} bullish</span>
      </div>
      <div class="metric-bar" aria-label="${phaseCountLabel(phases)}">
        <span style="width:${phases.bottom / referenceSignals.length * 100}%"></span>
        <span style="width:${phases.bearish / referenceSignals.length * 100}%"></span>
        <span style="width:${phases.bullish / referenceSignals.length * 100}%"></span>
        <span style="width:${phases.top / referenceSignals.length * 100}%"></span>
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
    const href = `charts/?chart=${encodeURIComponent(id)}`;
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
    const payload = await getPayload(id);
    const target = document.querySelector(`#dashboard-plot-${CSS.escape(id)}`);
    target.classList.remove("loading-block");
    const showHalvings = payload.show_halvings_default || ["pi-cycle-top", "200-dma-200-wma"].includes(payload.id);
    renderPlot(target, payload, {
      compact: true,
      maxPoints: 600,
      layout: showHalvings ? halvingOverlayLayout(payload) : undefined,
    });
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
    appState.chartOptions.halvings = Boolean(
      payload.show_halvings_default || ["pi-cycle-top", "200-dma-200-wma"].includes(payload.id),
    );
    appState.chartOptions.scale = payload.default_scale || payload.layout?.yaxis?.type || "linear";
    document.querySelector('[data-chart-action="halvings"]')?.classList.toggle("active", appState.chartOptions.halvings);
    updateChartControls(payload);
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

function updateChartControls(payload) {
  const hasNumericLine = payload.series.some((series) => (
    series.type === "scatter"
    && Array.isArray(series.y)
    && series.y.some((value) => Number.isFinite(toFiniteNumber(value)))
  ));
  const movingAverage = document.querySelector('[data-chart-action="moving-average"]');
  const halvings = document.querySelector('[data-chart-action="halvings"]');
  const rangeOptions = document.querySelector(".range-options");
  if (movingAverage) movingAverage.disabled = !hasNumericLine;
  if (halvings) halvings.disabled = pageConfig.market !== "bitcoin" || payload.x_value_type !== "date";
  if (rangeOptions) rangeOptions.hidden = payload.show_range_selector === false || payload.x_value_type !== "date";
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
  if (summary) setChartSummary(chart.description);
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
  if (payload.allow_scale_toggle && appState.chartOptions.scale && payload.layout?.yaxis !== undefined) {
    (payload.scale_axes || ["y"]).forEach((axis) => {
      const key = axis === "y" ? "yaxis" : `yaxis${axis.replace("y", "")}`;
      layout[key] = { ...(layout[key] || {}), type: appState.chartOptions.scale };
    });
  }
  await renderPlot(target, payload, { series, layout, grid: appState.chartOptions.grid, maxPoints: 2200 });
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
  return appState.chartOptions.halvings && payload.x_value_type !== "number"
    ? halvingOverlayLayout(payload)
    : {};
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
}

function renderChartDetails(payload) {
  const seriesList = document.querySelector("#series-list");
  const performanceList = document.querySelector("#performance-list");
  const latestDate = payload.x_value_type === "date"
    ? payload.series.find((series) => Array.isArray(series.x))?.x?.at(-1)
    : null;
  document.querySelector("#series-date").textContent = latestDate ? shortDate(latestDate) : "Latest";
  setChartSummary(payload.summary_text || appState.currentChart.description);

  seriesList.innerHTML = payload.series.slice(0, 8).map((series, index) => {
    const values = primaryValues(series);
    const value = last(values);
    return `
      <div class="series-row" data-series-index="${index}">
        <span class="series-dot" style="background:${seriesColor(series, index)}"></span>
        <span class="series-name" title="${escapeHtml(series.name)}">${escapeHtml(series.name)}</span>
        <strong class="series-value">${formatMetricValue(series.name, value)}</strong>
      </div>
    `;
  }).join("");

  const base = payload.x_value_type === "date"
    ? payload.series.find((series) => series.type !== "heatmap" && primaryValues(series).length > 2)
    : null;
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

function setChartSummary(text) {
  const summary = document.querySelector("#chart-summary");
  if (!summary) return;
  summary.textContent = text || "";
}

function renderDataSheet(payload) {
  const sheet = document.querySelector("#data-sheet");
  const horizontal = payload.series.filter((series) => (
    series.orientation === "h"
    && Array.isArray(series.x)
    && Array.isArray(series.y)
    && series.x.length === series.y.length
  ));
  if (horizontal.length) {
    const base = horizontal[0];
    const headers = horizontal.map((series) => `<th>${escapeHtml(series.name)}</th>`).join("");
    const rows = base.y.map((label, index) => {
      const values = horizontal.map((series) => `<td>${escapeHtml(formatMetricValue(series.name, series.x[index]))}</td>`).join("");
      return `<tr><td>${escapeHtml(String(label))}</td>${values}</tr>`;
    }).reverse().join("");
    sheet.innerHTML = `<table><thead><tr><th>Category</th>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
    return;
  }
  const compatible = payload.series.filter((series) => (
    series.type !== "heatmap"
    && Array.isArray(series.x)
    && Array.isArray(series.y)
    && series.x.length === series.y.length
  ));
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
    const coordinate = payload.x_value_type === "date" ? shortDate(date) : String(date);
    return `<tr><td>${escapeHtml(coordinate)}</td>${values}</tr>`;
  }).reverse().join("");
  const coordinateLabel = payload.x_value_type === "date" ? "Date" : "X";
  sheet.innerHTML = `<table><thead><tr><th>${coordinateLabel}</th>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
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
  renderTerminalPlot();
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
  if (series?.type === "heatmap") return [];
  if (series?.orientation === "h" && Array.isArray(series.x)) {
    return series.x.map(toFiniteNumber).filter(Number.isFinite);
  }
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
  const legacyMap = { "#f5c84b": "#c85f3c", "#55d6ff": "#2863a7", "#3ce38a": "#16844d", "#ff5f63": "#c91f50", "#ff9f43": "#d98945", "#ff5ccd": "#9d4c83", "#eef3f8": document.documentElement.dataset.theme === "dark" ? "#eef3f8" : "#393732" };
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
      const sourceSeries = signalSourceSeries(payload, definition);
      const points = definition.build
        ? definition.build(payload)
        : seriesPoints(sourceSeries, definition.invert ? -1 : 1);
      const valid = points.filter((point) => Number.isFinite(point.value));
      const values = valid.map((point) => point.value);
      const low = quantile(values, 0.05);
      const high = quantile(values, 0.95);
      const scored = valid.map((point) => ({ ...point, score: normalizedScore(point.value, low, high) }));
      const current = last(scored);
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

function signalSourceSeries(payload, definition) {
  if (definition.seriesKey) {
    const matching = payload.series.find((series) => series.source_key === definition.seriesKey);
    if (matching) return matching;
  }
  return payload.series[definition.series || 0];
}

function buildDashboardSignalSet(signals) {
  const selected = REFERENCE_SIGNAL_IDS.map((id) => signals.find((signal) => signal.id === id)).filter(Boolean);
  if (!selected.length) return signals;
  const dateScores = new Map();
  selected.forEach((signal) => {
    signal.points.forEach((point) => {
      const values = dateScores.get(point.date) || [];
      values.push(point.score);
      dateScores.set(point.date, values);
    });
  });
  const points = [...dateScores.entries()]
    .map(([date, scores]) => ({ date, value: average(scores), score: average(scores) }))
    .sort((a, b) => new Date(a.date) - new Date(b.date));
  const score = last(points)?.score || 0;
  return [{
    id: "cycle-index",
    chartId: "cycle-phase-dashboard",
    label: "Cycle Index",
    category: "Composite",
    points,
    score,
    rawValue: score,
    phase: phaseFor(score),
  }, ...selected];
}

function rawSignalDelta(signal, days) {
  if (!signal?.points?.length) return NaN;
  const latest = last(signal.points);
  const target = new Date(latest.date);
  target.setUTCDate(target.getUTCDate() - days);
  let previous = signal.points[0];
  for (let index = signal.points.length - 1; index >= 0; index -= 1) {
    if (new Date(signal.points[index].date) <= target) {
      previous = signal.points[index];
      break;
    }
  }
  return Number(latest.value) - Number(previous.value);
}

function recentSignalValues(signal, days) {
  if (!signal?.points?.length) return [];
  const latest = new Date(last(signal.points).date);
  const cutoff = new Date(latest);
  cutoff.setUTCDate(cutoff.getUTCDate() - days);
  return signal.points
    .filter((point) => new Date(point.date) >= cutoff)
    .map((point) => Number(point.value))
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
  const visibleSignals = signals.map((signal) => ({
    ...signal,
    points: signal.points.filter((point) => new Date(point.date).getTime() >= cutoff),
  }));
  const sampled = visibleSignals.map((signal) => sampleEvenly(signal.points, columns));
  const labels = sampled[0] || [];
  const rows = visibleSignals.map((signal, rowIndex) => {
    const cells = sampled[rowIndex].map((point) => `
      <span class="heatmap-cell ${phaseFor(point.score).className}" title="${escapeHtml(signal.label)} · ${escapeHtml(formatDate(new Date(point.date)))} · ${Math.round(point.score)}"></span>
    `).join("");
    return `<span class="heatmap-label" title="${escapeHtml(signal.label)}">${escapeHtml(signal.label)}</span>${cells}`;
  }).join("");
  const yearRow = labels.map((point, index) => {
    const show = index % 8 === 0;
    return `<span class="heatmap-year">${show ? new Date(point.date).getUTCFullYear() : ""}</span>`;
  }).join("");
  target.innerHTML = `<div class="heatmap-table" style="--heatmap-columns:${columns}">${rows}<span></span>${yearRow}</div>`;
}

function renderPlot(target, payload, options = {}) {
  if (!window.Plotly || !target) return;
  cleanupChartInteractions(target);
  const dark = document.documentElement.dataset.theme === "dark";
  const colorMap = {
    "#f5c84b": "#c85f3c",
    "#55d6ff": "#2863a7",
    "#3ce38a": "#16844d",
    "#ff5f63": "#c91f50",
    "#ff9f43": "#d98945",
    "#ff5ccd": "#9d4c83",
    "#eef3f8": dark ? "#eef3f8" : "#393732",
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
  const sourceSeries = options.series || payload.series;
  const displaySeries = sourceSeries
    .slice(0, options.compact ? 4 : sourceSeries.length)
    .flatMap(expandGradientLine);
  const traces = displaySeries.map((series) => {
    const { axis, ...trace } = series;
    const next = { ...trace, yaxis: axis || trace.yaxis || "y" };
    if (options.maxPoints && Array.isArray(trace.x) && !trace.x.includes(null)) {
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
    else next.hovertemplate = next.hovertemplate || "%{x}<br>%{y}<extra>%{fullData.name}</extra>";
    if (next.hoverinfo !== "skip" && !options.compact
        && ["scatter", "scattergl"].includes(next.type) && Array.isArray(next.y)) {
      next.hovertemplate = premiumHoverTemplate(next);
    }
    return next;
  });
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
  let layout = deepMerge(baseLayout, payload.layout || {});
  if (options.layout) Object.assign(layout, deepMerge(layout, options.layout));
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
    if (!axis || axis.type === "category" || options.compact) return;
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
  return Plotly.newPlot(target, traces, layout, {
    responsive: true,
    displaylogo: false,
    displayModeBar: !options.compact,
    scrollZoom: !options.compact,
    doubleClick: "reset+autosize",
    showAxisDragHandles: false,
    showAxisRangeEntryBoxes: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  }).then((plot) => {
    if (!options.compact) {
      cleanupChartInteractions(target);
      installPriceScaleControls(target);
      installAxisBadges(target);
      bindChartHoverDetails(target, payload);
    }
    return plot;
  });
}

function cleanupChartInteractions(target) {
  if (typeof target?._fintechChartCleanup === "function") target._fintechChartCleanup();
  if (target) target._fintechChartCleanup = null;
}

function installPriceScaleControls(target) {
  const fullLayout = target?._fullLayout;
  if (!fullLayout?._size) return;
  target.classList.add("premium-chart");
  const cleanups = [];
  const resizeObserver = new ResizeObserver(() => positionScaleRails(target));
  resizeObserver.observe(target);
  cleanups.push(() => resizeObserver.disconnect());

  [
    { axisName: "yaxis", side: "left" },
    { axisName: "yaxis2", side: "right" },
  ].forEach(({ axisName, side }) => {
    const axis = target._fullLayout?.[axisName];
    if (!axis || axis.type === "category" || axis.fixedrange) return;
    const rail = document.createElement("div");
    rail.className = `chart-scale-rail chart-scale-rail-${side}`;
    rail.dataset.axis = axisName;
    rail.setAttribute("aria-hidden", "true");
    rail.title = "Drag to scale price · double-click to reset";
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
    const side = rail.classList.contains("chart-scale-rail-right") ? "right" : "left";
    rail.style.top = `${size.t}px`;
    rail.style.height = `${size.h}px`;
    rail.style.width = `${Math.max(28, side === "left" ? size.l : size.r)}px`;
    rail.style[side] = "0";
  });
}

function installAxisBadges(target) {
  const fullLayout = target?._fullLayout;
  if (!fullLayout?._size || !fullLayout.xaxis || !fullLayout.yaxis
      || fullLayout.xaxis.type === "category" || fullLayout.yaxis.type === "category") return;
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
    const plotX = event.clientX - bounds.left - size.l;
    const plotY = event.clientY - bounds.top - size.t;
    if (plotX < 0 || plotX > size.w || plotY < 0 || plotY > size.h) {
      hideBadges();
      return;
    }
    const xValue = layout.xaxis?.p2d?.(plotX);
    const yValue = layout.yaxis?.p2d?.(plotY);
    xBadge.textContent = layout.xaxis.type === "date"
      ? formatCrosshairDate(xValue)
      : formatCrosshairValue(xValue, layout.xaxis);
    yBadge.textContent = formatCrosshairValue(yValue, layout.yaxis);
    xBadge.style.left = `${size.l + plotX}px`;
    xBadge.style.top = `${size.t + size.h + 8}px`;
    yBadge.style.left = `${size.l}px`;
    yBadge.style.top = `${size.t + plotY}px`;
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
  const absolute = Math.abs(number);
  let formatted;
  if (absolute >= 1e9) formatted = `${(number / 1e9).toFixed(absolute >= 1e10 ? 0 : 1)}B`;
  else if (absolute >= 1e6) formatted = `${(number / 1e6).toFixed(absolute >= 1e7 ? 0 : 1)}M`;
  else if (absolute >= 1e3) formatted = `${(number / 1e3).toFixed(absolute >= 1e4 ? 0 : 1)}K`;
  else if (absolute >= 100) formatted = number.toFixed(0);
  else if (absolute >= 10) formatted = number.toFixed(1);
  else if (absolute >= 1) formatted = number.toFixed(2);
  else formatted = number.toPrecision(3);
  return `${formatted}${axis?.ticksuffix || ""}`;
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

function premiumHoverTemplate(series) {
  const label = String(series.name || "").toLowerCase();
  let valueFormat = ",.3~g";
  let suffix = "";
  if (label.includes("price") || label.includes("usd") || label.includes("cost basis")) valueFormat = "$,.2f";
  else if (label.includes("percent") || label.includes("return") || label.includes("drawdown") || label.includes("volatility")) {
    valueFormat = ",.2f";
    suffix = "%";
  }
  return `%{y:${valueFormat}}${suffix}<extra>%{fullData.name}</extra>`;
}

function updateHoveredSeriesDetails(payload, xValue) {
  const dateNode = document.querySelector("#series-date");
  const referenceSeries = payload.series.find((series) => Array.isArray(series.x) && series.x.length);
  const referenceIndex = xValue === null ? -1 : nearestSeriesIndex(referenceSeries, xValue);
  const referenceDate = referenceIndex >= 0 ? referenceSeries.x[referenceIndex] : referenceSeries?.x?.at(-1);
  if (dateNode) dateNode.textContent = referenceDate ? shortDate(referenceDate) : "Latest";
  document.querySelectorAll("#series-list .series-row[data-series-index]").forEach((row) => {
    const series = payload.series[Number(row.dataset.seriesIndex)];
    const valueNode = row.querySelector(".series-value");
    if (!series || !valueNode) return;
    const index = xValue === null ? -1 : nearestSeriesIndex(series, xValue);
    const values = seriesValueArray(series);
    const rawValue = index >= 0 ? values[index] : values.at(-1);
    valueNode.textContent = formatMetricValue(series.name, rawValue);
  });
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
  if (!Array.isArray(values) || !Array.isArray(scale) || !Array.isArray(series.x) || !Array.isArray(series.y)) {
    return [series];
  }
  if (values.length !== series.y.length || series.x.length !== series.y.length) return [series];
  if (Number(series.marker.size) > 4) return [series];

  const lower = Number(series.marker.cmin);
  const upper = Number(series.marker.cmax);
  if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper) return [series];

  const bucketCount = 12;
  const buckets = Array.from({ length: bucketCount }, (_, index) => ({
    color: gradientColor(scale, (index + 0.5) / bucketCount),
    x: [],
    y: [],
  }));
  for (let index = 0; index < series.y.length - 1; index += 1) {
    const start = Number(series.y[index]);
    const end = Number(series.y[index + 1]);
    if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
    const midpoint = (start + end) / 2;
    const ratio = Math.max(0, Math.min(1, (midpoint - lower) / (upper - lower)));
    const bucket = buckets[Math.min(bucketCount - 1, Math.floor(ratio * bucketCount))];
    bucket.x.push(series.x[index], series.x[index + 1], null);
    bucket.y.push(start, end, null);
  }

  const visibleBuckets = buckets.filter((bucket) => bucket.x.length);
  const { marker: _marker, ...lineSeries } = series;
  const coloredSegments = visibleBuckets.map((bucket, index) => ({
    ...lineSeries,
    x: bucket.x,
    y: bucket.y,
    mode: "lines",
    line: { color: bucket.color, width: 1.8 },
    hoverinfo: "skip",
    showlegend: index === 0,
  }));
  const hoverCarrier = {
    ...lineSeries,
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
  if (upperIndex <= 0) return stops[0][1];
  if (upperIndex < 0) return stops.at(-1)[1];
  const [startAt, startColor] = stops[upperIndex - 1];
  const [endAt, endColor] = stops[upperIndex];
  const mix = endAt === startAt ? 1 : (ratio - startAt) / (endAt - startAt);
  const start = startColor.slice(1).match(/.{2}/g).map((part) => parseInt(part, 16));
  const end = endColor.slice(1).match(/.{2}/g).map((part) => parseInt(part, 16));
  const rgb = start.map((channel, index) => Math.round(channel + ((end[index] - channel) * mix)));
  return `#${rgb.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
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

function ratioByKeys(numeratorKey, denominatorKey) {
  return (payload) => {
    const numerator = payload.series.find((series) => series.source_key === numeratorKey);
    const denominator = payload.series.find((series) => series.source_key === denominatorKey);
    if (!numerator || !denominator) return [];
    const denominatorByDate = new Map(denominator.x.map((date, index) => [date, toFiniteNumber(denominator.y[index])]));
    return numerator.x.map((date, index) => ({
      date,
      value: toFiniteNumber(numerator.y[index]) / denominatorByDate.get(date),
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
  const promise = fetchJson(assetPath(chart.data_path)).then(normalizePayload);
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
