# FANS — Setup Instructions

## Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Git

## Step 1: Clone and Create Virtual Environment
```bash
git clone <repo-url>
cd FANS-C-A-...
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

## Step 2: Configure Environment
```bash
cp .env.example .env
```
Edit `.env` with your values:
```env
SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=True
DB_NAME=fans_db
DB_USER=fans_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
VERIFICATION_THRESHOLD=0.75
```

## Step 3: Create PostgreSQL Database
```sql
-- Run in psql as superuser:
CREATE DATABASE fans_db;
CREATE USER fans_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE fans_db TO fans_user;
ALTER DATABASE fans_db OWNER TO fans_user;
```

## Step 4: Run Setup Script
```bash
python setup.py
```

Or manually:
```bash
pip install -r requirements.txt
python manage.py generate_key   # Add output to .env as EMBEDDING_ENCRYPTION_KEY
python manage.py migrate
python manage.py init_config
python manage.py create_admin
python manage.py collectstatic --noinput
```

## Step 5: Run the Server
```bash
python manage.py runserver
```
Visit: http://127.0.0.1:8000/
Login: admin / Admin@1234 (change immediately)

## ML Model Notes
- **FaceNet**: Automatically downloaded by `keras-facenet` on first use (~90MB)
- **RetinaFace**: Downloaded by the `retinaface` package (~100MB weights)
- **Anti-spoofing**: Currently uses texture analysis (no external model needed)
  - For production, integrate [Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing)
  - Place model weights in `models/anti_spoof/`
- **MediaPipe**: Loaded from CDN in browser (no server installation needed)

## Project Structure
```
fans/                  # Django project config
accounts/              # Auth: CustomUser, login/logout, user management
beneficiaries/         # Beneficiary registration, list, detail
verification/          # Face processing, liveness, comparison, results
logs/                  # Audit and verification log views
templates/             # HTML templates
static/css|js/         # Frontend assets
```

## User Roles
| Role  | Permissions |
|-------|-------------|
| Admin | Full access: users, override, config, logs |
| Staff | Register + Verify only |

## Business Rules
- Liveness check fails → automatic denial (no retry)
- Face match fails → 1 retry allowed
- After retry fails → fallback ID verification
- Only Admin can override decisions (with mandatory reason)
- All actions are logged with timestamp, user, and IP
