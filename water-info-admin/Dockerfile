# Build stage
ARG DOCKER_REGISTRY_PREFIX=docker.m.daocloud.io/library/
FROM ${DOCKER_REGISTRY_PREFIX}alpine:3.20 AS build
WORKDIR /app

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories && \
    apk add --no-cache nodejs npm && \
    npm config set registry https://registry.npmmirror.com

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM ${DOCKER_REGISTRY_PREFIX}nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
