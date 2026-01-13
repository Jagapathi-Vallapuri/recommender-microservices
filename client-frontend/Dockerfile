# syntax=docker/dockerfile:1.6

FROM node:20-alpine AS builder

WORKDIR /app

ENV NODE_OPTIONS=--dns-result-order=ipv4first

ARG VITE_GATEWAY_URL=http://localhost:9000
ENV VITE_GATEWAY_URL=$VITE_GATEWAY_URL

COPY package*.json ./
RUN npm config set registry https://registry.npmjs.org/ && npm ping --loglevel=warn
RUN --mount=type=cache,target=/root/.npm \
		sh -lc 'if [ -f package-lock.json ]; then \
			npm ci --loglevel=verbose --no-audit --no-fund; \
		else \
			npm install --loglevel=verbose --no-audit --no-fund; \
		fi'

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
