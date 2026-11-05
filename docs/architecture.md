# Monster Tamers architecture

The architecture for the second delivery, with the reason for each choice. It updates slides 3, 9 and 11 of the first-delivery presentation after the professor's feedback ("be careful with the Data Storage Layer to avoid architectural smells", plus the questions on monster power and type modifiers) and the security requirements in §6 of the functional requirements.

Status: written by Hatem, waiting for the team to agree.

## Overview

```mermaid
flowchart TB
    FE["Web Frontend<br/>HTML · CSS · JavaScript<br/>(runs outside Docker)"]

    subgraph compose["Docker Compose"]
        GW["API Gateway<br/>Python / Flask<br/>only public entry point"]

        subgraph services["Application layer"]
            PS["Player Service<br/>registration, login<br/>issues JWT"]
            MS["Monster Service<br/>catalogue, owned monsters,<br/>rewards"]
            ES["Encounter Service<br/>team, challenges,<br/>resolution, history"]
        end

        subgraph data["Data layer (one database per service)"]
            PDB[("player-db<br/>PostgreSQL")]
            MDB[("monster-db<br/>PostgreSQL")]
            EDB[("encounter-db<br/>PostgreSQL")]
        end
    end

    FE -- "HTTPS · REST/JSON" --> GW
    GW -- HTTPS --> PS
    GW -- HTTPS --> MS
    GW -- HTTPS --> ES
    ES -- "HTTPS /internal<br/>get monsters · apply reward" --> MS
    PS -- TLS --> PDB
    MS -- TLS --> MDB
    ES -- TLS --> EDB
```

Only the gateway is published to the host. The three services and the three databases can only be reached inside the Docker network.

## Services

| Service | Owns | Calls |
|---|---|---|
| API Gateway | Routing of public URLs to services | Player, Monster, Encounter |
| Player Service | Accounts and credentials; signs JWTs | Nobody |
| Monster Service | Monster catalogue, owned monsters with their own ATK/HP, applied rewards | Nobody |
| Encounter Service | Current team, challenges, encounter resolution, encounter history | Monster (`/internal` only) |

Calls go one way. The Encounter Service is the only service that calls another one, and it only calls the Monster Service.

## Design rules

### 1. Each service has its own database

Each service gets its own PostgreSQL container, database login and volume. A service can only open its own database. Other services get that data through the owner's REST API.

The first delivery drew one PostgreSQL container shared by all three services, which is the shared-persistence smell the professor warned about. With one admin login, any service could read the passwords table, one leaked password would expose all the data, and one crash would stop every service. With separate containers, the setup itself enforces who owns which data.

### 2. The player's identity comes only from the token

Every service reads the player ID from the verified JWT. No public endpoint accepts a player ID in the URL, the query or the body.

If an endpoint accepted `player_id` from the client, a player could change it and read or modify another player's collection, team or history. This is the most common API vulnerability (broken object-level authorization), and the professor said they will try attacks during the evaluation.

### 3. Service-to-service endpoints are hidden

Calls between services use paths under `/internal/`. The gateway never routes `/internal/` paths, and the Monster Service accepts them only from the Encounter Service, which sends a service credential.

"Grant reward" is the endpoint a cheater would look for first. The requirements say rewards must be updated by the backend services that manage encounter results, never by a client request.

### 4. Encounters are resolved on the server, and each reward is applied once

The client only chooses a challenge and then an action. The Encounter Service reads the player's team from its own database and the monsters' current stats from the Monster Service, computes the chances, rolls on the server and stores the result. After a win or a capture it asks the Monster Service to apply the reward and sends the encounter ID. The Monster Service records each encounter ID and refuses a second reward for the same one.

So the client can never submit an outcome, and a double click or a retry cannot reward twice. If the reward call fails, the encounter keeps `reward_status = pending` and the reward can be retried. The requirements ask us to document how contingencies like this are handled.

### 5. No circular calls

The Player Service calls nobody. The Monster Service creates the starter monsters the first time it sees a new player ID in a valid token.

If Player called Monster at registration and Monster ever called Player, the two services would depend on each other (cyclic-dependency smell), and we could no longer run or test one without the other.

### 6. Only the Player Service can create tokens

The Player Service signs JWTs with a private key that only it holds (for example RS256). The other services verify tokens with the matching public key, which cannot create tokens. Tokens last about 15 minutes and carry the player ID in `sub`, plus `exp`, `iat`, `iss` and `aud`.

With a shared secret, any compromised service could forge a token for any player. Signing with a private key also follows the OAuth2/JWT requirement in §6.

### 7. Every connection is encrypted and nothing else is exposed

The frontend talks to the gateway over HTTPS, and so does the gateway to each service, with self-signed certificates. Services connect to their databases over TLS. No database port is published, and containers run as a non-root user. Passwords and keys come from environment variables or Docker secrets and are never committed; the repository keeps only a `.env.example`.

All of these are explicit requirements in §6. Encrypting traffic inside Docker limits what an attacker learns after taking over one container, and a non-root container has a much harder time attacking the host.

### 8. The gateway is a Flask application

The gateway follows the pattern from Labs 5 and 6: a Flask app that forwards requests and returns 502 or 504 when a service fails or times out. Issue #11 said Nginx and slide 9 showed the Nginx logo. The gateway on `main` is already a Flask app, so only the slide changes, and the diagram above replaces it.

## Database design

A species is one of the 16 monsters in the catalogue and is the same for every player. An owned monster is one player's copy of a species, with its own ATK and HP. Rewards change the owned monster and leave the species alone.

The player IDs stored in the Monster and Encounter databases are copied from the token, and the owned monster and species IDs stored in the Encounter database come from the Monster Service. None of them are foreign keys, because separate databases cannot reference each other.

### player-db (Player Service)

`player`

| Column | Rule | Why |
|---|---|---|
| `id` | UUID, primary key | Opaque IDs (Lab 3) cannot be guessed the way 1, 2, 3 can |
| `username` | unique, not null | The database rejects duplicates even if two sign-ups arrive at once |
| `password_hash` | not null | bcrypt hash only; a leaked database does not reveal passwords |
| `created_at` | timestamp | Record keeping |

There is no session or token table, because a JWT carries its own expiry. We store no other personal data (email, real name), so there is less to protect.

### monster-db (Monster Service)

`species`: the catalogue, 16 rows loaded once

| Column | Rule | Why |
|---|---|---|
| `id` | primary key | Identifies the monster |
| `name` | unique, not null | |
| `type` | one of `fire`, `water`, `grass`, `dark` | Typos and unknown types are rejected; the names match the monster cards |
| `base_atk`, `base_hp` | integer, greater than 0 | Starting stats from the roster slide; both enter the monster's power (see Encounter rules) |
| `image_url` | not null | Every monster must have an image (requirements §4) |

`owned_monster`: a player's monsters

| Column | Rule | Why |
|---|---|---|
| `id` | UUID, primary key | The team points to this ID |
| `player_id` | UUID, not null | Owner, from the token |
| `species_id` | references `species` | Which monster this is |
| `atk`, `hp` | integer, greater than 0 | Current stats: they start at the base values and grow by 1 per attack win, up to the base value + 3 |
| `source` | `starter` or `capture` | Where it came from (US-06 or US-12) |
| `source_encounter_id` | UUID, unique, nullable | The encounter that captured it; the same encounter cannot capture twice |
| `acquired_at` | timestamp | Record keeping |
| | unique (`player_id`, `species_id`) | No duplicates: a player owns at most one of each species |

`applied_reward`: rewards already given

| Column | Rule | Why |
|---|---|---|
| `encounter_id` | UUID, primary key | A second reward for the same encounter is rejected (rule 4) |
| `player_id` | UUID, not null | Who received it |
| `atk_bonus`, `hp_bonus` | integer | The stat increase from an attack win; 0 for a capture |
| `captured_species_id` | nullable | The monster captured, if the action was a capture |
| `applied_at` | timestamp | Record keeping |

### encounter-db (Encounter Service)

`team_member`: the three team slots

| Column | Rule | Why |
|---|---|---|
| `player_id`, `slot` | primary key; `slot` is 1, 2 or 3 | At most three slots, one monster per slot |
| `owned_monster_id` | UUID, not null | One of the player's monsters in the Monster Service |
| | unique (`player_id`, `owned_monster_id`) | The same monster cannot fill two slots |

When the player saves a team, the Encounter Service asks the Monster Service for the player's monsters and accepts the team only if it has exactly three different monsters that the player owns. It then replaces the three slots in one transaction.

The team lives here because it only exists to prepare encounters (US-14: "so that I can prepare for an encounter"). The same person builds the team stories (US-14, 15, 16) and the encounter stories, so nobody waits on a handoff. Elena suggested the move.

`challenge`: encounters a player can choose, 16 rows, one per monster

| Column | Rule | Why |
|---|---|---|
| `id` | primary key | |
| `name`, `description` | not null | Shown in the challenge list (US-17) |
| `wild_species_id` | not null, unique | The monster faced; its stats are read from the Monster Service when the encounter opens, so the catalogue has a single owner. Challenges differ by this monster's type and stats; there is no separate difficulty level |

`encounter`: one row per encounter

| Column | Rule | Why |
|---|---|---|
| `id` | UUID, primary key | Sent with the reward request so the reward is applied once |
| `player_id` | UUID, not null | Whose encounter |
| `challenge_id` | references `challenge` | Which challenge |
| `status` | `open` or `closed` | An open encounter is waiting for the player's action |
| | unique (`player_id`) where `status` is `open` | The database allows only one open encounter per player |
| `team_snapshot` | JSON, not null | The three monsters with their stats when the encounter opened; history stays correct after rewards change the stats |
| `wild_snapshot` | JSON, not null | The wild monster's stats used in the encounter |
| `team_power`, `challenge_power`, `p_win` | not null | The full calculation, so any result can be checked; also feeds the result and history pages (US-20, US-24) |
| `p_capture` | nullable | Empty when the player already owns the wild monster, because capture is not offered |
| `action` | `attack`, `capture` or `escape`; empty while open | What the player chose (US-21, US-22) |
| `roll` | nullable | The random number; empty while open and for an escape |
| `result` | `win`, `loss`, `captured`, `failed` or `escaped`; empty while open | |
| `reward_status` | `none`, `pending`, `applied` or `failed` | Shows a reward that still needs to be retried |
| `created_at`, `closed_at` | timestamp | |

### Rules for all databases

Each service connects with its own login, which can only reach its own database; no service uses the admin user. Queries use parameters or an ORM and never build SQL by string concatenation, which prevents SQL injection. Each database has its own volume, and no database port is published.

## Encounter rules

We keep the formula agreed in issue #10 and shown on slide 3. Only the monster power changed: it used to be the monster's level (1, 2 or 3), and the 16 monsters now have ATK and HP instead of levels. The actions come from US-21 and US-22.

### Power and chances

1. Monster power = (ATK + HP) / 2. Team monsters use their current stats, and the wild monster uses its base stats.
2. Each team monster's power is adjusted against the wild monster: +1 if its type beats the wild monster's type, -1 if the wild monster's type beats it, 0 otherwise. The adjusted power never goes below 0.
3. Team power = the sum of the three adjusted powers.
4. Challenge power = 3 × the wild monster's power, which puts one monster on the same scale as a team of three.
5. `P(win) = 1 / (1 + exp(-0.6 × (team_power - challenge_power)))`. Equal power gives 50%, a 5-point advantage about 95% and a 5-point disadvantage about 5%.
6. `P(capture) = 0.75 × P(win)`.

Type cycle: Fire beats Dark, Dark beats Grass, Grass beats Water, Water beats Fire. All other matchups are neutral.

Example: a team of Sproutpaw (Grass, 2/2), Drifin (Water, 2/3) and Emberbun (Fire, 3/2) against a wild Emberbun (Fire, 3/2).

| Monster | Power | Type | Adjusted |
|---|---|---|---|
| Sproutpaw | (2 + 2) / 2 = 2 | neutral | 2 |
| Drifin | (2 + 3) / 2 = 2.5 | Water beats Fire, +1 | 3.5 |
| Emberbun | (3 + 2) / 2 = 2.5 | neutral | 2.5 |

Team power = 8, challenge power = 3 × 2.5 = 7.5, so P(win) ≈ 57% and P(capture) ≈ 43%. Capture is not offered in this example, because the player already owns an Emberbun.

### How an encounter runs

There are 16 challenges, one for each monster.

1. The player opens an encounter by choosing a challenge. The Encounter Service reads the player's team, gets the current stats of those three monsters from the Monster Service, and saves them with the wild monster as they are at that moment. It then computes P(win) and P(capture). Capture is offered only if the player does not own that monster yet. If the player has not saved a valid team, the encounter does not open (409). A player can have one open encounter; opening a new one closes the old one as `escaped`.
2. The player picks one action. For attack and capture, the Encounter Service draws a random number between 0 and 1 with a secure generator, and the action succeeds if the number is lower than its chance.

   | Action | Success | Failure |
   |---|---|---|
   | Attack | `win`: each team monster gets +1 ATK and +1 HP, up to its base value + 3 | `loss`: nothing happens |
   | Capture | `captured`: the wild monster joins the collection | `failed`: nothing happens |
   | Escape | `escaped`: always works, with no roll | |

3. The encounter closes and stays in the history with the action, the result, both chances and the roll.

### Why these rules

We use (ATK + HP) / 2 because the requirements ask for at least two characteristics that influence encounters, and this way both stats count equally. The values also stay small like the old levels, so the agreed 0.6 factor still works. With ATK + HP the values double and most fights become certain wins or certain losses. With ATK alone, HP would have no effect.

Attack and capture give different rewards, so the player's choice changes what they get (US-22: "so that my decisions can influence its outcome"). Attack makes the team stronger and capture grows the collection. Capture is a bit harder than attack, so even a strong team takes a risk when it tries to catch a monster.

A lost attack costs nothing, so an escape that could fail would only change the label in the history. Escape therefore always works while the encounter is open, which is what "when the game rules allow it" means in US-21.

Without a limit, the starter monsters would keep growing until they beat every monster, and capturing would stop mattering. With the +3 limit, a fully grown starter team still has only about 11% against Dolwhale and 18% against Cindrake. The limit is one line in the Monster Service: `atk = min(atk + 1, base_atk + 3)`.

Allowing one open encounter per player needs no timers or cleanup jobs. Because the team is saved when the encounter opens, the chances the player sees are the ones that get rolled.

### API changes to contracts C5, C7, C9 and C10 (issue #21)

| Contract | Call | Change |
|---|---|---|
| C5 | `GET /team`, `PUT /team` | Move from the Monster Service to the Encounter Service, built by Hatem. `PUT /team` takes three owned monster IDs and returns 400 if the team breaks a rule |
| C7 | `POST /encounters` with `{"challenge_id": ...}` | Opens the encounter and returns its ID, the wild monster, the team, `p_win` and `p_capture` (`null` when capture is not offered). It no longer returns the result. Returns 409 if the player has no valid team |
| C7 | `POST /encounters/{id}/action` with `{"action": "attack"}`, `"capture"` or `"escape"` | Resolves the encounter and returns the result. Returns 409 if the encounter is already closed or capture is not offered, and 404 if the encounter belongs to another player |
| C9 | `GET /internal/players/{id}/monsters` | Replaces `GET /internal/players/{id}/team`. Returns the player's owned monsters with their species, type and current ATK and HP. The Encounter Service uses it to check a team when it is saved, to read the stats when an encounter opens, and to decide whether to offer capture |
| C10 | `POST /internal/rewards` | Two kinds of reward: stats (`owned_monster_ids` from the snapshot, `atk_bonus`, `hp_bonus`) or capture (`captured_species_id`). The Monster Service applies the +3 limit, because it owns the stats |

## Decisions taken

| Decision | Choice |
|---|---|
| Monster power | (ATK + HP) / 2, replacing the level |
| Type names | Fire, Water, Grass, Dark, as on the monster cards |
| Difficulty levels | None; each challenge is one wild monster |
| Challenges | 16, one per monster |
| Encounter flow | Two steps: open the encounter, then choose one action |
| Actions | Attack (a win raises stats), capture (a success adds the monster), escape (always works) |
| Capture chance | 0.75 × P(win) |
| Capturing a monster the player already owns | Not offered; the server returns 409 |
| Reward for an attack win | +1 ATK and +1 HP for each team monster, up to the base value + 3 |
| Reward for a loss or a failed capture | Nothing |
| Open encounters | At most one per player; opening a new one closes the old one as escaped |
| Opening an encounter without a valid team | Refused with 409 |
| Database separation | One PostgreSQL container, login and volume per service |
| A separate "progress" table (level, experience) | Not used; progress is the collection, the monsters' stats and the encounter history |
| Gateway owner | Elisa |
| Team (table, `GET /team`, `PUT /team`) | Encounter Service, built by Hatem; moved from the Monster Service on Elena's suggestion |
