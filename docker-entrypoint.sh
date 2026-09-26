#!/bin/sh
# 容器启动入口：确保依赖已安装（镜像构建时已装，此处为幂等保障），随后启动服务。
set -e

pip install --no-cache-dir -r /app/requirements.txt

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
