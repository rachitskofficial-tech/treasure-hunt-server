# Treasure Hunt Server 🗺️

**One Render server. Three separate dashboards. One shared deployment.**

Live server:
`https://treasure-hunt-server.onrender.com`

## Separate dashboards

[**Test wrong QR**](https://treasure-hunt-server.onrender.com/wrong)     [**Test clue QR**](https://treasure-hunt-server.onrender.com/clue)     [**Admin dashboard**](https://treasure-hunt-server.onrender.com/admin)

### 🧪 Test Wrong QR

Open **Test wrong QR** for the three fake-QR test sections. All test runs stay in the `test_scans` table.

| Section | Keyword | Test route |
|---|---|---|
| **Section 1** | **Wrong QR** | `/wrong/wrong` |
| **Section 2** | **Keep Finding** | `/wrong/wrong2` |
| **Section 3** | **Eureka? Nope** | `/wrong/wrong3` |

### 🧪 Test Clue QR

Open **Test clue QR** for the four clue test sections. All test runs stay in the `test_scans` table.

| Section | Keyword | Test route |
|---|---|---|
| **Section 1** | **Canteen** | `/clue/clue` |
| **Section 2** | **ID Card** | `/clue/clue2` |
| **Section 3** | **Magazine** | `/clue/clue3` |
| **Section 4** | **Notice Board** | `/clue/clue4` |

Every section keeps its own test-run history and run count.

## 🏁 Live event QR routes

The real QR codes use the same Render server with the `/event/...` routes. Registered team phones create entries in the `live_scans` table, and those scans are shown in the admin command center.

### 🟢 Original Clues

| Clue | Keyword | Live route |
|---|---|---|
| **Clue 1** | **Canteen** | `/event/clue` |
| **Clue 2** | **ID Card** | `/event/clue2` |
| **Clue 3** | **Magazine** | `/event/clue3` |
| **Clue 4** | **Notice Board** | `/event/clue4` |

### 🔴 Fake QRs

| Fake QR | Keyword / Message | Live route |
|---|---|---|
| **Wrong QR 1** | **Wrong QR** | `/event/wrong` |
| **Wrong QR 2** | **Keep Finding** | `/event/wrong2` |
| **Wrong QR 3** | **Eureka? Nope** | `/event/wrong3` |

## 📱 Participant QR Scanner

Registered teams are authorised through a secure device cookie. After registration, the **Proceed to QR Scanner** button opens `/scan`.

The scanner supports all 7 checkpoints and records every accepted scan through `/api/participant/scan`. Checkpoint progress is stored separately so repeated scans do not clear a checkpoint twice, while every scan remains visible in the live scan history.

Team slots are **Team 1 through Team 7**.

## 🔐 Admin dashboard

[**Open Treasure Hunt Control Room**](https://treasure-hunt-server.onrender.com/admin)

`/admin` contains only live event data:
- 🟢 Original Clues
- 🔴 Fake QRs
- Team registration status for Teams 1–7
- Per-team live scan counts
- Live route totals
- Recent live scan activity
- Automatic dashboard updates every 2 seconds

Test dashboards and test runs do **not** appear here.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Set these before running in a real event:
# Windows PowerShell:
# $env:SECRET_KEY="a-long-random-secret"
# $env:ADMIN_PASSWORD="your-dashboard-password"
# $env:VISITOR_SALT="another-random-secret"
# macOS/Linux:
# export SECRET_KEY="a-long-random-secret"
# export ADMIN_PASSWORD="your-dashboard-password"
# export VISITOR_SALT="another-random-secret"

# Recommended production-style local entry point:
gunicorn wsgi:application
```

## Deploy publicly
Use one Python-capable host such as Render for the entire application.

**Start command:**
```bash
gunicorn wsgi:application
```

The WSGI entry point is important because it loads both the main Flask application and the participant scanner routes, including `/scan` and `/api/participant/scan`, and enables Team 7.

Set these environment variables on the host:
- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `VISITOR_SALT`

For persistent live counts, the `live_scans` table should live on persistent disk or be replaced with a managed database such as PostgreSQL.
