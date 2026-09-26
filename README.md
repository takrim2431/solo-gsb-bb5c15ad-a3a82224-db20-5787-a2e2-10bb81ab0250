# 直流电阻网络求解器

基于 **Python + FastAPI + NumPy + 原生 JavaScript** 的直流电阻网络求解网页。
后端使用**改进节点法（Modified Nodal Analysis, MNA）**建立线性方程组，
用 SVD 秩判定区分**唯一解 / 无解 / 无穷多解**；支持两端均不接地的**浮地电压源**。

## 一条命令启动

需要已安装 Docker 与 Docker Compose（v2）：

```bash
docker compose up --build
```

启动后在浏览器访问：

> **http://localhost:8000**

- 网页端口：**8000**
- 停止服务：`Ctrl+C`；后台运行：`docker compose up --build -d`；删除：`docker compose down`

容器启动时会通过 `docker-entrypoint.sh` 自动执行 `pip install -r requirements.txt`
安装依赖并完成初始化，然后启动 uvicorn。

## 必要配置

| 配置项 | 值 | 说明 |
| --- | --- | --- |
| 容器端口 | `8000` | uvicorn 监听 `0.0.0.0:8000` |
| 宿主机端口映射 | `8000:8000` | 在 `docker-compose.yml` 中修改，例如 `9000:8000` 后访问 http://localhost:9000 |
| 依赖 | `requirements.txt` | FastAPI、uvicorn、NumPy、pydantic，容器启动时安装 |

无需数据库或其它外部服务。

## 网表输入格式

每行一个元件，字段之间用空格分隔；空行与以 `#` 开头的行被忽略。

```
R 名称 节点1 节点2 欧姆值
V 名称 正端节点 负端节点 伏特值
```

- **节点 0 为参考地（0 V）**，节点编号为不小于 0 的整数。
- **电阻值必须为正**（R 行欧姆值 ≤ 0 会报错并标明行号）。
- 电压源两端都可以不接地（浮地源），伏特值允许为负数。
- **电流正方向沿元件输入方向**：
  - 电阻：节点1 → 节点2，`I = (V节点1 − V节点2) / R`
  - 电压源：正端 → 负端（负值表示实际方向相反，例如电源向外供电）

结果区域展示：

1. **节点电压表**（含节点 0 = 0 V）；
2. **元件电流表**，列出每个元件沿其输入方向的电流；
3. 状态徽标：**唯一解 / 无解 / 无穷多解**——后两种情况**不会展示任何数值结果**。

### 判定规则

设 MNA 方程组为 `A x = z`，对增广矩阵 `[A | z]` 做奇异值分解并比较秩：

- `rank(A) = rank([A|z]) = 未知量数`：**唯一解**，展示电压、电流；
- `rank(A) < rank([A|z])`：**无解**（如两个不同电压的理想电压源直接并联），不展示数值；
- `rank(A) = rank([A|z]) < 未知量数`：**无穷多解**（如未接地、未被电压源约束的浮岛），不展示任意一个数值解。

## 本地开发（不使用 Docker）

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 路由 / API
│   ├── solver.py            # 网表解析 + MNA 建模 + 秩判定与求解
│   └── static/
│       ├── index.html       # 网页结构
│       ├── style.css        # 样式
│       └── app.js           # 原生 JS：行号、错误标注、示例、结果渲染
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh     # 启动时安装依赖并初始化
├── requirements.txt
└── test_solver.py           # 求解器端到端自测
```
