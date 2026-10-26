# ==============================================================================
# Stage 1: Build the React / Vite Frontend
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/web/frontend

# Install frontend dependencies
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci

# Copy frontend source and compile static production build to dist/
COPY web/frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Build the Pixi Python & Conda Environment Prefix
# ==============================================================================
FROM ghcr.io/prefix-dev/pixi:latest AS pixi-builder
WORKDIR /app

# Copy pixi manifest and locked resolution
COPY pixi.toml pixi.lock ./

# Install locked dependencies into the default environment prefix (.pixi/envs/default)
RUN pixi install --locked --frozen -e default

# ==============================================================================
# Stage 3: Production Runtime
# ==============================================================================
FROM ghcr.io/prefix-dev/pixi:latest AS runner
WORKDIR /app

# Runtime configuration
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    UVICORN_RELOAD=false \
    CONDA_PREFIX=/app/.pixi/envs/default \
    PATH="/app/.pixi/envs/default/bin:$PATH"

# Copy Pixi environment prefix and workspace specifications
COPY --from=pixi-builder /app/.pixi/envs/default /app/.pixi/envs/default
COPY pixi.toml pixi.lock ./

# Copy compiled frontend from Stage 1 into the expected location for FastAPI static mounting
COPY --from=frontend-builder /app/web/frontend/dist /app/web/frontend/dist

# Copy application source code and assets
COPY assets /app/assets
COPY pipeline /app/pipeline
COPY web/backend /app/web/backend

# Ensure directories for outputs and assets exist
RUN mkdir -p /app/outputs /app/assets/gameplay /app/assets/fonts

# Expose web application port
EXPOSE 8000

# Start web application using pixi task
CMD ["pixi", "run", "ui-server"]
