# AgentBench-Lite dashboard image (Phase 11.2). Build from the dashboard folder:
#     docker build -t agentbench-dashboard dashboard
#
# Two stages: Node builds the React app into plain files (dist/), then only those files are copied into a
# small nginx image. Node, node_modules and the source code are NOT in the final image.

# ---- stage 1: build -------------------------------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

# Dependencies first: this slow layer is reused as long as package*.json do not change.
# `npm ci` installs exactly what package-lock.json says (no surprises, fails if the lock is out of date).
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# Where the BROWSER finds the API. Baked in at build time (Vite replaces it in the code), so it must be an
# address your browser can reach: the API published on 127.0.0.1:8000.
ARG VITE_API_BASE=http://127.0.0.1:8000
ENV VITE_API_BASE=$VITE_API_BASE
# Same build as on your computer: type check, Vite build, and the check that /design is not included.
RUN npm run build

# ---- stage 2: serve -------------------------------------------------------------------------------------
# Official nginx image that runs as a normal user (uid 101) instead of root, listening on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
