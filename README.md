# Treasure Hunt QR Tracking Server

A tiny Flask server for your college treasure hunt.

## Routes
- `/wrong` → **Better luck next time :(**
- `/clue` → **The food will be great over here, but the chef has something to tell you 👀**
- `/admin` → password-protected scan dashboard
- `/health` → health check

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
Once deployed, use:
- `https://YOUR-DOMAIN/wrong`
- `https://YOUR-DOMAIN/clue`

Generate two QR codes using those URLs and put them on the corresponding hunt clues.

## Important counting note
The dashboard tracks **total scans** and an **approximate unique visitor count**. It does not know the real-world identity of a person, and the same person can appear more than once if they switch browsers/devices or networks.
