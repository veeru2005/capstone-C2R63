# Single-container build: React dashboard + FastAPI API on ONE port.
# Used for online hosting (Render / Railway / any Docker host):
#   docker build -t finops . && docker run -p 8000:8000 finops   ->  http://localhost:8000
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
RUN rm -f finops.db finops_live.db
COPY --from=web /web/dist ./static
ENV FRONTEND_DIST=/app/static \
    FINOPS_DB_PATH=/data/finops.db \
    CORS_ORIGINS=*
RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "scripts/docker_entrypoint.sh"]
