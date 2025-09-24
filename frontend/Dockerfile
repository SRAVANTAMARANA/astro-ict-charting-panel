# frontend/Dockerfile
FROM nginx:1.28-alpine

# copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# copy static frontend files
COPY ictpanel.html /usr/share/nginx/html/ictpanel.html
COPY app.js /usr/share/nginx/html/app.js
COPY styles.css /usr/share/nginx/html/styles.css
COPY static/ /usr/share/nginx/html/static/

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
