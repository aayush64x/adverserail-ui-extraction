# vision-scraping-robustness

Research project with Dr. Kendall-Morwick. Question: how well does vision-only extraction from screenshots hold up against adversarial UI changes? Mastodon is the test environment: we run it locally and later modify its layout to act as the adversary.

This file documents how the local Mastodon instance is set up and run, so it can be reproduced on any machine.

---

## Prerequisites

- macOS (tested) — on Windows, use WSL2
- Docker Desktop, with at least 8 GB RAM allocated (Elasticsearch needs it)
- git

## Mastodon version

- Repo: https://github.com/mastodon/mastodon
- Local path: `~/Desktop/Research/mastodon`
- Version: **TODO** — record output of `git describe --tags` and `git rev-parse --short HEAD`

---

## How the setup works

Mastodon needs several programs running together. The repo's `.devcontainer/compose.yaml` defines each one as a Docker service:

| Service | What it is |
|---|---|
| `app` | Ruby/Node dev container — runs Mastodon itself |
| `db` | PostgreSQL 14 — the database |
| `redis` | Redis 7 — cache and job queue |
| `es` | Elasticsearch — search |
| `libretranslate` | Translation service |

Notes:
- The repo folder is mounted into the `app` container, so file edits on the Mac show up in the container instantly.
- The database lives in a Docker **volume**, so it survives container restarts.
- Installed gems and yarn live inside the **container**, not a volume. If the container is deleted, they are gone.
- The `app` container runs `sleep infinity`, so it idles until you `exec` a command into it.

Every command below uses `-f .devcontainer/compose.yaml` because the repo has more than one compose file.

---

## First-time setup

Run from the Mastodon folder.

1. **Start Docker Desktop.** Run `open -a Docker`, then `docker info` to confirm the engine is up.

2. **Start the containers.** The first run builds and pulls images; later runs reuse them.
```sh
   docker compose -f .devcontainer/compose.yaml up -d
```

3. **Check that all 5 services show `Up`:**
```sh
   docker compose -f .devcontainer/compose.yaml ps
```

4. **Install and prepare the app.** This installs gems and JS packages, creates the database, and seeds the admin account. Run it once per new container.
```sh
   docker compose -f .devcontainer/compose.yaml exec app bin/setup
```
   If it fails with `yarn: No such file or directory`:
```sh
   docker compose -f .devcontainer/compose.yaml exec -u root app corepack enable
```
   Then rerun `bin/setup`.

5. **Run Mastodon.** This starts the Rails web server (port 3000), Vite assets (3036), streaming (4000), and Sidekiq. It runs in the foreground, so keep the terminal open.
```sh
   docker compose -f .devcontainer/compose.yaml exec app bin/dev
```

6. **Open http://localhost:3000** and log in:
   - Email: `admin@localhost`
   - Password: `mastodonadmin`

---

## Daily use

```sh
open -a Docker                                                 # if Docker isn't running
docker compose -f .devcontainer/compose.yaml up -d             # turn containers on
docker compose -f .devcontainer/compose.yaml exec app bin/dev  # run Mastodon
```

To stop:
- `Ctrl+C` stops Mastodon, but the containers keep running.
- `docker compose -f .devcontainer/compose.yaml stop` pauses the containers. **Use this.**

| Command | Effect |
|---|---|
| `stop` | Pauses containers. Keeps installed tools and data. |
| `down` | **Deletes containers.** Gems and yarn are lost, so `bin/setup` must be rerun. Data is kept. |
| `down -v` | **Deletes containers and volumes.** Database and all posts are wiped. Clean reset only. |

Mental model:
- `bin/setup` = install the app (once)
- `up -d` = turn the machine on
- `bin/dev` = open the app

---

## Creating extra accounts

The signup form doesn't work locally: there's no email server, and registration may require approval. Create accounts from the CLI instead:

```sh
docker compose -f .devcontainer/compose.yaml exec app bin/tootctl accounts create alice --email alice@localhost --confirmed
# prints a generated password — save it
docker compose -f .devcontainer/compose.yaml exec app bin/tootctl accounts approve alice   # only if login still fails
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `failed to connect to the docker API ... docker.sock` | Docker Desktop not running | `open -a Docker`, wait, retry |
| `bundler: command not found: puma` / `sidekiq`, `yarn: No such file` | Containers were recreated, so installed tools are gone | Run `bin/setup` (and `corepack enable` if yarn is missing) |
| Admin login fails | Seed didn't run | `docker compose -f .devcontainer/compose.yaml exec app bin/rails db:seed` |
| `es` container keeps restarting | Not enough Docker memory | Raise RAM in Docker Desktop → Settings → Resources |
| Port 3000 already in use | Another Mastodon/app running | `lsof -i :3000`, stop that process |

Tip: enable Docker Desktop → Settings → General → "Start Docker Desktop when you sign in".

---

## Progress log

**2026-09-28**
- Mastodon dev environment running via `.devcontainer/compose.yaml`
- Containers had been recreated, so `bin/setup` was rerun
- Admin login confirmed

**Next**
- [ ] Record Mastodon version (tag/commit) above
- [ ] Screenshot of a post on the timeline
- [ ] Read the GUI agents paper: task, models, failures, metrics, how we differ
- [ ] Feasibility test: one visible layout change to Mastodon's post component (`app/javascript/mastodon/components/`), with before and after screenshots
- [ ] Provisioning tools comparison (Docker Compose, Ansible, Terraform/OpenTofu, Chef/Puppet)
- [ ] Questions for Dr. J: old computers and power supplies, local vs. cloud, number of layout variants, success metric, FLAIRS deadline
