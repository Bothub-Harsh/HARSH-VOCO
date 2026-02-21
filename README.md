# Harsh Vocabulary Intelligence System

A production-ready, modular vocabulary learning web app built with FastAPI + SQLite + SQLAlchemy and a modern vanilla JS dashboard.

## Features
- JWT authentication (signup, login, protected APIs, logout).
- Word management (add/delete/list grouped words, random word).
- Smart learning engine with 3 modes:
  1. Single Group Mode
  2. All Group Rotation Mode
  3. Smart Spaced Repetition Mode
- APScheduler minute-based background dispatch.
- WebSocket-based real-time review prompts.
- Browser Notification API integration.
- Performance dashboard (`/api/stats`) with:
  - Total words
  - Strong words
  - Weak words
  - Accuracy percentage
  - Learning streak
- Render.com deployment support.

## Folder Structure
```text
project_root/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── auth.py
│   ├── scheduler.py
│   ├── services/
│   │   └── learning_engine.py
│   ├── routes/
│   │   ├── auth_routes.py
│   │   ├── word_routes.py
│   │   ├── learning_routes.py
│   │   └── stats_routes.py
│   └── templates/
│       ├── login.html
│       ├── signup.html
│       └── dashboard.html
├── requirements.txt
├── render.yaml
├── .env.example
├── .gitignore
└── README.md
```

## Local Setup
1. **Clone and enter project**
   ```bash
   git clone <your-repo-url>
   cd HARSH-VOCO
   ```
2. **Create venv & install dependencies**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure environment**
   ```bash
   cp .env.example .env
   ```
4. **Run app**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
5. Open:
   - `http://localhost:8000/` (login)
   - `http://localhost:8000/signup`
   - `http://localhost:8000/dashboard`

## Environment Variables
Set these in `.env` (or Render environment settings):
- `SECRET_KEY` - JWT signing key.
- `ACCESS_TOKEN_EXPIRE_MINUTES` - token lifetime in minutes.
- `DATABASE_URL` - defaults to SQLite file (`sqlite:///./vocabulary.db`).
- `PORT` - hosting port (Render sets this automatically).

## Render Deployment
1. Push repository to GitHub.
2. Create a **New Web Service** in Render.
3. Connect the repo.
4. Render auto-detects `render.yaml`:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Configure env vars (`SECRET_KEY`, etc.) in Render dashboard.

## Security Notes
- Passwords are hashed with bcrypt (`passlib[bcrypt]`).
- API routes use JWT bearer authentication.
- Use a strong `SECRET_KEY` in production.
- CORS is currently open (`*`) for easy integration; tighten for production domains.

## Run with main.py directly
```bash
python -m app.main
```
This respects:
```python
if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
```
