# FinShield AI - Frontend Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files first for better caching
COPY platform-app/package*.json ./
RUN npm ci

# Copy frontend code
COPY platform-app/ ./

# Set build-time environment variables for API proxy
# These will be baked into the standalone build
ENV API_URL=http://backend:8091
ENV NEXT_PUBLIC_API_URL=http://localhost:8091

# Build the application
RUN npm run build

# Expose port
EXPOSE 3000

# Set runtime environment variables
ENV NODE_ENV=production

# Run the application
CMD ["npm", "start"]
