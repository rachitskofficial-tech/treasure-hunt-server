# Treasure Hunt Server 🗺️

QR routes are live when this app is deployed.

[**Test wrong QR**](https://treasure-hunt-server.onrender.com/test/wrong)     [**Test clue QR**](https://treasure-hunt-server.onrender.com/test/clue)     [**Admin dashboard**](https://treasure-hunt-server.onrender.com/admin)

## 🧪 Test Runs

The two buttons above are **safe sandbox test runs**. They use the dedicated `/test/...` routes and write to the separate `test_scans` table, so testing them does **not** affect the real event counters.

- **Test wrong QR** → `/test/wrong`
- **Test clue QR** → `/test/clue`

You can also test every route directly:

**Original Clues**
- Test Clue 1 → `/test/clue`
- Test Clue 2 → `/test/clue2`
- Test Clue 3 → `/test/clue3`
- Test Clue 4 → `/test/clue4`

**Fake QRs**
- Test Wrong QR 1 → `/test/wrong`
- Test Wrong QR 2 → `/test/wrong2`
- Test Wrong QR 3 → `/test/wrong3`

## 🟢 Original Clues

| Clue | Keyword | Route |
|---|---|---|
| **Clue 1** | **Canteen** | `/clue` |
| **Clue 2** | **ID Card** | `/clue2` |
| **Clue 3** | **Magazine** | `/clue3` |
| **Clue 4** | **Notice Board** | `/clue4` |

## 🔴 Fake QRs

| Fake QR | Keyword / Message | Route |
|---|---|---|
| **Wrong QR 1** | **Wrong QR** | `/wrong` |
| **Wrong QR 2** | **Keep Finding** | `/wrong2` |
| **Wrong QR 3** | **Eureka? Nope** | `/wrong3` |

## Dashboard

- `/admin` → password-protected live scan dashboard
- `/health` → health check

The dashboard separates original clues from fake QRs and shows IST time, device, browser, approximate unique visitors, and repeated-scan counts. Test scans remain isolated from the real event counters.

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

python app.py
```

Open `http://localhost:5000/admin` to test the dashboard.

## Deploy publicly
Upload this folder to a Python-capable host such as Render, Railway, Fly.io, or another service you already use. Start command:

```bash
gunicorn app:app
```

Set these environment variables on the host:
- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `VISITOR_SALT`

For persistent scan counts, the SQLite database must live on persistent disk, or the database should be replaced with a managed database such as PostgreSQL. Some free hosting plans use ephemeral filesystems, which can erase `scans.db` on restart/redeploy.

## QR setup
Once deployed, use the live Render URLs for the corresponding routes and generate the QR codes from those URLs.

## Important counting note
The dashboard tracks **total scans** and an **approximate unique visitor count**. It does not know the real-world identity of a person, and the same person can appear more than once if they switch browsers/devices or networks.
