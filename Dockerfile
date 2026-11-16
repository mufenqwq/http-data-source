# 这套 PaaS 构建集群拉取 mirrors.tencent.com 的镜像仓库会返回 403，使用 Docker Hub 官方镜像。
FROM python:3.11-slim-bookworm

USER root
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    PIP_TRUSTED_HOST=mirrors.cloud.tencent.com

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py start.sh /app/

EXPOSE 5000

CMD ["bash", "/app/start.sh"]
