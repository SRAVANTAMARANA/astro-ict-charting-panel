FROM nginx:alpine

# overwrite default nginx.conf
COPY nginx.conf /etc/nginx/nginx.conf

# copy static files
COPY ictpanel.html /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
