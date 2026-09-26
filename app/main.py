"""FastAPI 入口：提供求解 API 并托管前端静态页面。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .solver import parse_netlist, solve_network

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="直流电阻网络求解器", version="1.0.0")


class SolveRequest(BaseModel):
    netlist: str = Field(..., description="网表文本，每行一个元件")


@app.post("/api/solve")
def api_solve(req: SolveRequest) -> dict:
    """解析并求解网表。解析错误、无解、多解均以 200 返回，由 status 字段区分。"""
    elements, errors = parse_netlist(req.netlist)
    if errors:
        return {"status": "error", "errors": errors}
    if not elements:
        return {
            "status": "error",
            "errors": [{"line": None, "message": "网络为空：请至少输入一个元件"}],
        }
    return solve_network(elements)


@app.get("/api/health")
def api_health() -> dict:
    return {"status": "ok"}


# 静态页面挂在根路径（注册在 API 路由之后，不影响 /api/*）
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
