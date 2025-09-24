FROM nginx:stable-alpine

# Drop our nginx conf into the container
COPY conf.d/default.conf /etc/nginx/conf.d/default.conf

# Copy static site (if you have one). Create frontend/public/index.html for quick testing
COPY public /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
