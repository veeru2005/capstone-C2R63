FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY finops ./finops
COPY config ./config
COPY fixtures ./fixtures
COPY scripts ./scripts
COPY main.py .
ENV FINOPS_DB_PATH=/data/finops.db
VOLUME /data
EXPOSE 8000
CMD ["sh", "scripts/docker_entrypoint.sh"]
