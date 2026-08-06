# Development-focused Dockerfile: runs the Vite dev server with hot reload,
# matching docker-compose.yml's volume-mounted local dev workflow.
#
# For a production image, replace this with a multi-stage build that runs
# `npm run build` and serves the static `dist/` output via nginx — a natural
# addition once Phase 1 infra is validated and you're ready to deploy.
FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
