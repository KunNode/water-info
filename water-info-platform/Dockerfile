ARG DOCKER_REGISTRY_PREFIX=docker.m.daocloud.io/library/

# ---- Build Stage ----
FROM ${DOCKER_REGISTRY_PREFIX}maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build

COPY pom.xml .
COPY settings.xml /root/.m2/settings.xml
RUN mvn dependency:go-offline -B

COPY src src
RUN mvn package -Dmaven.test.skip=true -B && \
    java -Djarmode=layertools -jar target/*.jar extract --destination extracted

# ---- Runtime Stage ----
FROM ${DOCKER_REGISTRY_PREFIX}eclipse-temurin:17-jre-alpine
WORKDIR /app

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
