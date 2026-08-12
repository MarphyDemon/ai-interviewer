#!/bin/bash
cd "$(dirname "$0")"

# 初始化conda并激活环境
source /c/ProgramData/miniconda3/etc/profile.d/conda.sh
conda activate ai-interviewer 2>/dev/null

# Ctrl+C 清理所有子进程
trap 'kill $FRONT_PID $BACK_PID 2>/dev/null' SIGINT SIGTERM

echo "=== 启动前端 ==="
npm run dev &
FRONT_PID=$!

echo "=== 启动后端 ==="
python -m uvicorn server.main:app --reload --port 8000 &
BACK_PID=$!

echo "前端PID: $FRONT_PID  后端PID: $BACK_PID"
echo "按 Ctrl+C 全部停止"

wait
