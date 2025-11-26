# Sample Application - Dockerfile
# Multi-stage build for React + Vite frontend and Node.js backend

# Stage 1: Build frontend
FROM node:18-alpine as frontend-builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build frontend (production build)
RUN npm run build

# Stage 2: Production image with both frontend and backend
FROM node:18-alpine as production

WORKDIR /app

# Install production dependencies only
COPY package*.json ./
RUN npm ci --only=production

# Copy built frontend from builder
COPY --from=frontend-builder /app/dist ./dist

# Copy backend server and other necessary files
COPY server.js ./
COPY public ./public

# Create non-root user
RUN addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose ports
EXPOSE 5173 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5173 || exit 1

# Start both frontend (preview) and backend
CMD ["sh", "-c", "node server.js & npm run preview -- --host 0.0.0.0 --port 5173"]
