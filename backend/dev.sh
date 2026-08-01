#!/usr/bin/env bash
# 开发后端启动脚本
#
# 用法：bash dev.sh            # 启动（自动清理占用 8000 的旧实例）
#       bash dev.sh --reload   # 加 --reload 自动热重载
#
# 说明：
# - 环境变量从 backend/.env 读取（pydantic-settings 自动加载），无需内联传参
# - 先杀掉本项目的旧 uvicorn 实例，避免 "address already in use"
# - 必须加 env -u PYTHONPATH：本机 ROS 环境会把 PYTHONPATH 指到 /opt/ros/humble，
#   导致 import 到错误版本的 sqlite3/sqlmodel
set -e
cd "$(dirname "$0")"

# 1. 清理本项目残留的 uvicorn 进程
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "[dev.sh] 已停止旧实例" || true
sleep 1

# 2. 检查 .env 是否存在
if [ ! -f .env ]; then
  echo "[dev.sh] 缺少 .env，请先：cp .env.example .env 并填入 JWT_SECRET / WX_APPID / WX_SECRET"
  exit 1
fi

# 3. 启动（前台运行，Ctrl+C 退出）
echo "[dev.sh] 启动后端 http://127.0.0.1:8000 (docs: /docs)"
exec env -u PYTHONPATH .venv/bin/uvicorn app.main:app --port 8000 "$@"
