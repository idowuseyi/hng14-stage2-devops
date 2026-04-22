# Stage 1: Builder - install dependencies
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

# Stage 2: Runtime - minimal image
FROM node:20-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -S app && adduser -S app -G app

# Copy node_modules from builder and application source
COPY --from=builder /app/node_modules ./node_modules
COPY . .

RUN chown -R app:app /app

USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --spider -q http://localhost:5000/health || exit 1

CMD ["node", "app.js"]
