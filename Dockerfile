FROM python:3.13-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
COPY app.py /app/app.py
RUN mkdir -p /app/config /app/output /app/logs \
    && chown -R app:app /app/config /app/output /app/logs \
    && chmod 755 /app /app/config /app/output /app/logs
USER app
EXPOSE 8787
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=3).read()"
CMD ["python", "/app/app.py"]
