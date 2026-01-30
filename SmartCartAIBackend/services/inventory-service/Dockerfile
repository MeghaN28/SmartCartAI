# Placeholder Dockerfile for Inventory Service
FROM openjdk:17-jdk-slim
WORKDIR /app
COPY build/libs/inventory-service.jar ./inventory-service.jar
EXPOSE 8080
ENTRYPOINT ["java","-jar","/app/inventory-service.jar"]
