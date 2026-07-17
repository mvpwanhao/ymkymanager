# 云煤矿业产销量管理系统 — 生产镜像（FastAPI + Uvicorn）
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# 国内网络：将 bookworm / security 默认源换为清华镜像后再 apt install。
ENV DEBIAN_FRONTEND=noninteractive
RUN set -eux; \
    MIR="https://mirrors.tuna.tsinghua.edu.cn"; \
    for f in /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list; do \
      [ -f "$f" ] || continue; \
      sed -i \
        -e "s|http://deb.debian.org/debian|${MIR}/debian|g" \
        -e "s|https://deb.debian.org/debian|${MIR}/debian|g" \
        -e "s|http://security.debian.org/debian-security|${MIR}/debian-security|g" \
        -e "s|https://security.debian.org/debian-security|${MIR}/debian-security|g" \
        "$f"; \
    done; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    gcc \
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
COPY scripts ./scripts

RUN mkdir -p /app/data /app/data/runtime /app/data/exports

# 创建非 root 用户，UID=1000 匹配宿主机 wanhao，确保 volume 写入文件属主正确
RUN useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# 监听 0.0.0.0 以便 Docker 端口映射到局域网
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
