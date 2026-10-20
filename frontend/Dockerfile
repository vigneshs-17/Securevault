FROM node:22-alpine
WORKDIR /app
COPY index.html style.css *.js server.mjs ./
COPY assets/ ./assets/
ENV HOST=0.0.0.0 PORT=3000
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1
CMD ["node", "server.mjs"]
