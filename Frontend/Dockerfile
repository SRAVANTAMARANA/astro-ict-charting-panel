FROM nginx:1.28-alpine

# Remove default html and copy our static
RUN rm -rf /usr/share/nginx/html/*

COPY public/ /usr/share/nginx/html/

# nginx.conf file will be mounted by docker-compose
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
