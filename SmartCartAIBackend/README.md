# SmartCart AI Backend

Simple Java (Spring Boot) REST API that reads data from PostgreSQL and exposes it via REST endpoints. Swagger UI is included for testing.

## Prerequisites

- Java 17+
- Maven
- PostgreSQL with the SmartCart schema (see `../database/schema.sql` or the schema from Team1_LowCodeAgenthon)

## Configuration

Edit `src/main/resources/application.properties`:

- `spring.datasource.url` – JDBC URL (default: `jdbc:postgresql://localhost:5432/smartcartai`)
- `spring.datasource.username` – DB user (default: `postgres`)
- `spring.datasource.password` – DB password (default: `postgres`)

## Build & Run

No need to install Maven—use the included Maven Wrapper:

```bash
cd SmartCartAIBackend
./mvnw spring-boot:run
```

Or build a JAR and run it:

```bash
./mvnw clean package
java -jar target/SmartCartAIBackend-1.0.0.jar
```

(If you have Maven installed, you can use `mvn` instead of `./mvnw`.)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/inventory` | List all inventory items |
| GET | `/api/sales` | List all sales |
| GET | `/api/consumption` | List all consumption records |
| GET | `/api/demand` | List all demand predictions |

## Swagger UI

After starting the app, open:

- **Swagger UI:** http://localhost:8080/swagger-ui.html  
- **OpenAPI JSON:** http://localhost:8080/api-docs  

Use Swagger UI to try the endpoints without a separate client.
