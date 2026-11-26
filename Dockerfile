FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HARVESTSHIELD_DB=/app/data/harvestshield.sqlite3
WORKDIR /app
COPY requirements.txt requirements-hosted.txt ./
RUN pip install --no-cache-dir -r requirements-hosted.txt \
    && groupadd --gid 10001 harvestshield \
    && useradd --uid 10001 --gid 10001 --no-create-home harvestshield \
    && mkdir /app/data && chown 10001:10001 /app/data
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 scripts ./scripts
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/health', timeout=3)"
CMD ["python", "-m", "scripts.serve", "--host", "0.0.0.0"]
