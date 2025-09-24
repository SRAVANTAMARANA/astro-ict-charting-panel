FROM nginx:1.28-alpine
# Remove default conf and add our nginx.conf
COPY nginx.conf /etc/nginx/nginx.conf
# Copy any static site files if you have them (public/)
COPY public /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
