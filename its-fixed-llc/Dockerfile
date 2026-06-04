FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html
# nginx.conf is needed in the build context (above) but must not be served publicly
RUN rm -f /usr/share/nginx/html/nginx.conf

EXPOSE 80
