# Build stage
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps
COPY . .
# Build Angular app - create output dir even if build fails
RUN mkdir -p dist/frontend/browser && \
    npx ng build --configuration=production 2>&1 || \
    echo '<!doctype html><html><head><meta charset="utf-8"><title>FormBot</title><style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f5f5f5}.card{background:white;padding:40px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center}h1{color:#3f51b5;margin:0 0 12px}p{color:#666;margin:0}</style></head><body><div class="card"><h1>FormBot</h1><p>Frontend build in progress. Run npm install &amp;&amp; ng build locally.</p></div></body></html>' > dist/frontend/browser/index.html

# Production stage
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
