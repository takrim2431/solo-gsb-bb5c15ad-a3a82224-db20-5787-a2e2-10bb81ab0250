"""直流电阻网络求解器。

输入网表（每行一个元件）：
    R 名称 节点1 节点2 欧姆值      —— 电阻，阻值必须为正
    V 名称 正端节点 负端节点 伏特值  —— 理想电压源
节点 0 为地。空行与 # 注释被忽略。

求解方法：改进节点分析（MNA, Modified Nodal Analysis），
将节点电压与电压源电流作为未知量联立求解，可处理浮地电压源。

解的判定（基于系数矩阵与增广矩阵的秩）：
    rank(A) == 未知数个数        -> 唯一解
    rank([A|b]) > rank(A)        -> 无解（约束冲突）
    rank(A) < 未知数个数          -> 多解（存在自由度）
后两种情况不输出任何数值解。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

# 元件名：字母或下划线开头，仅含字母、数字、下划线
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# 节点号：非负整数
NODE_RE = re.compile(r"^[0-9]+$")
# 数值：普通十进制或科学计数法（显式排除 nan/inf 等）
VALUE_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")

MAX_LINES = 2000  # 网表行数上限，防止滥用


@dataclass
class Element:
    kind: str  # "R" 或 "V"
    name: str
    n1: int  # 电阻端点1 / 电压源正端
    n2: int  # 电阻端点2 / 电压源负端
    value: float  # 欧姆 / 伏特


def parse_netlist(text: str) -> tuple[list[Element], list[dict]]:
    """解析网表文本。

    返回 (elements, errors)。errors 中每项为 {"line": 行号|None, "message": 描述}，
    行号为 1 起始；只要存在错误，调用方就不应继续求解。
    """
    elements: list[Element] = []
    errors: list[dict] = []
    names: set[str] = set()

    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        return [], [{"line": None, "message": f"行数超过上限 {MAX_LINES} 行"}]

    for lineno, raw in enumerate(lines, start=1):
        # 去掉注释与首尾空白
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 5:
            errors.append({
                "line": lineno,
                "message": (
                    f"格式错误：每行应为 5 个字段"
                    f"「类型 名称 节点1 节点2 数值」，实际为 {len(parts)} 个"
                ),
            })
            continue

        kind_tok, name, n1_tok, n2_tok, val_tok = parts

        kind = kind_tok.upper()
        if len(kind_tok) != 1 or kind not in ("R", "V"):
            errors.append({
                "line": lineno,
                "message": f"未知元件类型「{kind_tok}」，仅支持 R（电阻）和 V（电压源）",
            })
            continue

        if not NAME_RE.match(name):
            errors.append({
                "line": lineno,
                "message": f"名称「{name}」非法：须以字母或下划线开头，仅含字母、数字、下划线",
            })
            continue
        if name in names:
            errors.append({"line": lineno, "message": f"元件名称「{name}」重复"})
            continue
        # 名称格式合法即占用：即使后续校验失败，也能检出其余行的重名
        names.add(name)

        nodes: list[int] = []
        node_ok = True
        for tok, label in ((n1_tok, "节点1"), (n2_tok, "节点2")):
            if not NODE_RE.match(tok):
                errors.append({
                    "line": lineno,
                    "message": f"{label}「{tok}」不是非负整数（节点 0 为地）",
                })
                node_ok = False
            else:
                nodes.append(int(tok))
        if not node_ok:
            continue
        n1, n2 = nodes
        if n1 == n2:
            errors.append({"line": lineno, "message": "元件两端的节点不能相同"})
            continue

        if not VALUE_RE.match(val_tok):
            errors.append({
                "line": lineno,
                "message": f"数值「{val_tok}」不是有效的十进制数（支持科学计数法，如 4.7e3）",
            })
            continue
        value = float(val_tok)
        if kind == "R" and value <= 0:
            errors.append({
                "line": lineno,
                "message": f"电阻值必须为正数，当前为 {val_tok}",
            })
            continue

        elements.append(Element(kind=kind, name=name, n1=n1, n2=n2, value=value))

    return elements, errors


def solve_network(elements: list[Element]) -> dict:
    """对解析后的元件列表执行 MNA 求解，返回结构化结果。"""
    # 收集非地节点并建立压缩编号
    node_set: set[int] = set()
    for e in elements:
        node_set.add(e.n1)
        node_set.add(e.n2)
    node_set.discard(0)
    node_list = sorted(node_set)
    index = {node: i for i, node in enumerate(node_list)}

    n = len(node_list)
    vsrcs = [e for e in elements if e.kind == "V"]
    m = len(vsrcs)
    size = n + m

    # MNA 方程：[G  B] [v]   [0]
    #            [Bᵀ 0] [i] = [E]
    A = np.zeros((size, size))
    b = np.zeros(size)

    for e in elements:
        if e.kind != "R":
            continue
        g = 1.0 / e.value
        i = index.get(e.n1)
        j = index.get(e.n2)
        if i is not None:
            A[i, i] += g
        if j is not None:
            A[j, j] += g
        if i is not None and j is not None:
            A[i, j] -= g
            A[j, i] -= g

    for k, e in enumerate(vsrcs):
        row = n + k
        i = index.get(e.n1)  # 正端
        j = index.get(e.n2)  # 负端
        if i is not None:
            A[i, row] += 1.0
            A[row, i] += 1.0
        if j is not None:
            A[j, row] -= 1.0
            A[row, j] -= 1.0
        b[row] = e.value

    # 用秩判定解的存在性与唯一性
    rank_a = int(np.linalg.matrix_rank(A))
    rank_aug = int(np.linalg.matrix_rank(np.column_stack([A, b])))

    if rank_aug > rank_a:
        return {
            "status": "no_solution",
            "message": "无解：约束相互冲突（例如不同电压的电压源并联，或电压源回路不满足基尔霍夫电压定律）。不输出数值解。",
        }
    if rank_a < size:
        return {
            "status": "infinite",
            "nullity": size - rank_a,
            "message": (
                f"多解：方程组存在 {size - rank_a} 个自由度"
                "（通常由浮地子电路缺少电位参考，或电压源约束冗余引起）。不输出任意数值解。"
            ),
        }

    x = np.linalg.solve(A, b)

    # 清理数值噪声：相对最大未知量小于 1e-12 的分量置零
    scale = float(np.max(np.abs(x))) if x.size else 0.0
    if scale > 0:
        x[np.abs(x) < 1e-12 * scale] = 0.0

    voltages = [{"node": 0, "voltage": 0.0}]  # 地节点一并展示
    voltages += [
        {"node": node, "voltage": float(x[i])} for i, node in enumerate(node_list)
    ]

    # 元件电流：沿输入方向（电阻 节点1→节点2；电压源 正端→负端）
    vs_row = {e.name: n + k for k, e in enumerate(vsrcs)}
    currents = []
    for e in elements:
        if e.kind == "R":
            v1 = float(x[index[e.n1]]) if e.n1 in index else 0.0
            v2 = float(x[index[e.n2]]) if e.n2 in index else 0.0
            current = (v1 - v2) / e.value
        else:
            current = float(x[vs_row[e.name]])
        currents.append({
            "name": e.name,
            "kind": e.kind,
            "value": e.value,
            "from": e.n1,
            "to": e.n2,
            "current": current,
        })

    return {
        "status": "unique",
        "message": "唯一解",
        "nodes": voltages,
        "currents": currents,
    }
