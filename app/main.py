"""FastAPI 入口：直流电阻网络求解服务。"""

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .solver import parse_netlist, solve_network

app = FastAPI(title="直流电阻网络求解器", version="1.0.0")


class SolveRequest(BaseModel):
    netlist: str


@app.post("/api/solve")
def solve(req: SolveRequest):
    components, errors = parse_netlist(req.netlist)
    if errors:
        return JSONResponse({"ok": False, "errors": errors})
    result = solve_network(components)
    return {"ok": True, "result": result}


@app.get("/")
def index():
    return FileResponse("app/static/index.html")


app.mount("/static", StaticFiles(directory="app/static"), name="static")
