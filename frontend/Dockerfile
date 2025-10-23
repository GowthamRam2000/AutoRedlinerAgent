# Frontend container for Auto Redliner (India)
# - Serves static files via nginx on port 80
# - At startup, injects API_BASE_URL into config.js

FROM nginx:alpine

WORKDIR /usr/share/nginx/html

# Build context is the frontend/ folder, so copy relative paths
COPY . .

# Entry script replaces API_BASE_URL in config.js if env is set
COPY docker-entrypoint.sh /docker-entrypoint.d/10-config.sh
RUN chmod +x /docker-entrypoint.d/10-config.sh

EXPOSE 80

# nginx base image runs nginx in foreground by default
