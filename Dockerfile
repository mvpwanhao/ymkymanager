# 云煤矿业产销量管理系统 — 生产镜像（FastAPI + Uvicorn）
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 默认 sans-serif 优先 CJK（供 Kaleido 内置 Chromium + fontconfig 选字）
RUN mkdir -p /etc/fonts/conf.d
COPY docker/fontconfig/65-ymky-cjk-sans.conf /etc/fonts/conf.d/65-ymky-cjk-sans.conf

# 国内网络：将 bookworm / security 默认源换为清华镜像后再 apt install（含 Kaleido/Chromium 所需系统库）。
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
    at-spi2-core \
    dbus \
    gcc \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    fontconfig \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    libgbm1 \
    libglib2.0-0 \
    libgomp1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    && fc-cache -fv \
    && v="$(fc-list | grep -iE 'WenQuanYi Micro Hei|Noto Sans CJK SC' | head -n1)" \
    && test -n "$v" \
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
