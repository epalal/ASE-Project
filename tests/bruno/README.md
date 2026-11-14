# Bruno tests

One collection for the whole project, laid out like the course's Lab 6 reference
solution: a folder per service, a folder per stub, and an environment for each way
of running them.

| Folder | What it tests | Environment |
|---|---|---|
| `encounter` | The Encounter Service's answers: team, challenges, encounters, every error | `encounter-component` |
| `encounter-stub` | What the Encounter Service asks the Monster Service, and what happens when it fails or refuses | `encounter-component` (component tests only) |
| `encounter-security` | Hostile input (Lab 8): a body over 10 KB, control characters, `NaN`, huge numbers, text that is not JSON. Each one must be refused | `encounter-component` |

Each folder starts by getting login tokens from the Player Service stub, so a folder
can run on its own and nothing secret is stored here.

## Component tests of the Encounter Service

```
cp .env.example .env                                   # once, then set the three values
docker compose -f compose.encounter.yaml up --build -d --wait
docker compose -f compose.encounter.yaml cp encounter-service:/certs/ca.pem tests/bruno/ca.pem
```

The services use HTTPS with certificates from our own development authority, so
Bruno has to trust it: in Bruno, open Preferences > General, turn on "Use custom
CA Certificate" and choose `tests/bruno/ca.pem`. The file is not committed, and a
new one is made after every `down -v`, so copy it again then.

Then open this folder as a collection, choose the environment `encounter-component`
and run the folders `encounter`, `encounter-stub` and `encounter-security` with the Runner.

```
docker compose -f compose.encounter.yaml down -v       # stop; -v also deletes the data and certificates
```

### From the terminal (optional)

With Node installed (`npm install -g @usebruno/cli@4.3.0`):

```
cd tests/bruno
bru run encounter encounter-stub encounter-security --env encounter-component --cacert ca.pem
```

Without Node, the same run in a container on the stack's network:

```
docker run --rm --network encounter-component_default -v "$PWD/tests/bruno:/bruno" -w /bruno \
  node:22-alpine npx -y @usebruno/cli@4.3.0 run encounter encounter-stub encounter-security --env encounter-component \
  --env-var encounterUrl=https://encounter-service:5003 \
  --env-var monsterStubUrl=https://monster-service:5002 \
  --env-var playerStubUrl=https://player-service:5001 --cacert ca.pem
```

Exit code 0 means every test passed.

## The stubs' special players

The Monster stub chooses its answer from the player ID in the token:

| Player | What the Monster stub does |
|---|---|
| `stub-strong` | owns very strong monsters, so an attack always wins |
| `stub-refuse` | owns very strong monsters and refuses every reward |
| `stub-500` | answers 500 |
| `stub-slow` | answers after 5 seconds, after the Encounter Service has given up (3 seconds) |

Any other player owns the four starters, with the IDs `101`, `105`, `109` and `115`.
