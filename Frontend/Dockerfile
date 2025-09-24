FROM node:18-alpine

WORKDIR /usr/src/app

COPY package.json .
RUN npm ci --only=production

COPY index.html .

ENV PORT=8080
EXPOSE 8080

CMD ["npx", "http-server", ".", "-p", "8080", "-c-1", "--cors"]
