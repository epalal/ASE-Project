# Monster Tamers

Monster Tamers is a web game built as microservices for the Advanced Software Engineering course. Players collect monsters, build a team of three and take on challenges against wild monsters: in each encounter they attack, try to capture the wild monster or escape.

## Documents
- User stories (Google Sheet): https://docs.google.com/spreadsheets/d/1n1LCP2W7xMwLvVTNbPtSIBRUSwD_GZDaspnIldx8m-4/edit?usp=sharing
- The report (Google Doc): https://docs.google.com/document/d/15P4AK-pznGCsa-_O73v8gIAjkfgWTypQP4pjskGHUH4/edit?tab=t.0
- Presentation: https://docs.google.com/presentation/d/1hwFVqbLTSIAy_W3j63UvVDcWr2Wxn_53_uNvN8ClWSE/edit?slide=id.p#slide=id.p
- Architecture and design decisions: [docs/architecture.md](docs/architecture.md)

## Services

| Folder | What it is | Owner |
|---|---|---|
| `gateway/` | API gateway, the only entry point from outside | Elisa |
| `auth_service/` | Player Service: accounts, login, login tokens | Elisa |
| `monster_service/` | Monster Service: catalogue, players' monsters, rewards | Elena |
| `encounter_service/` | Encounter Service: team, challenges, encounters | Hatem |
| (not in the repo yet) | Web frontend | Tancredi |

Shared parts:

| Folder | What it is |
|---|---|
| `tls_init/` | Makes the HTTPS certificates of every service and the key pair for login tokens. It runs at every `docker compose up` and keeps what already exists. |
| `monster_stub/`, `player_stub/` | Stand-ins for the Monster and Player services in component tests |
| `tests/bruno/` | The Bruno API tests, with a folder per service and per stub |

## Get started

### What you need
- Docker Desktop, with Docker Compose v2
- Python 3.12 or newer, only to run the unit tests
- Bruno 4.3 (the app, or the CLI with Node), only to run the API tests

### Secrets
Passwords and secrets are never committed. Copy the example file and set your own values, using only letters, digits, `-` and `_`:
```
cp .env.example .env
```

### Run the Encounter Service
It starts with its own database and with stubs of the Monster and Player services:
```
docker compose -f compose.encounter.yaml up --build -d --wait
docker compose -f compose.encounter.yaml ps
```
It answers on https://localhost:5003, where `GET /health` needs no login. The API is described in [encounter_service/openapi.yaml](encounter_service/openapi.yaml). To stop it:
```
docker compose -f compose.encounter.yaml down       # add -v to also delete the data and certificates
```

### Unit tests of the Encounter Service
```
cd encounter_service
python3 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest
```

### API tests with Bruno
See [tests/bruno/README.md](tests/bruno/README.md).

### The whole application
We are putting the full stack together in `docker-compose.yaml`, with every service behind the gateway over HTTPS. Until then, each service runs on its own with its stubs, as above.
