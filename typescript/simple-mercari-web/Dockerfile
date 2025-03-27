FROM node:20-alpine

RUN addgroup -S mercari && adduser -S trainee -G mercari

WORKDIR /app

COPY package.json package-lock.json ./

RUN chown -R trainee:mercari /app

USER trainee

RUN npm ci

COPY . .

USER root

RUN rm -rf /app/node_modules/.vite && mkdir -p /app/node_modules/.vite && chown -R trainee:mercari /app/node_modules/.vite
RUN rm -rf /app/node_modules/.vite-temp && mkdir -p /app/node_modules/.vite-temp && chown -R trainee:mercari /app/node_modules/.vite-temp

USER trainee

EXPOSE 3000

CMD ["npm", "start"]
