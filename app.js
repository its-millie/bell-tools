const DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const TIME_OF_DAY_ORDER = ["morning", "afternoon", "evening", "night"];
const SEVERITY_ORDER = ["Critical", "Major", "Moderate", "Minor"];

const NEON = ["#14b8a6", "#ef6f3c", "#2f80ed", "#ffbe0b", "#0ea5e9", "#10b981", "#f43f5e", "#8b5cf6"];
const SEVERITY_COLORS = { Critical: "#d9480f", Major: "#f08c00", Moderate: "#fab005", Minor: "#2b8a3e" };
const TOD_COLORS = { morning: "#f59f00", afternoon: "#ef6f3c", evening: "#2f80ed", night: "#0f766e" };

const REQUIRED = ["machine_id", "downtime_hours", "failure_severity", "root_cause_category"];
const SENSOR_COLS = [
  "max_temperature_c_72h",
  "max_vibration_x_72h",
  "max_motor_current_a_72h",
  "min_lubricant_quality_72h",
];

const state = {
  raw: [],
  filtered: [],
  activeTab: "overview",
};

const el = {
  csvInput: document.getElementById("csvInput"),
  loadDefaultBtn: document.getElementById("loadDefaultBtn"),
  machineFilter: document.getElementById("machineFilter"),
  severityFilter: document.getElementById("severityFilter"),
  categoryFilter: document.getElementById("categoryFilter"),
  startDate: document.getElementById("startDate"),
  endDate: document.getElementById("endDate"),
  statusLine: document.getElementById("statusLine"),
  kpiRow: document.getElementById("kpiRow"),
  tabBtns: Array.from(document.querySelectorAll(".tab-btn")),
  tabContents: Array.from(document.querySelectorAll(".tab-content")),
  rawTableHead: document.querySelector("#rawTable thead"),
  rawTableBody: document.querySelector("#rawTable tbody"),
  downloadCsvBtn: document.getElementById("downloadCsvBtn"),
  sunburstMessage: document.getElementById("sunburstMessage"),
  tempMsg: document.getElementById("tempMsg"),
  vibrationMsg: document.getElementById("vibrationMsg"),
  motorLubeMsg: document.getElementById("motorLubeMsg"),
  corrMsg: document.getElementById("corrMsg"),
};

const PLOT_CONTAINERS = [
  "chartBreakdowns",
  "chartDowntime",
  "chartSeverity",
  "chartHeatmap",
  "chartPareto",
  "chartSunburst",
  "chartPolar",
  "chartBox",
  "chartWeekly",
  "chartRace",
  "chartTemp",
  "chartVibration",
  "chartMotorLube",
  "chartCorrelation",
];

const baseLayout = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  margin: { t: 12, l: 44, r: 10, b: 44 },
  font: { family: "Space Grotesk, sans-serif", color: "#1f2a37", size: 12 },
};

const chartConfig = { responsive: true, displayModeBar: false };

init();

function init() {
  wireEvents();
  clearPlots();
  el.statusLine.textContent = "Load a CSV with machine failure records to start.";
}

function wireEvents() {
  el.csvInput.addEventListener("change", onUploadCsv);
  el.loadDefaultBtn.addEventListener("click", loadBundledCsv);
  [el.machineFilter, el.severityFilter, el.categoryFilter, el.startDate, el.endDate].forEach((node) => {
    node.addEventListener("change", applyFiltersAndRender);
  });

  el.tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      state.activeTab = tab;
      el.tabBtns.forEach((b) => b.classList.toggle("active", b === btn));
      el.tabContents.forEach((content) => content.classList.toggle("active", content.id === `tab-${tab}`));
      setTimeout(() => window.dispatchEvent(new Event("resize")), 30);
    });
  });

  el.downloadCsvBtn.addEventListener("click", downloadFilteredCsv);
}

async function loadBundledCsv() {
  el.statusLine.textContent = "Loading bundled CSV...";
  try {
    const response = await fetch("data_drop/failure_records.csv", { cache: "no-cache" });
    if (!response.ok) {
      throw new Error("Bundled CSV not found. Upload one manually.");
    }
    const text = await response.text();
    const rows = parseCsvText(text);
    processData(rows, "data_drop/failure_records.csv");
  } catch (error) {
    el.statusLine.textContent = `Load failed: ${error.message}`;
  }
}

function onUploadCsv(event) {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  Papa.parse(file, {
    header: true,
    dynamicTyping: false,
    skipEmptyLines: true,
    complete: (results) => processData(results.data, file.name),
    error: (err) => {
      el.statusLine.textContent = `CSV parse error: ${err.message}`;
    },
  });
}

function parseCsvText(text) {
  const parsed = Papa.parse(text, {
    header: true,
    dynamicTyping: false,
    skipEmptyLines: true,
  });
  if (parsed.errors.length > 0) {
    throw new Error(parsed.errors[0].message);
  }
  return parsed.data;
}

function processData(rows, sourceName) {
  try {
    const normalized = normalizeRows(rows);
    state.raw = normalized;
    populateFilters(normalized);
    applyFiltersAndRender();
    el.statusLine.textContent = `Loaded ${normalized.length.toLocaleString()} records from ${sourceName}.`;
  } catch (error) {
    state.raw = [];
    state.filtered = [];
    clearPlots();
    el.kpiRow.innerHTML = "";
    el.rawTableHead.innerHTML = "";
    el.rawTableBody.innerHTML = "";
    el.statusLine.textContent = `Data error: ${error.message}`;
  }
}

function normalizeRows(rows) {
  if (!rows.length) {
    throw new Error("CSV has no rows.");
  }

  const columns = Object.keys(rows[0]);
  const hasTimestamp = columns.includes("failure_timestamp");
  const hasDate = columns.includes("date");

  if (!hasTimestamp && !hasDate) {
    throw new Error("Expected either failure_timestamp or date column.");
  }

  for (const req of REQUIRED) {
    if (!columns.includes(req)) {
      throw new Error(`Missing required column: ${req}`);
    }
  }

  const clean = [];
  rows.forEach((row) => {
    const when = hasTimestamp ? parseDateAny(row.failure_timestamp) : parseDateDMY(row.date);
    if (!when) {
      return;
    }

    const machine = cleanText(row.machine_id);
    const sev = cleanText(row.failure_severity);
    const cause = cleanText(row.root_cause_category);
    const downtime = Number(row.downtime_hours);
    if (!machine || !sev || !cause || Number.isNaN(downtime)) {
      return;
    }

    const day = row.day_of_week ? cleanText(row.day_of_week) : DAY_ORDER[when.getDay() === 0 ? 6 : when.getDay() - 1];
    const tod = row.time_of_day ? cleanText(row.time_of_day).toLowerCase() : classifyTimeOfDay(when.getHours());

    const out = {
      ...row,
      failure_timestamp: when,
      date: row.date || formatDMY(when),
      day_of_week: day,
      time_of_day: tod,
      machine_id: machine,
      failure_severity: sev,
      root_cause_category: cause,
      root_cause_subcategory: cleanText(row.root_cause_subcategory),
      downtime_hours: downtime,
    };

    SENSOR_COLS.forEach((col) => {
      const val = Number(row[col]);
      out[col] = Number.isNaN(val) ? null : val;
    });

    clean.push(out);
  });

  if (!clean.length) {
    throw new Error("No valid rows after parsing.");
  }

  return clean;
}

function populateFilters(rows) {
  fillSelect(el.machineFilter, uniq(rows.map((r) => r.machine_id).sort()));

  const severities = SEVERITY_ORDER.filter((s) => rows.some((r) => r.failure_severity === s));
  fillSelect(el.severityFilter, severities);

  fillSelect(el.categoryFilter, uniq(rows.map((r) => r.root_cause_category).sort()));

  const minDate = new Date(Math.min(...rows.map((r) => r.failure_timestamp.getTime())));
  const maxDate = new Date(Math.max(...rows.map((r) => r.failure_timestamp.getTime())));

  el.startDate.value = toISODate(minDate);
  el.endDate.value = toISODate(maxDate);
  el.startDate.min = toISODate(minDate);
  el.startDate.max = toISODate(maxDate);
  el.endDate.min = toISODate(minDate);
  el.endDate.max = toISODate(maxDate);
}

function applyFiltersAndRender() {
  if (!state.raw.length) {
    return;
  }

  const machines = selectedValues(el.machineFilter);
  const severities = selectedValues(el.severityFilter);
  const categories = selectedValues(el.categoryFilter);

  const start = parseDateAny(el.startDate.value);
  const end = parseDateAny(el.endDate.value);
  if (!start || !end) {
    return;
  }
  end.setHours(23, 59, 59, 999);

  state.filtered = state.raw.filter((row) => {
    return (
      machines.includes(row.machine_id) &&
      severities.includes(row.failure_severity) &&
      categories.includes(row.root_cause_category) &&
      row.failure_timestamp >= start &&
      row.failure_timestamp <= end
    );
  });

  const total = state.raw.length;
  const shown = state.filtered.length;
  el.statusLine.textContent = `${shown.toLocaleString()} of ${total.toLocaleString()} records shown after filters.`;

  if (!state.filtered.length) {
    el.kpiRow.innerHTML = "";
    clearPlots();
    el.rawTableHead.innerHTML = "";
    el.rawTableBody.innerHTML = "";
    return;
  }

  renderKpis(state.filtered);
  renderOverview(state.filtered);
  renderDeepDive(state.filtered);
  renderSensor(state.filtered);
  renderRawTable(state.filtered);
}

function renderKpis(data) {
  const totalBreakdowns = data.length;
  const downtime = sum(data.map((r) => r.downtime_hours));
  const avg = downtime / totalBreakdowns;
  const topMachine = topByCount(data.map((r) => r.machine_id));
  const topCause = topByCount(data.map((r) => r.root_cause_category));

  const cards = [
    ["Total Breakdowns", totalBreakdowns.toLocaleString()],
    ["Total Downtime (hrs)", downtime.toFixed(1)],
    ["Avg Downtime / Breakdown", `${avg.toFixed(1)} hrs`],
    ["Most Problematic Machine", topMachine],
    ["Top Root Cause", titleize(topCause.replaceAll("_", " "))],
  ];

  el.kpiRow.innerHTML = cards
    .map(([label, value]) => `<article class="kpi"><div class="kpi-label">${escapeHtml(label)}</div><div class="kpi-value">${escapeHtml(value)}</div></article>`)
    .join("");
}

function renderOverview(data) {
  const latest = maxDate(data);
  const pastMonthStart = new Date(latest);
  pastMonthStart.setDate(pastMonthStart.getDate() - 30);
  const monthData = data.filter((r) => r.failure_timestamp >= pastMonthStart);

  const byMachine = countBy(monthData, (r) => r.machine_id);
  const machines = Object.keys(byMachine).sort();
  const machineCounts = machines.map((m) => byMachine[m]);

  Plotly.react(
    "chartBreakdowns",
    [{ x: machines, y: machineCounts, type: "bar", marker: { color: machines.map((_, i) => NEON[i % NEON.length]) } }],
    { ...baseLayout, yaxis: { title: "Breakdowns" }, xaxis: { title: "Machine" } },
    chartConfig,
  );

  const downtimeByMachine = sumBy(monthData, (r) => r.machine_id, (r) => r.downtime_hours);
  const machineOrder = Object.keys(downtimeByMachine).sort();
  Plotly.react(
    "chartDowntime",
    [{ x: machineOrder, y: machineOrder.map((k) => downtimeByMachine[k]), type: "bar", marker: { color: machineOrder.map((_, i) => NEON[(i + 1) % NEON.length]) } }],
    { ...baseLayout, yaxis: { title: "Downtime hours" }, xaxis: { title: "Machine" } },
    chartConfig,
  );

  const severityCounts = countBy(monthData, (r) => r.failure_severity);
  const order = SEVERITY_ORDER.filter((s) => severityCounts[s] !== undefined);
  Plotly.react(
    "chartSeverity",
    [{
      x: order,
      y: order.map((s) => severityCounts[s] || 0),
      type: "bar",
      marker: { color: order.map((s) => SEVERITY_COLORS[s] || "#999") },
    }],
    { ...baseLayout, yaxis: { title: "Breakdowns" }, xaxis: { title: "Severity" } },
    chartConfig,
  );

  const machineSet = uniq(data.map((r) => r.machine_id).sort());
  const z = machineSet.map((machine) => {
    return DAY_ORDER.map((day) => data.filter((r) => r.machine_id === machine && r.day_of_week === day).length);
  });

  Plotly.react(
    "chartHeatmap",
    [{ x: DAY_ORDER, y: machineSet, z, type: "heatmap", colorscale: "YlOrRd" }],
    { ...baseLayout, xaxis: { title: "Day of week" }, yaxis: { title: "Machine" } },
    chartConfig,
  );
}

function renderDeepDive(data) {
  const categoryCounts = Object.entries(countBy(data, (r) => r.root_cause_category))
    .sort((a, b) => b[1] - a[1]);
  const cats = categoryCounts.map((x) => x[0]);
  const counts = categoryCounts.map((x) => x[1]);
  const cumulative = counts.map((_, i) => (100 * sum(counts.slice(0, i + 1))) / sum(counts));

  Plotly.react(
    "chartPareto",
    [
      { x: cats, y: counts, type: "bar", marker: { color: NEON[0] }, name: "Breakdowns" },
      { x: cats, y: cumulative, type: "scatter", mode: "lines+markers", marker: { color: NEON[1] }, line: { width: 3 }, yaxis: "y2", name: "Cumulative %" },
    ],
    {
      ...baseLayout,
      yaxis: { title: "Breakdowns" },
      yaxis2: { overlaying: "y", side: "right", range: [0, 105], title: "Cumulative %" },
      legend: { orientation: "h", y: 1.14 },
    },
    chartConfig,
  );

  const hasSub = data.some((r) => r.root_cause_subcategory);
  if (hasSub) {
    el.sunburstMessage.classList.add("hidden");
    const labels = [];
    const parents = [];
    const values = [];

    categoryCounts.forEach(([cat]) => {
      labels.push(cat);
      parents.push("");
      values.push(data.filter((r) => r.root_cause_category === cat).length);

      const subCounts = countBy(data.filter((r) => r.root_cause_category === cat && r.root_cause_subcategory), (r) => r.root_cause_subcategory);
      Object.entries(subCounts).forEach(([sub, n]) => {
        labels.push(sub);
        parents.push(cat);
        values.push(n);
      });
    });

    Plotly.react(
      "chartSunburst",
      [{ labels, parents, values, type: "sunburst", marker: { colors: labels.map((_, i) => NEON[i % NEON.length]) } }],
      { ...baseLayout, margin: { t: 8, l: 8, r: 8, b: 8 } },
      chartConfig,
    );
  } else {
    Plotly.purge("chartSunburst");
    el.sunburstMessage.textContent = "No root_cause_subcategory values are available for the current filters.";
    el.sunburstMessage.classList.remove("hidden");
  }

  const polarTraces = TIME_OF_DAY_ORDER.map((tod) => {
    return {
      type: "barpolar",
      r: DAY_ORDER.map((day) => data.filter((r) => r.day_of_week === day && r.time_of_day === tod).length),
      theta: DAY_ORDER,
      name: tod,
      marker: { color: TOD_COLORS[tod] || "#999" },
    };
  });
  Plotly.react("chartPolar", polarTraces, { ...baseLayout, polar: { radialaxis: { visible: true } } }, chartConfig);

  const presentSev = SEVERITY_ORDER.filter((sev) => data.some((r) => r.failure_severity === sev));
  const boxTraces = presentSev.map((sev) => ({
    y: data.filter((r) => r.failure_severity === sev).map((r) => r.downtime_hours),
    name: sev,
    type: "box",
    marker: { color: SEVERITY_COLORS[sev] },
    boxpoints: "all",
    jitter: 0.35,
    pointpos: 0,
  }));
  Plotly.react("chartBox", boxTraces, { ...baseLayout, yaxis: { title: "Downtime hours" } }, chartConfig);

  const weekly = groupWeekly(data);
  Plotly.react(
    "chartWeekly",
    [{
      x: weekly.weeks,
      y: weekly.totals,
      type: "scatter",
      mode: "lines+markers",
      fill: "tozeroy",
      line: { color: NEON[2], width: 2 },
      marker: { size: 6, color: NEON[1] },
    }],
    {
      ...baseLayout,
      yaxis: { title: "Downtime hours" },
      xaxis: { rangeslider: { visible: true } },
    },
    chartConfig,
  );

  const race = buildRaceFrames(data);
  Plotly.react(
    "chartRace",
    race.traces,
    {
      ...baseLayout,
      yaxis: { title: "Cumulative breakdowns", rangemode: "tozero" },
      updatemenus: [
        {
          type: "buttons",
          showactive: false,
          x: 1,
          y: 1.15,
          buttons: [
            {
              label: "Play",
              method: "animate",
              args: [null, { frame: { duration: 380, redraw: false }, transition: { duration: 200 }, fromcurrent: true }],
            },
          ],
        },
      ],
      sliders: [
        {
          active: 0,
          y: -0.1,
          x: 0.1,
          len: 0.85,
          pad: { t: 12 },
          steps: race.frames.map((f) => ({
            label: f.name,
            method: "animate",
            args: [[f.name], { mode: "immediate", frame: { duration: 0, redraw: true }, transition: { duration: 0 } }],
          })),
        },
      ],
    },
    chartConfig,
  ).then(() => Plotly.addFrames("chartRace", race.frames));
}

function renderSensor(data) {
  const available = SENSOR_COLS.filter((c) => data.some((r) => r[c] !== null));

  renderScatter(
    "chartTemp",
    data,
    "max_temperature_c_72h",
    "downtime_hours",
    "failure_severity",
    "max_temperature_c_72h",
    "Max temperature (72h before, C)",
    el.tempMsg,
    available,
  );

  renderScatter(
    "chartVibration",
    data,
    "max_vibration_x_72h",
    "downtime_hours",
    "root_cause_category",
    "max_vibration_x_72h",
    "Max vibration (72h before)",
    el.vibrationMsg,
    available,
  );

  if (available.includes("max_motor_current_a_72h") && available.includes("min_lubricant_quality_72h")) {
    el.motorLubeMsg.classList.add("hidden");
    Plotly.react(
      "chartMotorLube",
      [
        {
          mode: "markers",
          type: "scatter",
          x: data.map((r) => r.max_motor_current_a_72h).filter((v) => v !== null),
          y: data.map((r) => r.min_lubricant_quality_72h).filter((v) => v !== null),
          marker: {
            size: data.map((r) => Math.max(6, Math.min(28, (r.downtime_hours || 1) * 1.2))),
            color: data.map((r) => SEVERITY_COLORS[r.failure_severity] || "#777"),
            opacity: 0.75,
          },
          text: data.map((r) => `${r.machine_id} | ${r.root_cause_category}`),
          hovertemplate: "%{text}<br>Motor current: %{x}<br>Lubricant quality: %{y}<extra></extra>",
        },
      ],
      { ...baseLayout, xaxis: { title: "Max motor current (A)" }, yaxis: { title: "Min lubricant quality" } },
      chartConfig,
    );
  } else {
    Plotly.purge("chartMotorLube");
    el.motorLubeMsg.textContent = "This chart needs both max_motor_current_a_72h and min_lubricant_quality_72h columns.";
    el.motorLubeMsg.classList.remove("hidden");
  }

  const numericCols = ["downtime_hours", ...available];
  if (numericCols.length < 2) {
    Plotly.purge("chartCorrelation");
    el.corrMsg.textContent = "Not enough numeric sensor columns for a correlation matrix.";
    el.corrMsg.classList.remove("hidden");
  } else {
    el.corrMsg.classList.add("hidden");
    const matrix = numericCols.map((rowCol) => {
      return numericCols.map((colCol) => pearson(data.map((r) => [r[rowCol], r[colCol]])));
    });
    Plotly.react(
      "chartCorrelation",
      [{ z: matrix, x: numericCols, y: numericCols, type: "heatmap", zmin: -1, zmax: 1, colorscale: "RdBu" }],
      { ...baseLayout },
      chartConfig,
    );
  }
}

function renderScatter(containerId, data, xCol, yCol, colorCol, keyCol, xTitle, msgEl, availableCols) {
  if (!availableCols.includes(keyCol)) {
    Plotly.purge(containerId);
    msgEl.textContent = `Column ${keyCol} is missing.`;
    msgEl.classList.remove("hidden");
    return;
  }

  msgEl.classList.add("hidden");
  const filtered = data.filter((r) => r[xCol] !== null && r[yCol] !== null);

  const byGroup = groupBy(filtered, (r) => r[colorCol]);
  const traces = Object.entries(byGroup).map(([group, rows], index) => ({
    type: "scatter",
    mode: "markers",
    name: group,
    x: rows.map((r) => r[xCol]),
    y: rows.map((r) => r[yCol]),
    marker: {
      size: rows.map((r) => Math.max(6, Math.min(26, (r.downtime_hours || 1) * 1.1))),
      color: SEVERITY_COLORS[group] || NEON[index % NEON.length],
      opacity: 0.74,
    },
    text: rows.map((r) => `${r.machine_id} | ${r.root_cause_category}`),
    hovertemplate: "%{text}<br>X: %{x}<br>Downtime: %{y}<extra></extra>",
  }));

  Plotly.react(
    containerId,
    traces,
    {
      ...baseLayout,
      xaxis: { title: xTitle },
      yaxis: { title: "Downtime hours" },
      legend: { orientation: "h", y: 1.16 },
    },
    chartConfig,
  );
}

function renderRawTable(data) {
  const cols = Object.keys(data[0] || {});
  el.rawTableHead.innerHTML = `<tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr>`;

  const limit = 500;
  const rows = data.slice(0, limit).map((row) => {
    const tds = cols.map((c) => {
      const val = row[c] instanceof Date ? row[c].toISOString() : row[c];
      return `<td>${escapeHtml(String(val ?? ""))}</td>`;
    });
    return `<tr>${tds.join("")}</tr>`;
  });
  el.rawTableBody.innerHTML = rows.join("");
}

function downloadFilteredCsv() {
  if (!state.filtered.length) {
    return;
  }

  const exportRows = state.filtered.map((row) => {
    const out = { ...row };
    out.failure_timestamp = row.failure_timestamp.toISOString();
    return out;
  });

  const csv = Papa.unparse(exportRows);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "failure_records_filtered.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function clearPlots() {
  PLOT_CONTAINERS.forEach((id) => Plotly.purge(id));
}

function fillSelect(selectEl, items) {
  selectEl.innerHTML = items.map((item) => `<option value="${escapeHtml(item)}" selected>${escapeHtml(item)}</option>`).join("");
}

function selectedValues(selectEl) {
  return Array.from(selectEl.selectedOptions).map((o) => o.value);
}

function classifyTimeOfDay(hour) {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  if (hour >= 17 && hour < 21) return "evening";
  return "night";
}

function parseDateAny(value) {
  if (!value) return null;
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return date;
  }
  return parseDateDMY(value);
}

function parseDateDMY(value) {
  if (!value || typeof value !== "string") return null;
  const parts = value.split("-");
  if (parts.length !== 3) return null;
  const [d, m, y] = parts.map(Number);
  if (!d || !m || !y) return null;
  return new Date(y, m - 1, d);
}

function formatDMY(date) {
  const d = String(date.getDate()).padStart(2, "0");
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const y = date.getFullYear();
  return `${d}-${m}-${y}`;
}

function toISODate(date) {
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function sum(values) {
  return values.reduce((acc, cur) => acc + cur, 0);
}

function sumBy(rows, keyFn, valFn) {
  const out = {};
  rows.forEach((row) => {
    const key = keyFn(row);
    out[key] = (out[key] || 0) + valFn(row);
  });
  return out;
}

function countBy(rows, keyFn) {
  const out = {};
  rows.forEach((row) => {
    const key = keyFn(row);
    out[key] = (out[key] || 0) + 1;
  });
  return out;
}

function groupBy(rows, keyFn) {
  const out = {};
  rows.forEach((row) => {
    const key = keyFn(row);
    if (!out[key]) out[key] = [];
    out[key].push(row);
  });
  return out;
}

function topByCount(values) {
  const counts = countBy(values, (v) => v);
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || "n/a";
}

function uniq(arr) {
  return [...new Set(arr)];
}

function cleanText(value) {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function titleize(value) {
  return value
    .split(" ")
    .filter(Boolean)
    .map((s) => s[0].toUpperCase() + s.slice(1).toLowerCase())
    .join(" ");
}

function maxDate(data) {
  return new Date(Math.max(...data.map((r) => r.failure_timestamp.getTime())));
}

function groupWeekly(rows) {
  const map = {};
  rows.forEach((r) => {
    const monday = mondayDate(r.failure_timestamp);
    const key = toISODate(monday);
    map[key] = (map[key] || 0) + r.downtime_hours;
  });
  const weeks = Object.keys(map).sort();
  return { weeks, totals: weeks.map((w) => map[w]) };
}

function mondayDate(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function buildRaceFrames(rows) {
  const weeklyMachine = {};
  const machines = uniq(rows.map((r) => r.machine_id)).sort();
  rows.forEach((r) => {
    const week = toISODate(mondayDate(r.failure_timestamp));
    if (!weeklyMachine[week]) {
      weeklyMachine[week] = {};
    }
    weeklyMachine[week][r.machine_id] = (weeklyMachine[week][r.machine_id] || 0) + 1;
  });

  const weeks = Object.keys(weeklyMachine).sort();
  const running = Object.fromEntries(machines.map((m) => [m, 0]));
  const frames = [];

  weeks.forEach((week) => {
    machines.forEach((m) => {
      running[m] += weeklyMachine[week][m] || 0;
    });

    frames.push({
      name: week,
      data: [
        {
          x: machines,
          y: machines.map((m) => running[m]),
          type: "bar",
          marker: { color: machines.map((_, i) => NEON[i % NEON.length]) },
        },
      ],
    });
  });

  const first = frames[0] || {
    name: "No data",
    data: [{ x: machines, y: machines.map(() => 0), type: "bar", marker: { color: NEON } }],
  };

  return { traces: first.data, frames };
}

function pearson(pairs) {
  const valid = pairs.filter(([a, b]) => a !== null && b !== null && !Number.isNaN(a) && !Number.isNaN(b));
  const n = valid.length;
  if (n < 2) {
    return 0;
  }
  const sumX = sum(valid.map((p) => p[0]));
  const sumY = sum(valid.map((p) => p[1]));
  const meanX = sumX / n;
  const meanY = sumY / n;

  let num = 0;
  let denX = 0;
  let denY = 0;
  valid.forEach(([x, y]) => {
    const dx = x - meanX;
    const dy = y - meanY;
    num += dx * dy;
    denX += dx * dx;
    denY += dy * dy;
  });

  const den = Math.sqrt(denX * denY);
  return den === 0 ? 0 : num / den;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
