#!/bin/bash
# 工作目录固定到脚本所在目录，避免开发者中心的启动目录和镜像 WORKDIR 不一致。
cd "$(dirname "$0")"

exec gunicorn app:app \
    --bind "0.0.0.0:${PORT:-5000}" \
    --workers "${WEB_WORKERS:-2}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
