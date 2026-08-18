FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ONLINE_STUDIO_DATA_ROOT=/srv/online-paper-studio \
    ONLINE_STUDIO_SECURE_COOKIE=1 \
    ONLINE_STUDIO_PUBLIC_REGISTRATION=1 \
    ONLINE_STUDIO_TRUST_PROXY_AUTH=1

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ghostscript \
        latexmk \
        nodejs \
        poppler-utils \
        texlive-extra-utils \
        texlive-fonts-recommended \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/research-avatar
COPY . .
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 studio \
    && mkdir -p /srv/online-paper-studio \
    && chown -R studio:studio /srv/online-paper-studio

USER studio
EXPOSE 8876
VOLUME ["/srv/online-paper-studio"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8876/api/online/health', timeout=3)"

CMD ["python", "-m", "research_avatar.online_studio", "--host", "0.0.0.0", "--port", "8876"]
