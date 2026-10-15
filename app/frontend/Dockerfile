# 1) compila la SPA (las pruebas se ejecutan antes, en local: aqui alargarian el build)
FROM node:22.23.3-alpine AS build
WORKDIR /srv/frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# 2) Caddy sirve los estaticos y hace de proxy a la API; solo lleva el Caddyfile y dist
FROM caddy:2.8.4
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /srv/frontend/dist /srv/web
