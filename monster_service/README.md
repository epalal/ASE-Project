# Monster Service

The `monster_service` directory contains the Monster Service microservice of the
ASE project. It is a Flask application that owns the global monster catalogue,
creates and stores each player's collection, serves monster artwork, and
receives rewards from the Encounter Service.

The service exposes a JSON HTTP API and persists its data with SQLAlchemy. In a
containerized deployment it runs behind Gunicorn on port `5002` and connects to
PostgreSQL.

## Responsibilities

The service is responsible for:

- maintaining the catalogue of 16 monsters;
- returning catalogue entries and individual monster details;
- lazily assigning three starter monsters to a player on the first collection
  request;
- storing player-specific attack (`atk`) and health (`hp`) values;
- exposing an internal collection endpoint for other services;
- applying encounter rewards:
  - stat bonuses to one or more owned monsters; or
  - a newly captured catalogue species;
- making monster image assets available through HTTP;
- validating user JWTs and internal service-to-service requests.

The service does not issue JWTs. Tokens are issued by the Player/Auth Service
and verified here with its configured RSA public key.

## Directory structure

```text
monster_service/
├── app/
│   ├── __init__.py              # Flask application factory and service setup
│   ├── auth.py                  # JWT and internal-secret decorators
│   ├── initial_monsters.py      # Catalogue seed data and starter IDs
│   ├── models.py                # SQLAlchemy models and serializers
│   ├── routes/
│   │   └── monsters.py          # Catalogue, collection and reward routes
│   └── static/
│       └── assets/monsters/     # Monster artwork
├── tests/
│   ├── test_monsters.py         # Flask integration tests
│   └── bruno/                   # Bruno API request collection
├── compose.monster.yaml         # Docker Compose definition
├── Dockerfile                   # Production container image
├── openapi.yaml                 # OpenAPI 3.0 API description
└── requirements.txt             # Python dependencies
```

## Application startup

The application is created through the `create_app()` factory in
`app/__init__.py`. Startup performs the following operations:

1. Creates a Flask application.
2. Reads the database URL from `DATABASE_URL`.
3. Initializes Flask-SQLAlchemy.
4. Registers the monster blueprint.
5. Creates database tables if they do not already exist.
6. Seeds the catalogue when the `monster_catalog` table is empty.

The catalogue seed is idempotent: existing catalogue rows are not duplicated.
The default starter species are:

| Catalogue ID | Name | Element | Power | HP |
|---:|---|---|---:|---:|
| 1 | Sproutpaw | Grass | 2 | 2 |
| 5 | Drifin | Water | 2 | 3 |
| 9 | Emberbun | Fire | 3 | 2 |

## Data model

### `MonsterCatalog`

Represents a global species in the catalogue:

- `id`: integer catalogue identifier;
- `name`: unique species name;
- `element`: `Fire`, `Water`, `Dark`, or `Grass`;
- `power`: base attack value;
- `hp`: base health value;
- `image_url`: public path for the species artwork.

### `PlayerMonster`

Represents one monster owned by a player:

- `id`: ownership identifier returned as `ownership_id`;
- `player_id`: identifier of the owning player;
- `monster_id`: foreign key to `MonsterCatalog`;
- `atk` and `hp`: player-specific values;
- `acquired_at`: UTC acquisition timestamp;

The database prevents a player from owning the same species more than once.

### `AppliedReward`

Records each encounter whose reward has been applied. The encounter ID is the
primary key, so retrying the same reward request is idempotent.

## API

The complete machine-readable contract is in [`openapi.yaml`](./openapi.yaml).
Unless stated otherwise, successful responses use `application/json`.

### Health check

```http
GET /health
```

Returns the service status and service name.

### Catalogue

```http
GET /monsters
GET /monsters/{monster_id}
```

`GET /monsters` returns all 16 catalogue entries ordered by ID.
`GET /monsters/{monster_id}` returns one entry. Valid IDs are `1` through `16`;
invalid or unknown IDs return `404`.

Example catalogue entry:

```json
{
  "id": 9,
  "name": "Emberbun",
  "element": "Fire",
  "power": 3,
  "hp": 2,
  "image_url": "/assets/monsters/emberbun.png"
}
```

### Monster images

```http
GET /assets/monsters/{filename}
```

Serves files from `app/static/assets/monsters`. The same asset path is
available for catalogue `image_url` values.

### Player collection

```http
GET /collection
Authorization: Bearer <JWT>
```

The JWT must contain a `sub` or `player_id` claim. If the player has no
collection yet, the service lazily creates the three starter monsters.

Response shape:

```json
{
  "player_id": "player_123",
  "count": 3,
  "collection": [
    {
      "ownership_id": 1,
      "player_id": "player_123",
      "acquired_at": "2026-11-05T18:00:00+00:00",
      "atk": 2,
      "hp": 2,
      "monster": {
        "id": 1,
        "name": "Sproutpaw",
        "element": "Grass",
        "power": 2,
        "hp": 2,
        "image_url": "/assets/monsters/sproutpaw.png"
      }
    }
  ]
}
```

Missing, expired, malformed, or invalid JWTs return `401`.

### Internal player collection

```http
GET /internal/players/{player_id}/monsters
Authorization: Bearer <JWT>
```

This endpoint is intended for trusted services and returns the player's
collection:

```http
X-Internal-Secret: <shared-secret>
```

This endpoint is intended for trusted services. It returns the player's
collection:

```json
{
  "player_id": "player_123",
  "count": 3,
  "collection": []
}
```

Requests without the configured internal secret return `403`.

### Internal rewards

```http
POST /internal/rewards
X-Internal-Secret: <shared-secret>
Content-Type: application/json
```

The request must contain `player_id` and a unique `encounter_id`. It must
specify exactly one of the following reward types.

#### Capture reward

Adds a new species to the player's collection:

```json
{
  "player_id": "player_123",
  "encounter_id": "enc_987654",
  "captured_species_id": 11
}
```

The species must exist and must not already be owned. A successful capture
returns `201`. Repeating the same `encounter_id` returns `200` without adding a
duplicate reward.

#### Stats reward

Increases the selected owned monsters' stats:

```json
{
  "player_id": "player_123",
  "encounter_id": "enc_987655",
  "owned_monster_ids": [1, 2],
  "atk_bonus": 1,
  "hp_bonus": 2
}
```

Bonuses must be non-negative integers. Each value is capped at three points
above the corresponding catalogue value. A successful stats reward returns
`200`.

Both reward types reject malformed payloads with `400`. Unknown species or
foreign ownership IDs return `404`; duplicate species ownership or database
conflicts return `409`.

## Authentication and configuration

The service supports two authentication mechanisms:

1. **Player JWTs** use RS256 and are required for `/collection`.
2. **Internal service secrets** use the `X-Internal-Secret` header and are
   required for internal collection and reward routes.

Supported environment variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy database connection string |
| `JWT_PUBLIC_KEY` | PEM-encoded RSA public key; escaped `\n` sequences are expanded |
| `JWT_PUBLIC_KEY_PATH` | File containing the public key; default `/certs/jwt_public.pem` |
| `INTERNAL_SERVICE_SECRET` | Shared secret for internal endpoints |

For production, provide secrets through the deployment environment or a secret
manager rather than committing them to source control.

## Running with Docker Compose

From this directory:

```bash
docker compose -f compose.monster.yaml up --build
```

The Compose file starts:

- `monster_service`, exposed on `127.0.0.1:5002`;
- `monster_db`, a PostgreSQL 15 instance on `127.0.0.1:5432`.

The container listens on port `5002` with Gunicorn and generates a
self-signed HTTPS certificate during image creation. The Compose configuration
uses the service name `monster_db` to connect to PostgreSQL.

## Running locally

Create and activate a Python virtual environment, then install dependencies:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Set `DATABASE_URL`, `JWT_PUBLIC_KEY` (or `JWT_PUBLIC_KEY_PATH`), and
`INTERNAL_SERVICE_SECRET`, then start Flask through the application factory:

```bash
flask --app "app:create_app()" run --port 5002
```

For a production-style local process:

```bash
gunicorn --bind 0.0.0.0:5002 "app:create_app()"
```

## Testing

The Python tests use an in-memory SQLite database and generate a temporary
RS256 key pair, so they do not require a running PostgreSQL container:

```bash
pytest
```

The test suite covers catalogue retrieval, image routes, JWT failures, lazy
starter initialization, internal-secret protection, capture
rewards, idempotency, and capped stat rewards.

The `tests/bruno` collection provides additional request-level checks for the
catalogue, collection, and reward workflows.

## API documentation

`openapi.yaml` contains the OpenAPI 3.0 definition for the public catalogue,
collection, and internal reward operations. It can be imported into Swagger
UI, Postman, Bruno, or another OpenAPI-compatible tool for interactive
testing.
