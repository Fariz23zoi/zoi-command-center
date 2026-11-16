# ZOI YOUTUBE INTELLIGENCE — image untuk mode online (Render free plan).
# Tahap 1: build frontend (Node 22). Tahap 2: backend Python 3.12 + hasil build frontend.

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/apps/web/package.json apps/web/
COPY frontend/packages/avatar/package.json packages/avatar/
COPY frontend/packages/api-client/package.json packages/api-client/
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run --workspace @zoi/web build

FROM python:3.12-slim
WORKDIR /zoi
ENV PYTHONUNBUFFERED=1 ZOI_MODE=online
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /build/apps/web/dist frontend/apps/web/dist
WORKDIR /zoi/backend
# Port dari $PORT (Render) — dibaca app sendiri; EXPOSE hanya dokumentasi.
EXPOSE 10000
CMD ["python", "-m", "app"]
