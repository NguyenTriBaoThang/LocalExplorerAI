FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
# The lockfile has no entry for rollup's musl (Alpine) binary; install the one matching the locked rollup version.
RUN npm install --no-save --no-audit --no-fund "@rollup/rollup-linux-x64-musl@$(node -p "require('rollup/package.json').version")"
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
