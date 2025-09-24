FROM nginx:stable-alpine
# remove default nginx index to avoid stale copy (not strictly required, but safe)
RUN rm -rf /usr/share/nginx/html/*
COPY . /usr/share/nginx/html
# ensure permissions
RUN chmod -R a+r /usr/share/nginx/html
# keep default nginx config
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
