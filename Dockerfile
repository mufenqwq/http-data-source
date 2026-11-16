# 构建集群访问不了 Docker Hub，mirrors.tencent.com 的镜像仓库会返回 403。
# 腾讯云镜像加速可匿名拉取官方 Python 镜像。
FROM mirror.ccs.tencentyun.com/library/python:3.11-slim-bookworm

USER root
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PIP_INDEX_URL=https://mirrors.tencent.com/pypi/simple \
    PIP_TRUSTED_HOST=mirrors.tencent.com

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py start.sh /app/

EXPOSE 5000

CMD ["bash", "/app/start.sh"]
