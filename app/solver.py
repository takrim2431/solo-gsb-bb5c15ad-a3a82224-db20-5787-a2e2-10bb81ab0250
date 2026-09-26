"""直流电阻网络：网表解析与改进节点法（MNA）求解。

网表每行一个元件（空行与以 # 开头的行被忽略）：
    R 名称 节点1 节点2 欧姆值
    V 名称 正端节点 负端节点 伏特值
节点 0 为参考地；电阻值必须严格为正。
"""

import math
import re
from dataclasses import dataclass

import numpy as np

_INTEGER = re.compile(r"^\d+$")


@dataclass
class Component:
    kind: str  # 'R' 电阻 或 'V' 独立电压源
    name: str
    n1: int
    n2: int
    value: float
    line: int


def parse_netlist(text):
    """解析网表文本，返回 (components, errors)。errors 非空时 components 不可用。"""
    components = []
    errors = []
    names = set()

    for lineno, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) != 5:
            errors.append({
                "line": lineno,
                "message": "字段数应为 5：类型 名称 节点1 节点2 数值",
            })
            continue

        type_tok, name, n1_tok, n2_tok, val_tok = parts
        kind = type_tok.upper()

        if kind not in ("R", "V"):
            errors.append({
                "line": lineno,
                "message": f"未知元件类型“{type_tok}”，只支持 R（电阻）或 V（电压源）",
            })
            continue

        if name in names:
            errors.append({"line": lineno, "message": f"元件名称“{name}”重复"})
            continue

        bad_node = False
        for label, tok in (("节点1", n1_tok), ("节点2", n2_tok)):
            if not _INTEGER.match(tok):
                errors.append({
                    "line": lineno,
                    "message": f"{label}“{tok}”必须是不小于 0 的整数",
                })
                bad_node = True
        if bad_node:
            continue

        n1, n2 = int(n1_tok), int(n2_tok)

        unit = "欧姆" if kind == "R" else "伏特"
        try:
            value = float(val_tok)
        except ValueError:
            errors.append({
                "line": lineno,
                "message": f"数值“{val_tok}”不是合法数字（单位：{unit}）",
            })
            continue
        if not math.isfinite(value):
            errors.append({"line": lineno, "message": f"数值必须是有限实数（单位：{unit}）"})
            continue

        if kind == "R" and value <= 0.0:
            errors.append({"line": lineno, "message": f"电阻值必须为正，当前为 {value:g} 欧姆"})
            continue

        names.add(name)
        components.append(Component(kind, name, n1, n2, value, lineno))

    if not errors and not components:
        errors.append({"line": 0, "message": "网络为空，请至少输入一行元件"})

    return components, errors


def solve_network(components):
    """用改进节点法求解，返回可直接 JSON 序列化的结果字典。

    status:
      unique    —— 唯一解，含 node_voltages / currents
      infeasible —— 无解（约束冲突），不返回任何数值结果
      infinite  —— 无穷多解（浮地部分自由），不返回任何数值结果
    """
    nodes = sorted({n for c in components for n in (c.n1, c.n2)} - {0})
    node_index = {node: i for i, node in enumerate(nodes)}
    vsources = [c for c in components if c.kind == "V"]

    n_nodes = len(nodes)
    n_vsrc = len(vsources)
    size = n_nodes + n_vsrc

    # 所有元件都挂在节点 0 上（只有 0-0 电阻时才会到这里）：唯一的零解。
    if size == 0:
        return {
            "status": "unique",
            "summary": "网络存在唯一解：所有元件均接于参考地，电压、电流均为 0。",
            "rank": 0,
            "unknowns": 0,
            "node_voltages": [{"node": 0, "voltage": 0.0}],
            "currents": [
                {
                    "name": c.name,
                    "kind": c.kind,
                    "from_node": c.n1,
                    "to_node": c.n2,
                    "current": 0.0,
                    "line": c.line,
                }
                for c in components
            ],
        }

    A = np.zeros((size, size), dtype=float)
    z = np.zeros(size, dtype=float)

    # 电阻 stamps：节点导纳矩阵
    for c in components:
        if c.kind != "R":
            continue
        g = 1.0 / c.value
        i1 = node_index.get(c.n1)
        i2 = node_index.get(c.n2)
        if i1 is not None:
            A[i1, i1] += g
        if i2 is not None:
            A[i2, i2] += g
        if i1 is not None and i2 is not None:
            A[i1, i2] -= g
            A[i2, i1] -= g

    # 电压源 stamps：新增支路电流变量（正方向为正端 -> 负端，穿过电源）
    for k, c in enumerate(vsources):
        row = n_nodes + k
        i1 = node_index.get(c.n1)
        i2 = node_index.get(c.n2)
        if i1 is not None:
            A[i1, row] += 1.0
            A[row, i1] = 1.0
        if i2 is not None:
            A[i2, row] -= 1.0
            A[row, i2] = -1.0
        z[row] = c.value

    aug = np.hstack((A, z.reshape(-1, 1)))
    rank_a = int(np.linalg.matrix_rank(A))
    rank_aug = int(np.linalg.matrix_rank(aug))

    if rank_aug > rank_a:
        return {
            "status": "infeasible",
            "summary": "网络无解：元件约束相互矛盾（例如两个电压不同的理想电压源直接并联）。"
                       "按要求不展示任何数值结果。",
            "rank": rank_a,
            "rank_augmented": rank_aug,
            "unknowns": size,
        }

    if rank_a < size:
        return {
            "status": "infinite",
            "summary": "网络存在无穷多解：存在未接地、也未被电压源固定电位的浮地部分，"
                       "其整体电位可自由取值。按要求不展示任意一个数值解。",
            "rank": rank_a,
            "rank_augmented": rank_aug,
            "unknowns": size,
        }

    # 满秩：唯一解
    try:
        x = np.linalg.solve(A, z)
    except np.linalg.LinAlgError:
        x, *_ = np.linalg.lstsq(A, z, rcond=None)

    voltages = x[:n_nodes]
    currents = []
    vk = {c.name: n_nodes + k for k, c in enumerate(vsources)}
    for c in components:
        if c.kind == "R":
            v1 = 0.0 if c.n1 == 0 else voltages[node_index[c.n1]]
            v2 = 0.0 if c.n2 == 0 else voltages[node_index[c.n2]]
            current = float((v1 - v2) / c.value)
        else:
            current = float(x[vk[c.name]])
        currents.append({
            "name": c.name,
            "kind": c.kind,
            "from_node": c.n1,
            "to_node": c.n2,
            "current": current,
            "line": c.line,
        })

    node_voltages = [{"node": 0, "voltage": 0.0}]
    node_voltages += [
        {"node": node, "voltage": float(voltages[i])}
        for i, node in enumerate(nodes)
    ]
    node_voltages.sort(key=lambda item: item["node"])

    return {
        "status": "unique",
        "summary": "网络存在唯一解。",
        "rank": rank_a,
        "unknowns": size,
        "node_voltages": node_voltages,
        "currents": currents,
    }
