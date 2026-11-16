# 蓝鲸测试环境的构建集群使用内部基础镜像。
# 如果构建机只能拉公网镜像，把下面这一行改成：
# FROM python:3.11-slim-bookworm
FROM mirrors.tencent.com/blueking/python:3.11.14-ts4

USER root
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PIP_INDEX_URL=https://mirrors.tencent.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.tencent.com

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py start.sh /app/

EXPOSE 5000

CMD ["bash", "/app/start.sh"]
