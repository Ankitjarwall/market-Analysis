# syntax=docker/dockerfile:1
# ── Stage 1: Build ──────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install --prefer-offline

COPY . .
# Empty VITE_API_URL → frontend uses relative URLs → nginx proxies /api/ /auth/ /ws/ to backend
RUN VITE_API_URL="" npm run build

# ── Stage 2: Serve with nginx ────────────────────────────
FROM nginx:1.27-alpine AS runner

RUN rm -rf /usr/share/nginx/html/*

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
