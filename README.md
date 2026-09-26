# 直流电阻网络求解器

基于 **Python + FastAPI + NumPy + 原生 JavaScript** 的直流电阻网络求解网页。
输入由电阻与理想电压源构成的网表，后端采用改进节点分析（MNA）求解，
支持浮地电压源，并严格区分 **唯一解 / 无解 / 多解**（后两者不输出任何数值解）。

## 一、启动（单条命令）

```bash
docker compose up --build
```

启动过程会自动完成依赖安装与初始化，无需其他操作。

## 二、访问

- 网页地址：**http://localhost:8000**
- 健康检查：`GET http://localhost:8000/api/health`
- 求解接口：`POST http://localhost:8000/api/solve`，请求体 `{"netlist": "..."}`

## 三、配置（可选）

| 配置项 | 位置 | 说明 |
| --- | --- | --- |
| 对外端口 | `docker-compose.yml` 中 `ports: "8000:8000"` | 修改**左侧**端口即可，例如改为 `"8080:8000"` 后访问 http://localhost:8080 |
| 容器内端口 | `docker-compose.yml` 中环境变量 `PORT` | 默认 8000，一般无需修改 |

## 四、输入格式

每行一个元件，字段以空白分隔，`#` 之后为注释，空行忽略：

```
R 名称 节点1 节点2 欧姆值        # 电阻，阻值必须为正数
V 名称 正端节点 负端节点 伏特值   # 理想电压源，可浮地
```

- 节点为**非负整数**，节点 `0` 为地；
- 元件名以字母/下划线开头，仅含字母、数字、下划线，且不可重复；
- 数值支持科学计数法（如 `4.7e3`）；
- 输入错误会在结果区**标明行号**。

示例（分压器）：

```
V V1 1 0 10
R R1 1 2 1000
R R2 2 0 2000
```

## 五、输出说明

- **唯一解**：展示各节点电压（含地节点 0 V）与每个元件沿输入方向的电流
  （电阻：节点1 → 节点2；电压源：正端 → 负端）；
- **无解**：约束冲突（如不同电压的电压源并联），不展示数值解；
- **多解**：存在自由度（如浮地子电路缺少电位参考），不展示任意数值解。

网页内置 5 个示例（分压器、惠斯通电桥、浮地电压源、无解、多解），
点击「载入示例」即可计算，修改网表后点「求解」（或 Ctrl+Enter）重新计算。

## 六、本地开发（不用 Docker）

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 七、项目结构

```
app/
  main.py            # FastAPI 入口与 API
  solver.py          # 网表解析 + MNA 求解（NumPy）
  static/            # 前端（原生 HTML/CSS/JS）
    index.html
    app.js
    style.css
requirements.txt     # Python 依赖
Dockerfile           # 镜像构建（安装依赖、健康检查）
docker-compose.yml   # 单服务编排
docker-entrypoint.sh # 启动入口：幂等安装依赖并启动 uvicorn
```
