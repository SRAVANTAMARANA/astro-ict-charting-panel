FROM nginx:stable-alpine
# Copy our nginx config into container location
COPY nginx.conf /etc/nginx/nginx.conf
# Copy static public files (if present)
COPY public /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
