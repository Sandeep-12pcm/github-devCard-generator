FROM nginx:alpine

# Copy index.html into a template location so it can be dynamically compiled
COPY index.html /usr/share/nginx/html/index.html.template

# Expose the standard Nginx HTTP port
EXPOSE 80

# Replace the $BACKEND_URL variable inside the index.html.template on container start,
# outputs to index.html, and executes the Nginx process in the foreground.
CMD ["/bin/sh", "-c", "envsubst '${BACKEND_URL}' < /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html && exec nginx -g 'daemon off;'"]
