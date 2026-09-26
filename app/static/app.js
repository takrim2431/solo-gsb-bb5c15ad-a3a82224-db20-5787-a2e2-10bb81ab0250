"use strict";

const EXAMPLES = {
  // 基本分压：12V 电源驱动 1k/2k 串联
  divider: `# 分压电路：节点 2 电压应为 8V
V Vs 1 0 12
R R1 1 2 1000
R R2 2 0 2000`,

  // 浮地电压源：Vx 两端都不接地
  floating: `# 浮地电压源 Vx 把节点 3 抬升到 V2 + 5
V Vs 1 0 12
R R1 1 2 2000
R R2 2 0 4000
V Vx 3 2 5
R R3 3 0 1000`,

  // 无解：不同电压的理想电压源直接并联
  infeasible: `# 12V 与 9V 电源直接并联，约束矛盾 -> 无解
V V1 1 0 12
V V2 1 0 9
R R1 1 0 1000`,

  // 多解：节点 2、3 构成纯电阻浮岛，没有任何元件接到地或电压源，
  // 浮岛整体电位可自由平移 -> 无穷多解
  infinite: `# 节点 2、3 组成浮岛：R2、R3 只在岛内相连，
# 没有任何元件把它们与地或电压源相连，整体电位自由 -> 无穷多解
V Vs 1 0 10
R R1 1 0 500
R R2 2 3 1000
R R3 3 2 2000`,
};

const netlistEl = document.getElementById("netlist");
const gutterEl = document.getElementById("gutter");
const bannerEl = document.getElementById("banner");
const errorsBoxEl = document.getElementById("errors-box");
const errorListEl = document.getElementById("error-list");
const tablesEl = document.getElementById("tables");
const voltageBodyEl = document.getElementById("voltage-body");
const currentBodyEl = document.getElementById("current-body");
const placeholderEl = document.getElementById("placeholder");

let errorLines = new Set();

function renderGutter() {
  const lines = netlistEl.value.split("\n").length;
  const parts = [];
  for (let i = 1; i <= lines; i++) {
    const cls = errorLines.has(i) ? ' class="error-line"' : "";
    parts.push(`<div${cls}>${i}</div>`);
  }
  gutterEl.innerHTML = parts.join("");
}

function clearResults() {
  bannerEl.className = "banner hidden";
  errorsBoxEl.classList.add("hidden");
  tablesEl.classList.add("hidden");
  placeholderEl.classList.remove("hidden");
  errorLines.clear();
  renderGutter();
}

function formatNumber(x) {
  if (!Number.isFinite(x)) return "—";
  const ax = Math.abs(x);
  if (ax !== 0 && (ax < 1e-4 || ax >= 1e7)) return x.toExponential(4);
  // 去掉浮点尾差与多余的 0
  return parseFloat(x.toPrecision(10)).toString();
}

const STATUS_TEXT = {
  unique: ["唯一解", "unique"],
  infeasible: ["无解", "infeasible"],
  infinite: ["无穷多解", "infinite"],
};

function renderResult(result) {
  placeholderEl.classList.add("hidden");
  errorsBoxEl.classList.add("hidden");

  const [label, cls] = STATUS_TEXT[result.status] || ["未知状态", "infeasible"];
  bannerEl.className = `banner ${cls}`;
  bannerEl.innerHTML =
    `<span class="tag">${label}</span>` +
    `<span>${result.summary}` +
    `<span class="meta">（系数矩阵秩 ${result.rank} / 未知量 ${result.unknowns}` +
    (result.rank_augmented !== undefined ? `，增广矩阵秩 ${result.rank_augmented}` : "") +
    "）</span></span>";

  if (result.status !== "unique") {
    // 无解 / 多解：按要求不展示任何数值
    tablesEl.classList.add("hidden");
    return;
  }

  tablesEl.classList.remove("hidden");

  voltageBodyEl.innerHTML = result.node_voltages
    .map(
      (nv) => `<tr><td>${nv.node}${nv.node === 0 ? "（地）" : ""}</td>` +
              `<td class="num">${formatNumber(nv.voltage)}</td></tr>`
    )
    .join("");

  currentBodyEl.innerHTML = result.currents
    .map((c) => {
      const kind = c.kind === "R" ? "电阻" : "电压源";
      return `<tr>
        <td>${c.name}</td>
        <td><span class="kind-badge kind-${c.kind}">${kind}</span></td>
        <td class="dir">${c.from_node} → ${c.to_node}</td>
        <td class="num">${formatNumber(c.current)}</td>
      </tr>`;
    })
    .join("");
}

function renderErrors(errors) {
  placeholderEl.classList.add("hidden");
  tablesEl.classList.add("hidden");
  bannerEl.className = "banner infeasible";
  bannerEl.innerHTML =
    '<span class="tag">输入错误</span><span>网表存在格式问题，请按行号修正后重新求解。</span>';

  errorLines = new Set();
  errorListEl.innerHTML = errors
    .map((e) => {
      const where = e.line === 0 ? "网络" : `第 ${e.line} 行`;
      if (e.line > 0) errorLines.add(e.line);
      return `<li data-line="${e.line}"><b>${where}</b>：${e.message}</li>`;
    })
    .join("");
  errorsBoxEl.classList.remove("hidden");
  renderGutter();

  errorListEl.querySelectorAll("li[data-line]").forEach((li) => {
    li.addEventListener("click", () => {
      const line = Number(li.dataset.line);
      if (line <= 0) { netlistEl.focus(); return; }
      const pos = netlistEl.value.split("\n")
        .slice(0, line - 1)
        .reduce((a, l) => a + l.length + 1, 0);
      netlistEl.focus();
      netlistEl.setSelectionRange(pos, pos);
      // 让目标行滚动到可视区域中部
      const lineHeight = parseFloat(getComputedStyle(netlistEl).lineHeight) || 20;
      netlistEl.scrollTop = Math.max(0, (line - 3) * lineHeight);
      gutterEl.scrollTop = netlistEl.scrollTop;
    });
  });
}

async function solve() {
  const text = netlistEl.value;
  let resp;
  try {
    resp = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ netlist: text }),
    });
  } catch (err) {
    renderErrors([{ line: 0, message: "无法连接求解服务：" + err.message }]);
    return;
  }

  let data;
  try { data = await resp.json(); }
  catch { renderErrors([{ line: 0, message: "服务返回了无法解析的响应" }]); return; }

  if (!data.ok) { renderErrors(data.errors); return; }
  errorLines.clear();
  renderGutter();
  renderResult(data.result);
}

netlistEl.addEventListener("input", () => {
  if (errorLines.size) { errorLines.clear(); renderGutter(); }
});
netlistEl.addEventListener("scroll", () => { gutterEl.scrollTop = netlistEl.scrollTop; });
netlistEl.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const s = netlistEl.selectionStart, en = netlistEl.selectionEnd;
    netlistEl.value = netlistEl.value.slice(0, s) + "  " + netlistEl.value.slice(en);
    netlistEl.selectionStart = netlistEl.selectionEnd = s + 2;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") solve();
});

document.getElementById("solve-btn").addEventListener("click", solve);

document.getElementById("clear-btn").addEventListener("click", () => {
  netlistEl.value = "";
  clearResults();
  netlistEl.focus();
});

document.getElementById("example-select").addEventListener("change", (e) => {
  const key = e.target.value;
  if (!key || !EXAMPLES[key]) return;
  netlistEl.value = EXAMPLES[key];
  netlistEl.scrollTop = 0;
  errorLines.clear();
  renderGutter();
  solve();
  e.target.value = "";
});

renderGutter();
netlistEl.value = EXAMPLES.divider;
renderGutter();
solve();
