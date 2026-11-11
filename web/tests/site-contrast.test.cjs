const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8");

function load(theme = "dark") {
  const context = {
    window: { location: { search: "" } },
    document: { body: { dataset: {} }, documentElement: { dataset: { theme } }, addEventListener() {} },
    URLSearchParams, Intl,
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  context.constant = (name) => vm.runInContext(name, context);
  return context;
}

const site = load();
const DARK = "#181816";
const LIGHT = "#fffefa";
const MIN = site.constant("MIN_SERIES_CONTRAST");

test("contrast maths matches the WCAG reference values", () => {
  assert.equal(site.contrastRatio("#000000", "#ffffff"), 21);
  assert.equal(site.contrastRatio("#ffffff", "#ffffff"), 1);
  assert.ok(Math.abs(site.contrastRatio("#767676", "#ffffff") - 4.54) < 0.01);
  assert.ok(Math.abs(site.relativeLuminance("#808080") - 0.2159) < 0.001);
});

test("parser accepts hex, rgb, rgba, hsl, hsla, named and transparent colours", () => {
  assert.deepEqual({ ...site.parseCssColor("#abc") }, { r: 170, g: 187, b: 204, a: 1 });
  assert.equal(site.parseCssColor("#11223380").a.toFixed(2), "0.50");
  assert.deepEqual({ ...site.parseCssColor("rgb(10, 20, 30)") }, { r: 10, g: 20, b: 30, a: 1 });
  assert.deepEqual({ ...site.parseCssColor("rgba(10,20,30,.5)") }, { r: 10, g: 20, b: 30, a: 0.5 });
  assert.deepEqual({ ...site.parseCssColor("rgb(10 20 30 / 25%)") }, { r: 10, g: 20, b: 30, a: 0.25 });
  assert.deepEqual({ ...site.parseCssColor("rgb(100%, 0%, 0%)") }, { r: 255, g: 0, b: 0, a: 1 });
  assert.deepEqual({ ...site.parseCssColor("hsl(120, 100%, 25%)") }, { r: 0, g: 128, b: 0, a: 1 });
  assert.deepEqual({ ...site.parseCssColor("hsla(0deg, 0%, 100%, 0.4)") }, { r: 255, g: 255, b: 255, a: 0.4 });
  assert.deepEqual({ ...site.parseCssColor("  BLACK ") }, { r: 0, g: 0, b: 0, a: 1 });
  assert.equal(site.parseCssColor("transparent").a, 0);
});

test("parser rejects invalid input without throwing", () => {
  for (const value of ["", "   ", "banana", "#12", "#12345", "#gggggg", "rgb(1,2)", "rgb(a,b,c)", "hsl(x,1%,2%)", "url(x)", null, undefined, 5, {}, ["#fff"]]) {
    assert.equal(site.parseCssColor(value), null, String(value));
  }
});

test("pure black becomes light grey in dark mode and stays hue-neutral", () => {
  const adapted = site.ensureContrast("#000000", DARK);
  const { r, g, b } = site.parseCssColor(adapted);
  assert.ok(r === g && g === b, adapted);
  assert.ok(r >= 200, `black should become light grey, got ${adapted}`);
  assert.ok(site.contrastRatio(adapted, DARK) >= 7);
});

test("source near-blacks (#393732, #1f1e1c) are lifted in dark mode and keep their warm tint", () => {
  for (const color of ["#393732", "#1f1e1c"]) {
    const adapted = site.ensureContrast(color, DARK);
    assert.notEqual(adapted, color);
    assert.ok(site.contrastRatio(adapted, DARK) >= MIN, `${color} -> ${adapted}`);
    const { r, b } = site.parseCssColor(adapted);
    assert.ok(r >= b, `${adapted} keeps the source red>=blue tint`);
  }
});

test("colours that already have enough contrast are returned unchanged, in both themes", () => {
  assert.equal(site.ensureContrast("#858585", DARK), "#858585");
  assert.equal(site.ensureContrast("#858585", LIGHT), "#858585");
  assert.equal(site.ensureContrast("#eef3f8", DARK), "#eef3f8");
  assert.equal(site.ensureContrast("#171715", LIGHT), "#171715");
  assert.equal(site.ensureContrast("hsl(200, 80%, 60%)", DARK), "hsl(200, 80%, 60%)");
});

test("white and very light colours are darkened on the light surface", () => {
  const white = site.ensureContrast("#ffffff", LIGHT);
  const { r, g, b } = site.parseCssColor(white);
  assert.ok(r === g && g === b && r <= 40, `white should become near-black, got ${white}`);
  const yellow = site.ensureContrast("#ffff54", LIGHT);
  const parsed = site.parseCssColor(yellow);
  assert.ok(site.contrastRatio(yellow, LIGHT) >= MIN);
  assert.ok(parsed.r === parsed.g && parsed.b < parsed.r, `yellow keeps its hue, got ${yellow}`);
});

test("hue is preserved when a chromatic colour is lifted", () => {
  const hue = (color) => site.rgbToHsl(site.parseCssColor(color)).h;
  for (const [color, surface] of [["#0106f5", DARK], ["#2863a7", DARK], ["#6b21a8", DARK], ["#ffff54", LIGHT], ["#24c813", LIGHT]]) {
    const adapted = site.ensureContrast(color, surface);
    assert.notEqual(adapted, color);
    assert.ok(Math.abs(hue(adapted) - hue(color)) < 4, `${color} -> ${adapted}`);
    assert.ok(site.contrastRatio(adapted, surface) >= MIN);
  }
});

test("adaptation is idempotent", () => {
  for (const [color, surface] of [["#000000", DARK], ["#393732", DARK], ["#0106f5", DARK], ["#ffffff", LIGHT], ["#b5b2aa", LIGHT]]) {
    const once = site.ensureContrast(color, surface);
    assert.equal(site.ensureContrast(once, surface), once);
  }
});

test("rgba() and hsl() inputs keep their alpha and become valid CSS", () => {
  const rgba = site.ensureContrast("rgba(0,0,0,0.9)", DARK);
  assert.match(rgba, /^rgba\(\d+,\d+,\d+,0\.9\)$/);
  assert.ok(site.parseCssColor(rgba).r > 200);
  const hsl = site.ensureContrast("hsl(0, 0%, 5%)", DARK);
  assert.match(hsl, /^#[0-9a-f]{6}$/);
  assert.ok(site.contrastRatio(hsl, DARK) >= MIN);
});

test("translucent washes, transparent and invalid colours are left alone", () => {
  assert.equal(site.ensureContrast("rgba(0,0,0,0)", DARK), "rgba(0,0,0,0)");
  assert.equal(site.ensureContrast("rgba(31,30,28,0.1)", DARK), "rgba(31,30,28,0.1)");
  assert.equal(site.ensureContrast("rgba(245,200,75,0.38)", LIGHT), "rgba(245,200,75,0.38)");
  assert.equal(site.ensureContrast("banana", DARK), "banana");
  assert.equal(site.ensureContrast("#fff", "not-a-colour"), "#fff");
  assert.equal(site.ensureContrast(undefined, DARK), undefined);
  assert.equal(site.ensureContrast(7, DARK), 7);
});

test("the result never has less contrast than the input", () => {
  const surfaces = [DARK, "#1d1d1a", LIGHT, "#ffffff", "#808080"];
  for (let r = 0; r < 256; r += 51) for (let g = 0; g < 256; g += 51) for (let b = 0; b < 256; b += 51) {
    const color = `rgb(${r}, ${g}, ${b})`;
    for (const surface of surfaces) {
      const adapted = site.ensureContrast(color, surface);
      assert.ok(site.contrastRatio(adapted, surface) >= Math.min(MIN, site.contrastRatio(color, surface)) - 0.02, `${color} on ${surface} -> ${adapted}`);
    }
  }
});

test("mapSeriesColors recolours lines, markers, per-point arrays, fills, candles and colour scales without mutating the input", () => {
  const trace = {
    type: "scatter",
    x: [1, 2], y: [3, 4], name: "color: red",
    line: { color: "#111111", width: 2 },
    marker: { color: ["#222222", "#ffffff", 7, null], line: { color: "#333333" }, colorscale: [[0, "#000000"], [1, "#ffffff"]] },
    fillcolor: "rgba(1,2,3,0.5)",
    increasing: { line: { color: "#010101" }, fillcolor: "rgba(60,227,138,0.58)" },
    error_y: { color: "#050505" },
    textfont: { color: "#060606" },
    hoverlabel: { bgcolor: "#000000" },
    colorbar: { tickcolor: "#000000" },
    meta: { color: "#000000" },
  };
  const snapshot = JSON.stringify(trace);
  const seen = [];
  const mapped = site.mapSeriesColors(trace, (color, at) => { seen.push(at); return `<${color}>`; });
  assert.equal(JSON.stringify(trace), snapshot, "source payload is not mutated");
  assert.equal(mapped.line.color, "<#111111>");
  assert.deepEqual([...mapped.marker.color], ["<#222222>", "<#ffffff>", 7, null]);
  assert.equal(mapped.marker.line.color, "<#333333>");
  assert.deepEqual(JSON.parse(JSON.stringify(mapped.marker.colorscale)), [[0, "<#000000>"], [1, "<#ffffff>"]]);
  assert.equal(mapped.fillcolor, "<rgba(1,2,3,0.5)>");
  assert.equal(mapped.increasing.line.color, "<#010101>");
  assert.equal(mapped.increasing.fillcolor, "<rgba(60,227,138,0.58)>");
  assert.equal(mapped.error_y.color, "<#050505>");
  assert.equal(mapped.textfont.color, "<#060606>");
  assert.equal(mapped.hoverlabel.bgcolor, "#000000");
  assert.equal(mapped.colorbar.tickcolor, "#000000");
  assert.equal(mapped.meta.color, "#000000");
  assert.equal(mapped.name, "color: red");
  assert.equal(mapped.x, trace.x, "data arrays are shared, not copied");
  assert.ok(seen.includes("marker.line.color") && seen.includes("increasing.line.color"));
});

test("mapLayoutSeriesColors covers shapes, annotations and colorway but not axis chrome", () => {
  const layout = {
    shapes: [{ type: "line", line: { color: "#111111" }, fillcolor: "#222222" }],
    annotations: [{ text: "x", font: { color: "#333333" }, arrowcolor: "#444444", bgcolor: "#555555" }],
    colorway: ["#666666"],
    xaxis: { gridcolor: "#777777", tickfont: { color: "#888888" } },
  };
  const mapped = site.mapLayoutSeriesColors(layout, (color) => `<${color}>`);
  assert.equal(mapped.shapes[0].line.color, "<#111111>");
  assert.equal(mapped.shapes[0].fillcolor, "<#222222>");
  assert.equal(mapped.annotations[0].font.color, "<#333333>");
  assert.equal(mapped.annotations[0].arrowcolor, "<#444444>");
  assert.equal(mapped.annotations[0].bgcolor, "#555555");
  assert.deepEqual([...mapped.colorway], ["<#666666>"]);
  assert.equal(mapped.xaxis.gridcolor, "#777777");
  assert.equal(layout.shapes[0].line.color, "#111111");
});

test("palette remap precedes contrast and follows the active theme", () => {
  const dark = load("dark");
  const light = load("light");
  assert.equal(dark.themePaletteColor("#000000"), "#eef3f8");
  assert.equal(light.themePaletteColor("#000000"), "#393732");
  assert.equal(light.themePaletteColor("#F5C84B"), "#c85f3c");
  const adapter = dark.themeColorAdapter(dark.parseCssColor(DARK));
  assert.equal(adapter("#1f1e1c"), dark.ensureContrast("#1f1e1c", DARK));
  assert.equal(adapter(12), 12);
  assert.equal(adapter("#1f1e1c"), adapter("#1f1e1c"));
});

test("sidebar series colour follows the surface and never returns an invisible near-black", () => {
  const series = { name: "Stock-to-Flow", line: { color: "#1f1e1c" } };
  const dark = load("dark");
  const light = load("light");
  const onDark = dark.seriesColor(series, 0, dark.parseCssColor(DARK));
  const onLight = light.seriesColor(series, 0, light.parseCssColor(LIGHT));
  assert.ok(dark.contrastRatio(onDark, DARK) >= MIN, onDark);
  assert.equal(onLight, "#1f1e1c");
  assert.equal(dark.seriesSourceColor({ name: "n", marker: { color: "#123456" } }, 0), "#123456");
  assert.match(dark.seriesSourceColor({ name: "n" }, 1), /^#[0-9a-f]{6}$/);
});

test("every CSS named colour resolves and is adapted (full table, no DOM needed)", () => {
  assert.deepEqual({ ...site.parseCssColor("rebeccapurple") }, { r: 102, g: 51, b: 153, a: 1 });
  assert.deepEqual({ ...site.parseCssColor("DarkSlateGray") }, { r: 47, g: 79, b: 79, a: 1 });
  const adapted = site.ensureContrast("darkslategray", DARK);
  assert.notEqual(adapted, "darkslategray");
  assert.ok(site.contrastRatio(adapted, DARK) >= MIN, adapted);
  assert.equal(site.parseCssColor("constructor"), null);
  assert.equal(site.parseCssColor("__proto__"), null);
});

test("hsl() accepts deg, turn, rad and grad hue units and modern space syntax", () => {
  const red = { r: 255, g: 0, b: 0, a: 1 };
  for (const value of ["hsl(0, 100%, 50%)", "hsl(360deg 100% 50%)", "hsl(1turn,100%,50%)", "hsl(6.283185307rad, 100%, 50%)", "hsl(400grad 100% 50%)"]) {
    assert.deepEqual({ ...site.parseCssColor(value) }, red, value);
  }
  assert.deepEqual({ ...site.parseCssColor("hsl(.5turn,100%,50%)") }, { r: 0, g: 255, b: 255, a: 1 });
  assert.equal(site.parseCssColor("hsl(10px, 50%, 50%)"), null);
});

test("browser-only colour syntax is a safe no-op without a DOM and never throws", () => {
  for (const value of ["color(srgb 0.1 0.1 0.1)", "oklch(20% 0.02 80)", "color-mix(in srgb, red, blue)", "currentcolor", "var(--x)", "lab(10 0 0)"]) {
    assert.equal(site.parseCssColor(value), null, value);
    assert.equal(site.ensureContrast(value, DARK), value);
  }
  assert.equal(site.resolveBrowserColor("red"), null, "no document in the Node harness");
});

test("browser colour resolution works when a canvas is available, and caches results", () => {
  const calls = [];
  const context = {
    window: { location: { search: "" } },
    document: {
      body: { dataset: {} }, documentElement: { dataset: { theme: "dark" } }, addEventListener() {},
      createElement: () => ({
        getContext: () => {
          let style = "#000000";
          return {
            get fillStyle() { return style; },
            set fillStyle(value) { calls.push(value); if (value === "oklch(20% 0.02 80)") style = "#2a2620"; else if (/^#/.test(value)) style = value; },
          };
        },
      }),
    },
    URLSearchParams, Intl,
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  const parsed = context.parseCssColor("oklch(20% 0.02 80)");
  assert.deepEqual({ ...parsed }, { r: 42, g: 38, b: 32, a: 1 });
  assert.equal(context.parseCssColor("not a colour"), null);
  const before = calls.length;
  context.parseCssColor("oklch(20% 0.02 80)");
  context.parseCssColor("not a colour");
  assert.equal(calls.length, before, "second lookups are served from the cache");
  assert.ok(context.contrastRatio(context.ensureContrast("oklch(20% 0.02 80)", DARK), DARK) >= MIN);
});

test("adapting thousands of distinct colours stays fast", () => {
  const adapter = site.themeColorAdapter(site.parseCssColor(LIGHT));
  const colors = Array.from({ length: 6000 }, (_, index) => `#${((index * 2654435761) >>> 8 & 0xffffff).toString(16).padStart(6, "0")}`);
  const started = process.hrtime.bigint();
  colors.forEach((color) => adapter(color, "marker.color"));
  colors.forEach((color) => adapter(color, "marker.color"));
  const elapsed = Number(process.hrtime.bigint() - started) / 1e6;
  assert.ok(elapsed < 1500, `6,000 distinct colours took ${elapsed.toFixed(0)} ms`);
});

test("named and explicit colour scales are adapted with the same colour-scale target", () => {
  const surface = site.parseCssColor(LIGHT);
  const adapter = site.themeColorAdapter(surface);
  const stops = [[0, "#440154"], [0.5, "#21918c"], [1, "#fde725"]];
  const explicit = site.mapSeriesColors({ marker: { color: [1, 2], colorscale: stops } }, adapter).marker.colorscale;
  const resolvedPath = stops.map(([position, color]) => [position, adapter(color, "marker.colorscale")]);
  assert.deepEqual(JSON.parse(JSON.stringify(explicit)), resolvedPath);
  const asLine = adapter("#fde725", "line.color");
  assert.notEqual(asLine, resolvedPath[2][1], "line target is stricter than the colour-scale target");
  assert.equal(resolvedPath[2][1], site.ensureContrast("#fde725", surface, { min: 3, target: 3 }));
  assert.ok(site.contrastRatio(resolvedPath[2][1], surface) >= 3);
});

test("effective Plotly backgrounds are composited over the DOM surface", () => {
  const white = site.parseCssColor("#ffffff");
  const opaque = site.effectivePlotSurface(white, { plot_bgcolor: "#111111" });
  assert.equal(site.contrastRatio("#111111", opaque), 1);
  assert.deepEqual({ ...opaque }, { r: 17, g: 17, b: 17, a: 1 });
  const paperThenPlot = site.effectivePlotSurface(white, { paper_bgcolor: "#010101" }, { plot_bgcolor: "rgba(255,255,255,0.5)" });
  assert.deepEqual({ ...paperThenPlot }, { r: 128, g: 128, b: 128, a: 1 });
  assert.deepEqual({ ...site.effectivePlotSurface(white, { plot_bgcolor: "rgba(0,0,0,0)", paper_bgcolor: "transparent" }) }, { ...white });
  assert.deepEqual({ ...site.effectivePlotSurface(white, { plot_bgcolor: "not-a-colour" }) }, { ...white });
  assert.deepEqual({ ...site.effectivePlotSurface(white) }, { ...white });
  const lightened = site.ensureContrast("#111111", opaque);
  assert.ok(site.contrastRatio(lightened, opaque) >= MIN, lightened);
});

test("sidebar dot, legend and trace agree for marker-only and line series", () => {
  const surface = site.parseCssColor(LIGHT);
  const adapter = site.themeColorAdapter(surface);
  for (const series of [
    { name: "markers", mode: "markers", marker: { color: "#ffff54" } },
    { name: "line", mode: "lines", line: { color: "#ffff54" } },
    { name: "both", mode: "lines+markers", line: { color: "#ffff54" }, marker: { color: "#00ffff" } },
  ]) {
    const trace = site.mapSeriesColors(series, adapter);
    const traceColor = trace.line?.color || trace.marker.color;
    assert.equal(site.seriesColor(series, 0, surface), traceColor, series.name);
  }
  const markerOnly = site.seriesColor({ marker: { color: "#ffff54" } }, 0, surface);
  assert.equal(markerOnly, site.ensureContrast("#ffff54", surface, { target: MIN }));
  assert.equal(site.seriesColorPath({ marker: { color: "#fff" } }), "marker.color");
  assert.equal(site.seriesColorPath({ line: { color: "#fff" }, marker: { color: "#000" } }), "line.color");
});
