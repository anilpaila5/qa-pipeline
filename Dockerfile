FROM node:22-alpine AS base
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-workspace.yaml tsconfig.json tsconfig.base.json ./
COPY lib/db/package.json lib/db/package.json
COPY lib/api-zod/package.json lib/api-zod/package.json
COPY lib/api-client-react/package.json lib/api-client-react/package.json
COPY artifacts/api-server/package.json artifacts/api-server/package.json
COPY artifacts/qa-pipeline/package.json artifacts/qa-pipeline/package.json
RUN pnpm install

FROM deps AS build
COPY . .
ARG PORT=3001
ARG BASE_PATH=/
ENV PORT=$PORT BASE_PATH=$BASE_PATH
RUN pnpm -r --if-present run typecheck || echo "typecheck non-blocking"
RUN pnpm -r --if-present run build

FROM node:22-alpine AS production
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app
ENV NODE_ENV=production

COPY package.json pnpm-workspace.yaml ./
COPY lib/db/package.json lib/db/package.json
COPY lib/api-zod/package.json lib/api-zod/package.json
COPY lib/api-client-react/package.json lib/api-client-react/package.json
COPY artifacts/api-server/package.json artifacts/api-server/package.json
COPY artifacts/qa-pipeline/package.json artifacts/qa-pipeline/package.json
RUN pnpm install --prod

COPY --from=build /app/artifacts/api-server/dist /app/artifacts/api-server/dist
COPY --from=build /app/artifacts/qa-pipeline/dist /app/artifacts/qa-pipeline/dist
COPY --from=build /app/lib/db/src /app/lib/db/src
COPY --from=build /app/lib/api-zod/src /app/lib/api-zod/src
COPY --from=build /app/lib/api-client-react/src /app/lib/api-client-react/src

EXPOSE 3001
CMD ["node", "--enable-source-maps", "artifacts/api-server/dist/index.mjs"]
