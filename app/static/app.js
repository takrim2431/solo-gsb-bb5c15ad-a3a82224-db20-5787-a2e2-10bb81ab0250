"use strict";

// ---------- 内置示例 ----------
const EXAMPLES = {
  divider: {
    title: "分压器（唯一解）",
    text: [
      "# 分压器：10V 电源经 1kΩ / 2kΩ 分压",
      "V V1 1 0 10",
      "R R1 1 2 1000",
      "R R2 2 0 2000",
      "",
    ].join("\n"),
  },
  bridge: {
    title: "惠斯通电桥（唯一解）",
    text: [
      "# 惠斯通电桥",
      "V V1 1 0 12",
      "R R1 1 2 1000",
      "R R2 1 3 2000",
      "R R3 2 4 1500",
      "R R4 3 4 2200",
      "R R5 2 3 470",
      "R R6 4 0 1000",
      "",
    ].join("\n"),
  },
  floating: {
    title: "浮地电压源（唯一解）",
    text: [
      "# V2 两端均不接地，仍可求解",
      "V V1 1 0 10",
      "R R1 1 2 1000",
      "V V2 2 3 5",
      "R R2 3 0 2000",
      "",
    ].join("\n"),
  },
  conflict: {
    title: "电压源冲突（无解）",
    text: [
      "# 两个不同电压的电压源并联，约束冲突",
      "V V1 1 0 5",
      "V V2 1 0 3",
      "R R1 1 0 1000",
      "",
    ].join("\n"),
  },
  underdetermined: {
    title: "浮地子电路（多解）",
    text: [
      "# 节点 2、3 构成的子电路浮地，电位无法唯一确定",
      "V V1 1 0 10",
      "R R1 1 0 1000",
      "V V2 2 3 5",
      "R R2 2 3 2000",
      "",
    ].join("\n"),
  },
};

// ---------- DOM ----------
const netlistEl = document.getElementById("netlist");
const lineNumbersEl = document.getElementById("line-numbers");
const exampleSelect = document.getElementById("example-select");
const statusEl = document.getElementById("status");
const errorsEl = document.getElementById("errors");
const tablesEl = document.getElementById("tables");

// ---------- 行号 gutter ----------
function updateLineNumbers() {
  const count = netlistEl.value.split("\n").length;
  let html = "";
  for (let i = 1; i <= count; i++) html += i + "\n";
  lineNumbersEl.textContent = html;
}
netlistEl.addEventListener("input", updateLineNumbers);
netlistEl.addEventListener("scroll", () => {
  lineNumbersEl.scrollTop = netlistEl.scrollTop;
});

// ---------- 数字格式化 ----------
function fmt(x) {
  if (!Number.isFinite(x)) return String(x);
  if (Object.is(x, -0) || x === 0) return "0";
  const a = Math.abs(x);
  if (a >= 1e6 || a < 1e-4) return x.toExponential(4);
  return String(Number(x.toPrecision(6)));
}

// ---------- 渲染 ----------
function setStatus(cls, text) {
  statusEl.className = "status " + cls;
  statusEl.textContent = text;
}

function renderErrors(errors) {
  errorsEl.innerHTML = "";
  for (const err of errors) {
    const li = document.createElement("li");
    const where = err.line != null ? `第 ${err.line} 行：` : "";
    li.innerHTML = `<span class="line-no">${where}</span>${escapeHtml(err.message)}`;
    errorsEl.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderTables(data) {
  tablesEl.innerHTML = "";

  const vTable = document.createElement("table");
  vTable.innerHTML =
    "<caption>节点电压</caption>" +
    "<thead><tr><th>节点</th><th>电压 (V)</th></tr></thead>";
  const vBody = document.createElement("tbody");
  for (const row of data.nodes) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${row.node === 0 ? "0（地）" : row.node}</td>` +
      `<td class="num">${fmt(row.voltage)}</td>`;
    vBody.appendChild(tr);
  }
  vTable.appendChild(vBody);
  tablesEl.appendChild(vTable);

  const cTable = document.createElement("table");
  cTable.innerHTML =
    "<caption>元件电流（沿输入方向）</caption>" +
    "<thead><tr><th>元件</th><th>参数</th><th>方向</th><th>电流 (A)</th></tr></thead>";
  const cBody = document.createElement("tbody");
  for (const row of data.currents) {
    const tr = document.createElement("tr");
    const badge =
      row.kind === "R"
        ? `<span class="badge">电阻</span> ${escapeHtml(row.name)}`
        : `<span class="badge">电压源</span> ${escapeHtml(row.name)}`;
    const param = row.kind === "R" ? `${fmt(row.value)} Ω` : `${fmt(row.value)} V`;
    tr.innerHTML =
      `<td>${badge}</td>` +
      `<td class="num">${param}</td>` +
      `<td class="num">${row.from} → ${row.to}</td>` +
      `<td class="num">${fmt(row.current)}</td>`;
    cBody.appendChild(tr);
  }
  cTable.appendChild(cBody);
  tablesEl.appendChild(cTable);
}

function render(data) {
  errorsEl.innerHTML = "";
  tablesEl.innerHTML = "";

  switch (data.status) {
    case "unique":
      setStatus("unique", "✔ 唯一解");
      renderTables(data);
      break;
    case "no_solution":
      setStatus("no_solution", "✘ 无解 —— " + data.message);
      break;
    case "infinite":
      setStatus("infinite", "⚠ 多解 —— " + data.message);
      break;
    case "error":
      setStatus("error", "✘ 输入存在错误，请修正后重新求解：");
      renderErrors(data.errors || []);
      break;
    default:
      setStatus("error", "✘ 未知响应");
  }
}

// ---------- 求解 ----------
async function solve() {
  setStatus("idle", "求解中…");
  errorsEl.innerHTML = "";
  tablesEl.innerHTML = "";
  try {
    const resp = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ netlist: netlistEl.value }),
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    render(await resp.json());
  } catch (e) {
    setStatus("error", "✘ 请求失败：" + e.message);
  }
}

// ---------- 事件 ----------
for (const [key, ex] of Object.entries(EXAMPLES)) {
  const opt = document.createElement("option");
  opt.value = key;
  opt.textContent = ex.title;
  exampleSelect.appendChild(opt);
}

document.getElementById("load-example").addEventListener("click", () => {
  const ex = EXAMPLES[exampleSelect.value];
  if (!ex) return;
  netlistEl.value = ex.text;
  updateLineNumbers();
  solve(); // 载入后立即计算，便于查看效果；可修改后再次求解
});

document.getElementById("solve-btn").addEventListener("click", solve);

document.getElementById("clear-btn").addEventListener("click", () => {
  netlistEl.value = "";
  updateLineNumbers();
  setStatus("idle", "请在左侧输入网表，然后点击「求解」。");
  errorsEl.innerHTML = "";
  tablesEl.innerHTML = "";
  netlistEl.focus();
});

netlistEl.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    solve();
  }
});

// 初始载入第一个示例
netlistEl.value = EXAMPLES.divider.text;
updateLineNumbers();
solve();
