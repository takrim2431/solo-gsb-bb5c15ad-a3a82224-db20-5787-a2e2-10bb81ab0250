"""端到端验证：解析 + 求解，覆盖唯一解/无解/多解与输入错误。"""
import numpy as np

from app.solver import parse_netlist, solve_network


def run(text):
    comps, errs = parse_netlist(text)
    if errs:
        return {"errors": errs}
    return solve_network(comps)


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok:", msg)


# 1) 基本分压 12V, 1k+2k -> V2=8V, I=4mA
print("[1] 分压电路（唯一解）")
r = run("V Vs 1 0 12\nR R1 1 2 1000\nR R2 2 0 2000\n")
expect(r["status"] == "unique", "状态 unique")
volts = {nv["node"]: nv["voltage"] for nv in r["node_voltages"]}
expect(abs(volts[0] - 0) < 1e-9, "V0 = 0")
expect(abs(volts[1] - 12) < 1e-9, "V1 = 12")
expect(abs(volts[2] - 8) < 1e-9, f"V2 = 8（实际 {volts[2]:.6g}）")
cur = {c["name"]: c["current"] for c in r["currents"]}
expect(abs(cur["R1"] - 0.004) < 1e-12, f"I(R1)=4mA（实际 {cur['R1']:.6g}）")
expect(abs(cur["R2"] - 0.004) < 1e-12, f"I(R2)=4mA（实际 {cur['R2']:.6g}）")
expect(abs(cur["Vs"] - -0.004) < 1e-12, f"I(Vs)=-4mA，正→负方向（实际 {cur['Vs']:.6g}）")

# 2) 浮地电压源
print("[2] 浮地电压源（唯一解）")
r = run("V Vs 1 0 12\nR R1 1 2 2000\nR R2 2 0 4000\nV Vx 3 2 5\nR R3 3 0 1000\n")
expect(r["status"] == "unique", "状态 unique")
volts = {nv["node"]: nv["voltage"] for nv in r["node_voltages"]}
# 节点2: (12-V2)/2000 = V2/4000 + (V2+5)/1000
v2 = volts[2]
lhs = (12 - v2) / 2000
rhs = v2 / 4000 + (v2 + 5) / 1000
expect(abs(lhs - rhs) < 1e-9, f"KCL@2 满足（V2={v2:.6g}, V3={volts[3]:.6g}）")
expect(abs(volts[3] - (v2 + 5)) < 1e-9, "V3 = V2 + 5（浮地源约束）")

# 2b) 两端都浮的电压源
print("[2b] 两端全浮电压源 + 接地电阻（唯一解）")
r = run("V Vb 1 2 10\nR R1 1 0 1000\nR R2 2 0 4000\n")
expect(r["status"] == "unique", "状态 unique")
volts = {nv["node"]: nv["voltage"] for nv in r["node_voltages"]}
expect(abs(volts[1] - volts[2] - 10) < 1e-9, "V1 - V2 = 10")
i = volts[1] / 1000
expect(abs(i - (-volts[2]) / 4000) < 1e-12, "串联电流一致")

# 3) 无解
print("[3] 冲突电压源并联（无解）")
r = run("V V1 1 0 12\nV V2 1 0 9\nR R1 1 0 1000\n")
expect(r["status"] == "infeasible", "状态 infeasible")
expect("node_voltages" not in r and "currents" not in r, "不返回任何数值解")

# 3b) 浮地的冲突：两个浮地源约束矛盾
print("[3b] 浮地回路约束矛盾（无解）")
r = run("V Va 1 2 10\nV Vb 2 1 3\nR R1 1 0 100\nR R2 2 0 100\n")
expect(r["status"] == "infeasible", "状态 infeasible")
expect("node_voltages" not in r, "不返回数值")

# 4) 多解
print("[4] 纯电阻浮岛（无穷多解）")
r = run("V Vs 1 0 10\nR R1 1 0 500\nR R2 2 3 1000\nR R3 3 2 2000\n")
expect(r["status"] == "infinite", "状态 infinite")
expect("node_voltages" not in r and "currents" not in r, "不返回任意数值解")

# 4b) 等电压电压源并联 -> 电流任意 -> 多解
print("[4b] 等压电压源并联（电流不定，无穷多解）")
r = run("V V1 1 0 12\nV V2 1 0 12\nR R1 1 0 1000\n")
expect(r["status"] == "infinite", "状态 infinite")
expect("node_voltages" not in r, "不返回数值")

# 5) 错误处理与行号
print("[5] 输入错误（行号标注）")
r = run("V Vs 1 0 12\nR bad a b -5\nR R1 1 0 0\nX X1 1 0 1\nR R2 2 x 10\n")
lines = sorted(e["line"] for e in r["errors"])
expect(lines == [2, 2, 3, 4, 5], f"错误行号 {lines}")
r2 = parse_netlist("R R1 1 0 100\nR R1 2 0 200")[1]
expect(r2[0]["line"] == 2 and "重复" in r2[0]["message"], "重名错误带行号")
r3 = parse_netlist("# 只有注释\n\n")[1]
expect(r3[0]["line"] == 0, "空网络错误")

# 6) 纯地元件 0-0
print("[6] 0-0 电阻")
r = run("R R0 0 0 100")
expect(r["status"] == "unique", "唯一零解")
expect(r["currents"][0]["current"] == 0.0, "零电流")

# 7) 节点顺序与方向
print("[7] 电阻反向定义电流取反")
r = run("V Vs 1 0 5\nR Rf 0 1 10\n")
cur = {c["name"]: c["current"] for c in r["currents"]}
expect(abs(cur["Rf"] - -0.5) < 1e-12, f"Rf 方向 0→1，I=-0.5A（实际 {cur['Rf']}）")

# 8) KCL 随机网络校验
print("[8] 随机较复杂网络 KCL 校验")
rng = np.random.default_rng(42)
lines = ["V Vs 1 0 10", "R Rg 1 0 1000"]
m = 8
for i in range(30):
    a, b = rng.integers(0, m, 2)
    while a == b:
        a, b = rng.integers(0, m, 2)
    lines.append(f"R R{i} {a} {b} {rng.uniform(1, 1e4):.3f}")
# 保证与地/源连通：随机加对地电阻
for n in range(1, m):
    lines.append(f"R Rg{n} {n} 0 {rng.uniform(1e3, 5e4):.3f}")
r = run("\n".join(lines))
expect(r["status"] == "unique", "随机网络唯一解")
V = {nv["node"]: nv["voltage"] for nv in r["node_voltages"]}
# 用求解返回的各元件电流对每个非地节点做 KCL（电阻、电压源同样取 n1→n2 为正）
kcl = {n: 0.0 for n in range(1, m)}
for c in r["currents"]:
    i12 = c["current"]
    if c["from_node"] in kcl:
        kcl[c["from_node"]] -= i12
    if c["to_node"] in kcl:
        kcl[c["to_node"]] += i12
worst = max(abs(v) for v in kcl.values())
expect(worst < 1e-9, f"所有非地节点 KCL 残差 < 1e-9（最大 {worst:.2e}）")

print("\n全部通过 ✔")
