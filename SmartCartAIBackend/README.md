# SmartCart AI Backend

Simple Java (Spring Boot) REST API that reads data from PostgreSQL and exposes it via REST endpoints. Swagger UI is included for testing.

## Prerequisites

- Java 17+
- Maven
- PostgreSQL with the SmartCart schema (see `../database/schema.sql` or the schema from Team1_LowCodeAgenthon)

## Configuration

The `src/main/resources/application.properties` file is already configured with:

- `spring.datasource.url` – JDBC URL: `jdbc:postgresql://localhost:5432/smartcart_ai`
- `spring.datasource.username` – DB user: `meghanarendrasimha`
- `spring.datasource.password` – DB password: `Welcome@123`

If you need to change these, edit `src/main/resources/application.properties`.

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

## Phase 1 Security (JWT + Rate Limit + Agent Token)

Set these environment variables before starting backend:

```bash
export JWT_ENFORCE=true
export JWT_SECRET="replace-with-strong-secret-at-least-32-chars"
export JWT_EXP_MINUTES=120
export APP_AUTH_USERNAME=admin
export APP_AUTH_PASSWORD="replace-this-password"
export RATE_LIMIT_MAX_REQUESTS=120
export RATE_LIMIT_WINDOW_SECONDS=60
export AGENT_SHARED_TOKEN="replace-with-strong-internal-token"
```

Get a JWT:

```bash
curl -X POST http://localhost:8080/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"replace-this-password"}'
```

Use token:

```bash
curl http://localhost:8080/api/inventory \
  -H "Authorization: Bearer <access_token>"
```

Notes:
- If `JWT_ENFORCE=false` (default), JWT validation is not enforced.
- Python agents enforce `X-Agent-Token` when `AGENT_SHARED_TOKEN` is set.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/inventory` | List all inventory items |
| GET | `/api/sales` | List all sales |
| GET | `/api/consumption` | List all consumption records |
| GET | `/api/demand` | List all demand predictions |
| GET | `/api/dashboard/overview` | Dashboard sales chart (7-day trend) |
| POST | `/api/agents/dashboard/item-insights` | Proxy dashboard item insights from Dashboard Agent |

## Swagger UI

After starting the app, open:

- **Swagger UI:** http://localhost:8080/swagger-ui.html  
- **OpenAPI JSON:** http://localhost:8080/api-docs  

Use Swagger UI to try the endpoints without a separate client.
