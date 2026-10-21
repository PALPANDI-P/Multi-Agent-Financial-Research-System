# =============================================================================
# Multi-Agent Financial Research System - frontend image
# =============================================================================
# Build from the repository root:
#
#     docker build -t frs-frontend:local -f frontend/Dockerfile .
#
# Stage 1 builds the Vite/React single page application, stage 2 serves the
# static bundle with nginx.  The nginx configuration proxies `/api/` to the
# backend service, therefore the SPA calls the API through a relative base
# URL (`/api/v1`).
#
# The files are copied one by one on purpose: a blanket `COPY frontend/ ./`
# would copy a local `node_modules` (and a local `dist`) into the build
# context.
#
# NOTE: this image was AUTHORED but never BUILT on the development machine
# (Docker is not installed there).  See README.md.
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1 - build the SPA
# -----------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# The lock file is copied first so that the dependency layer is cached.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Everything the build needs.
COPY frontend/index.html ./index.html
COPY frontend/tsconfig.json frontend/tsconfig.node.json ./
COPY frontend/vite.config.ts ./vite.config.ts
COPY frontend/public ./public
COPY frontend/src ./src

# The base URL of the API.  The default is the relative path that the nginx
# reverse proxy serves.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2 - serve the bundle with nginx
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine AS serve

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# The default nginx entrypoint serves the configuration and starts nginx.
CMD ["nginx", "-g", "daemon off;"]
