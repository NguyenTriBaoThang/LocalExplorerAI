FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
RUN node -e 'const { execFileSync } = require("node:child_process"); const { version } = require("./node_modules/rollup/package.json"); execFileSync("npm", ["install", "--no-save", "--no-audit", "--no-fund", `@rollup/rollup-linux-${process.arch}-musl@${version}`], { stdio: "inherit" })'
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
