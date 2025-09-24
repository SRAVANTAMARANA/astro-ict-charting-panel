FROM nginx:alpine

# copy frontend build files (ictpanel.html, static/)
COPY . /usr/share/nginx/html

# replace default nginx.conf with ours
COPY nginx.conf /etc/nginx/nginx.conf
