FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY sitio/ /usr/share/nginx/html/
EXPOSE 8080
