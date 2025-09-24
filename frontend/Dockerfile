# Use Nginx as base image
FROM nginx:1.28-alpine

# Copy custom nginx.conf
COPY nginx.conf /etc/nginx/nginx.conf

# Copy frontend files into nginx html directory
COPY ictpanel.html /usr/share/nginx/html/
COPY static/ /usr/share/nginx/html/static/
COPY app.js /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/

# Expose port
EXPOSE 3000

# Run nginx
CMD ["nginx", "-g", "daemon off;"]
