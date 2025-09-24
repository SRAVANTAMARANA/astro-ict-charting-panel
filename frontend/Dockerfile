# Use official nginx base for static frontend
FROM nginx:1.28-alpine

# Remove default conf (optional)
RUN rm /etc/nginx/conf.d/default.conf || true

# Copy our nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built frontend static files into nginx html (adjust if build artifact path differs)
# If you build frontend with npm build, adjust to copy the build output
# Example: COPY dist /usr/share/nginx/html
COPY static/ /usr/share/nginx/html/

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
