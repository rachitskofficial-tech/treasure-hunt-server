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

Every section keeps its own test-run history, last scan time, device, browser, and run count.

## 🏁 Live event QR routes

The real QR codes use the same Render server with the `/event/...` routes. These write to `event_scans` and are the only scans shown in the admin dashboard.

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

## 🔐 Admin dashboard

[**Open Treasure Hunt Control Room**](https://treasure-hunt-server.onrender.com/admin)

`/admin` contains only live event data:
- 🟢 Original Clues
- 🔴 Fake QRs
- IST timestamps
- Device and browser
- Approximate unique visitors
- Repeated scan counts (`Times Rec.`)

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

python app.py
```

## Deploy publicly
Use one Python-capable host such as Render for the entire application. Start command:

```bash
gunicorn app:app
```

Set these environment variables on the host:
- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `VISITOR_SALT`

For persistent live counts, the `event_scans` table should live on persistent disk or be replaced with a managed database such as PostgreSQL.
