# frontend/Dockerfile
FROM nginx:stable-alpine
# Remove default nginx index to be safe and copy our static app
RUN rm -f /usr/share/nginx/html/*
COPY . /usr/share/nginx/html
# keep default nginx.conf from image; static files served out of /usr/share/nginx/html
