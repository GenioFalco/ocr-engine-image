# Сборка
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Раздача готовой статики
FROM nginx:alpine
# Удаляем стандартный конфиг
RUN rm /etc/nginx/conf.d/default.conf
# Добавляем очень простой конфиг для React (SPA)
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
