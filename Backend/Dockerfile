FROM node:18-alpine

WORKDIR /usr/src/app

COPY package.json package.json
RUN npm install --production

COPY index.js index.js

ENV PORT=8000

EXPOSE 8000

CMD ["node", "index.js"]
