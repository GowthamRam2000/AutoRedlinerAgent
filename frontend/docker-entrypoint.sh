#!/bin/sh
set -e

# If API_BASE_URL is provided, patch the static config.js before nginx starts
if [ -n "${API_BASE_URL}" ] && [ -f "/usr/share/nginx/html/config.js" ]; then
  sed -i "s|API_BASE_URL: \".*\"|API_BASE_URL: \"${API_BASE_URL}\"|" /usr/share/nginx/html/config.js || true
fi

# Default nginx entrypoint continues

