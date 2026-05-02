# 云煤矿业产销量管理系统 — 生产镜像（FastAPI + Uvicorn）
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 构建依赖 + Kaleido/Chromium headless（Plotly 导出 PNG）常见动态库
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libcairo2 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    fonts-liberation \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# docker-compose.yml 为国内网络传入 PIP_INDEX_URL（清华源）；默认仍为官方 PyPI
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install -i "${PIP_INDEX_URL}" --default-timeout=300 --no-cache-dir -U pip && \
    pip install -i "${PIP_INDEX_URL}" --default-timeout=300 --no-cache-dir -r requirements.txt

COPY VERSION .
COPY app ./app
COPY templates ./templates
COPY static ./static

RUN mkdir -p /app/data /app/data/runtime /app/data/exports

EXPOSE 8080

# 监听 0.0.0.0 以便 Docker 端口映射到局域网
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
