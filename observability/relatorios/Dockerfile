FROM node:22-slim

WORKDIR /app

COPY observability/relatorios/package.json ./
RUN npm install --no-audit --no-fund

RUN mkdir -p public
COPY observability/relatorios/index.tsx ./pages/index.tsx
COPY observability/relatorios/observabilidade-page.tsx ./observabilidade-page.tsx
COPY observability/relatorios/pages/observabilidade.tsx ./pages/observabilidade.tsx
COPY observability/relatorios/observabilidades.ts ./observabilidades.tsx
COPY observability/relatorios/pages/api/phoenix.ts ./pages/api/phoenix.ts
COPY observability/relatorios/next.config.mjs ./
COPY observability/relatorios/login.json ./public/login.json

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
