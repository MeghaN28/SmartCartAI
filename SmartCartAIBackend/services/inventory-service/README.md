# Inventory Service

Lightweight Java REST microservice that exposes inventory APIs described in the architecture diagram.

Key endpoints:
- GET /inventory
- GET /inventory/{id}
- POST /inventory/{id}/flag
- POST /inventory/{id}/recommendation

Database: reads/writes to `database.inventory` (PK: inventory_id).

Status: placeholder files — add implementation (Spring Boot / Micronaut / Quarkus) as needed.