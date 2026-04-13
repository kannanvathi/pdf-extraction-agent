FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# In production the nginx reverse-proxy handles /api/ → api:8000
# so all API calls go through a relative path (no CORS, no hard-coded host)
ENV VITE_API_URL=/api/v1
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
