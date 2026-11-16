# Deployment plan (2026-09-09)

> TL;DR: (1) Frontend and backend are **built into one image behind one URL**. Same origin removes CORS issues, and only one certificate is needed.
> (2) Recommended: **Fly.io + Frankfurt + persistent volume**, about **EUR 8-10 for the whole study period** (Fly.io no longer has a free tier).
> (3) **Run exactly one instance.** Block randomisation counts lines in the assignment ledger; two instances would each record half and the groups would silently become unbalanced.

---

## 1. Why hosting is required

Prolific only sends participants to a URL. **The task itself runs in this app**, so the app needs a public address.

Three hard constraints:

| Constraint | Reason |
|---|---|
| **Server in the EU** | Cross-border data transfer would complicate the lightweight GDPR argument (anonymous, Prolific ID only, self-assessment) |
| **URL must not change during the study** | The link is configured in the Prolific study; changing it sends active participants to a 404 |
| **Restarts must not lose data** | The three JSONL files are the entire dataset; there is no second copy |

---

## 2. Platform comparison (checked 2026-09-09)

| Platform | Price | EU | Persistent disk | Verdict |
|---|---|---|---|---|
| **Fly.io** (chosen) | shared-cpu-1x/512MB always on, about **$3.32/month**; volume **$0.15/GB-month** | `fra` Frankfurt | Yes (volume) | **Recommended.** Single instance can be pinned, region can be chosen, volumes are first-class |
| Hetzner Cloud | CX series about **EUR 4/month** | Germany (Nuremberg/Falkenstein) | Yes (full VPS) | Cheapest and most controllable, but OS, TLS and reverse proxy are all self-managed |
| Render | Free tier for web services | Frankfurt | **No persistent disk on the free tier, and idle services sleep** | Rejected: cold starts time out participants, no disk loses data |
| Railway | Usage-based | EU region available | Yes | Usable, but scales horizontally by default and must be locked manually |
| **Chair server** | Free | Yes | Yes | **Best option if available** |

**Cost**: about **EUR 8-10** for two months. Negligible compared with the EUR 230 for Prolific, but **not zero**.

---

## 3. Deployment structure

```
+- One Fly app (fra) ---------------------+
|  FastAPI                                |
|   |-- /api/*        study API           |
|   |-- /health       health check        |
|   +-- /*            frontend dist        |
|                     (same origin)       |
|                                         |
|  /data (persistent volume)              |
|   |-- assignments.jsonl      ledger     |
|   |-- experiment_log.jsonl   behaviour  |
|   +-- survey_responses.jsonl answers    |
+-----------------------------------------+
```

**Same origin is deliberate**: the backend serves the frontend itself, so the browser never makes cross-origin requests and `ALLOWED_ORIGINS` cannot be misconfigured in production. Local development is unaffected: `npm run dev` still runs on 5173, and the static mount is skipped when `dist/` does not exist.

**The data directory is configurable** (`storage.py`): locally it defaults to `backend/`; in the container `DATA_DIR=/data` puts it on the volume. The container's own file system is wiped on every restart and redeploy, which is the easiest way to lose data silently.

---

## 4. First deployment

```bash
# 1. Install flyctl and log in
fly auth login

# 2. Change the app name in fly.toml (it becomes part of the URL and cannot be changed later)

# 3. Create the app and the volume (the volume must be in the same region as the machine)
fly apps create <app-name>
fly volumes create hems_data --region fra --size 1

# 4. Set the researcher token (without it, export and summary endpoints return 503 on purpose)
fly secrets set RESEARCHER_TOKEN=$(openssl rand -hex 24)

# 5. Deploy
fly deploy

# 6. Health check
curl https://<app-name>.fly.dev/health
```

Once the Prolific completion URL and code are available, put them into `[build.args]` in `fly.toml` and **redeploy**. Vite bakes them into the bundle at build time; changing runtime environment variables has no effect.

---

## 5. Data backup (not optional)

The server holds the **only** copy of the data. Losing it means the study has to be repeated and Prolific still has to be paid.

```bash
set STUDY_URL=https://<app-name>.fly.dev
set RESEARCHER_TOKEN=<the token generated above>
python backup_study_data.py
```

Each run writes a new timestamped file and **never overwrites**. Run it **once a day** during data collection.

Exit codes: `0` success; `1` failure or empty export (usually a wrong URL or a fresh volume; **no file is written on purpose**, so that an empty backup never looks successful); `2` written, but the server reported corrupted lines, which means data has already been lost on the server and must be checked the same day.

---

## 6. Pre-launch checklist

- [ ] App name in `fly.toml` is final and **will not change**
- [ ] Volume exists in the same region as the machine (`fly volumes list`)
- [ ] `RESEARCHER_TOKEN` is set, and `curl .../api/export/all` without a token returns 401
- [ ] Prolific completion URL / code are in the build args and the app has been redeployed
- [ ] Run the full flow with `?PROLIFIC_PID=test123`: consent -> three tasks -> five questionnaire pages -> completion code -> redirect to Prolific
- [ ] `/api/survey/summary?token=...` shows the test record
- [ ] **Clear test data**: `backend/assignments.jsonl` must be emptied before launch, otherwise block randomisation starts from the wrong count
- [ ] Backup script has run successfully once and is scheduled daily
- [ ] Single instance confirmed: `fly scale show` should be 1

---

## 7. Known limitations (reported in the thesis)

- **A single instance is a single point of failure.** 40 participants do not need high availability, but if the machine fails the study stops. Mitigation is a health check plus daily backups, not redundancy.
- **Data is stored as JSONL files rather than a database.** With a small sample and sparse writes this trade-off is appropriate; the cost is that write safety relies on there being only one process rather than on database transactions.
