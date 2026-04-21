FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

ARG VITE_API_BASE_URL=http://api:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

EXPOSE 5173

CMD ["npm", "run", "dev"]
