# ---- Build Stage ----
ARG DOCKER_REGISTRY_PREFIX=docker.m.daocloud.io/library/
FROM ${DOCKER_REGISTRY_PREFIX}alpine:3.20 AS builder
WORKDIR /build

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories && \
    apk add --no-cache openjdk17-jdk maven

COPY settings-docker.xml /root/.m2/settings.xml
COPY pom.xml ./
RUN mvn -s /root/.m2/settings.xml dependency:go-offline -B

COPY src ./src
RUN mvn -s /root/.m2/settings.xml package -DskipTests -B && \
    java -Djarmode=layertools -jar target/*.jar extract --destination extracted

# ---- Runtime Stage ----
FROM ${DOCKER_REGISTRY_PREFIX}alpine:3.20
WORKDIR /app

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories && \
    apk add --no-cache openjdk17-jre-headless

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder /build/extracted/dependencies/ ./
COPY --from=builder /build/extracted/spring-boot-loader/ ./
COPY --from=builder /build/extracted/snapshot-dependencies/ ./
COPY --from=builder /build/extracted/application/ ./

RUN mkdir -p /app/logs && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8080

ENV JAVA_OPTS="-Xms256m -Xmx512m -XX:+UseG1GC"
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.launch.JarLauncher"]
