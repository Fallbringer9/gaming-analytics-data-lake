"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("question-form");
const questionField = byId("question");
const submit = byId("submit");
const titles = {
  get_player_finance: "Bilan du joueur",
  get_net_flow_by_player: "Flux net par joueur",
  get_finance_overview: "Bilan financier global",
  get_daily_finance_trend: "Tendance journalière",
  get_failed_deposits: "Dépôts échoués",
  get_top_depositors: "Classement des déposants",
  get_max_deposit: "Plus gros dépôt validé",
  get_large_deposits: "Dépôts validés supérieurs à 10 000",
};
const columnTitles = {
  player_id: "Joueur",
  activity_date: "Date UTC",
  completed_deposits: "Dépôts validés",
  completed_withdrawals: "Retraits validés",
  net_flow: "Flux net",
  failed_deposits: "Dépôts échoués",
  amount: "Montant",
};
const chartMetrics = {
  get_net_flow_by_player: "net_flow",
  get_daily_finance_trend: "net_flow",
  get_failed_deposits: "failed_deposits",
  get_top_depositors: "completed_deposits",
  get_large_deposits: "amount",
};
const moneyColumns = new Set(["completed_deposits", "completed_withdrawals", "net_flow", "amount"]);
const dateFormat = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeZone: "UTC" });
const numberFormat = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const countFormat = new Intl.NumberFormat("fr-FR");

function formatDate(value) {
  const date = new Date(value + "T00:00:00Z");
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}

function formatValue(column, value) {
  if (value == null) return "—";
  if (column === "activity_date") return formatDate(value);
  if (moneyColumns.has(column)) return numberFormat.format(value);
  if (column === "failed_deposits") return countFormat.format(value);
  return value;
}

function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  if (className) node.className = className;
  return node;
}

function setStatus(state, message) {
  byId("status").dataset.state = state;
  byId("status-text").textContent = message;
  byId("status").hidden = !message;
}

function renderTable(columns, rows) {
  const heading = element("tr");
  const isNumeric = (column) => moneyColumns.has(column) || column === "failed_deposits";
  for (const column of columns) {
    const cell = element("th", columnTitles[column] ?? column, isNumeric(column) ? "numeric" : "");
    cell.scope = "col";
    heading.append(cell);
  }
  byId("table-head").replaceChildren(heading);
  byId("table-body").replaceChildren(...rows.map((row) => {
    const line = element("tr");
    for (const column of columns) {
      line.append(element("td", formatValue(column, row[column]), isNumeric(column) ? "numeric" : ""));
    }
    return line;
  }));
}

function renderChart(tool, rows) {
  const metric = chartMetrics[tool];
  const points = rows.filter((row) => row[metric] != null && Number.isFinite(Number(row[metric])));
  byId("chart").hidden = !metric || points.length < 2;
  if (byId("chart").hidden) return;

  const shown = points.slice(0, 10);
  const values = shown.map((row) => Number(row[metric]));
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = max - min || 1;
  const zero = (0 - min) / range * 100;
  byId("chart-title").textContent = columnTitles[metric];
  byId("chart-bars").replaceChildren(...shown.map((row, index) => {
    const label = [row.player_id, row.activity_date && formatDate(row.activity_date)].filter(Boolean).join(" · ");
    const track = element("span", undefined, "track");
    track.setAttribute("aria-hidden", "true");
    const barEnd = (values[index] - min) / range * 100;
    const bar = element("i", undefined, values[index] < 0 ? "bar negative" : "bar");
    bar.style.left = Math.min(zero, barEnd) + "%";
    bar.style.width = Math.abs(barEnd - zero) + "%";
    track.append(bar);
    if (min < 0 && max > 0) {
      const marker = element("i", undefined, "zero");
      marker.style.left = zero + "%";
      track.append(marker);
    }
    const item = element("li");
    item.append(element("span", label), track, element("span", formatValue(metric, row[metric])));
    return item;
  }));
  const note = byId("chart-note");
  note.hidden = points.length <= shown.length;
  note.textContent = "Les 10 premières lignes sont représentées.";
}

function renderResult(payload) {
  const { query_name: tool, parameters, result: { columns, rows } } = payload;
  byId("result-title").textContent = titles[tool] ?? "Résultats";
  const from = formatDate(parameters.start_date);
  const until = formatDate(parameters.end_date);
  byId("period").textContent = from + " → " + until + " (fin exclue)";
  byId("period").hidden = false;
  byId("row-count").textContent = rows.length + (rows.length === 1 ? " ligne" : " lignes");
  byId("row-count").hidden = false;

  if (!rows.length) {
    setStatus("empty", "Aucun résultat pour cette période.");
    return;
  }

  renderTable(columns, rows);
  renderChart(tool, rows);
  byId("data").hidden = false;
  setStatus("success", "");
}

for (const button of document.querySelectorAll(".example")) {
  button.addEventListener("click", () => {
    questionField.value = button.dataset.question;
    questionField.focus();
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionField.value.trim();
  if (!question || submit.disabled) return;

  submit.disabled = true;
  byId("results").setAttribute("aria-busy", "true");
  byId("result-title").textContent = "Résultats";
  byId("period").hidden = byId("row-count").hidden = byId("data").hidden = true;
  setStatus("loading", "Analyse de la question en cours…");
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();
    if (!response.ok) {
      setStatus("error", payload.error?.message ?? "La requête a échoué.");
      return;
    }
    renderResult(payload);
  } catch {
    setStatus("error", "La réponse de l’API est indisponible. Réessaie dans un instant.");
  } finally {
    byId("results").setAttribute("aria-busy", "false");
    submit.disabled = false;
  }
});
