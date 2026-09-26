#!/bin/sh
# 容器启动时安装依赖并完成初始化，然后启动 Web 服务。
set -e

echo "[entrypoint] 安装 Python 依赖（requirements.txt）..."
pip install -r /app/requirements.txt

echo "[entrypoint] 依赖安装完成，初始化求解服务。"
echo "[entrypoint] 启动 uvicorn: $*"
exec "$@"
