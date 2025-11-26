# 🔮 Nexus AI – Multi-Model Router with Login & Chat History

Nexus AI is a **multi-model AI router** with:

- 🔐 User authentication (register + login with JWT)
- 💬 Per-user chat sessions with **saved history**
- 🤖 Smart routing between **Groq (Llama 3)** for text and **Google Imagen / Pollinations** for images
- 🖥️ Clean **Streamlit UI** + **FastAPI** backend
- 🗄️ SQLite + SQLModel for users and chat logs

---

## ✨ Features

- **Multi-Model Routing**
  - Routes prompts to **Groq Llama 3** for text.
  - Routes to **Google Imagen 3** for images.
  - Falls back to **Pollinations.ai** if Gemini image API fails.
  - Auto-detects image vs text using keywords and optional `mode` hint.

- **Authentication**
  - User **registration** (`/register`)
  - **Login** with OAuth2 password flow (`/token`)
  - Access tokens using **JWT** (`Authorization: Bearer <token>`)

- **Chat History & Sessions**
  - Each conversation has a **session ID**.
  - All chats are stored per user in `router_database.db`.
  - Sidebar UI shows your past sessions; you can reopen and continue them.

- **Frontend (Streamlit)**
  - Login / Register screen.
  - Chat UI with:
    - Text messages
    - Generated images shown inline
  - Session list (archives) in sidebar.
  - Quick-start prompt buttons on empty chat.

---

## 🧱 Tech Stack

- **Backend**
  - [FastAPI](https://fastapi.tiangolo.com/)
  - [SQLModel](https://sqlmodel.tiangolo.com/) + SQLite
  - [python-jose](https://python-jose.readthedocs.io/) for JWT
  - [argon2-cffi](https://pypi.org/project/argon2-cffi/) via Passlib for password hashing
  - [Groq Python SDK](https://github.com/groq/groq-python)
  - `httpx` for calling Google Imagen / Pollinations

- **Frontend**
  - [Streamlit](https://streamlit.io/)

---

## 📂 Project Structure

```text
.
├── main.py              # FastAPI backend (auth, routing, chat, DB models)
├── frontend.py          # Streamlit UI (login + chat + history)
├── router_database.db   # SQLite database (auto-created)
├── .env                 # Environment variables (not committed)
├── .gitignore
└── README.md
ℹ️ router_database.db is created automatically on startup if it doesn’t exist.

⚙️ Setup & Installation
1. Clone the repository
bash
Copy code
git clone https://github.com/<your-username>/Multi-Model-Bot.git
cd Multi-Model-Bot
2. Create & activate a virtual environment (recommended)
bash
Copy code
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate
3. Install dependencies
bash
Copy code
pip install fastapi uvicorn sqlmodel passlib[argon2] python-jose[cryptography] \
            groq google-generativeai python-dotenv argon2-cffi \
            streamlit httpx requests
(You can also move these into a requirements.txt later.)

4. Environment variables
Create a .env file in the project root:

env
Copy code
SECRET_KEY=your_super_secret_key
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_or_google_image_key
Do not commit .env to Git. Make sure it’s in .gitignore.

🚀 Running the App
You need to run backend and frontend separately.

1️⃣ Start the FastAPI backend
bash
Copy code
uvicorn main:app --reload
Runs on: http://127.0.0.1:8000

API docs: http://127.0.0.1:8000/docs

This will:

Create router_database.db (if not present)

Set up User + ChatHistory tables

2️⃣ Start the Streamlit frontend
In a new terminal (same venv):

bash
Copy code
streamlit run frontend.py
Default: http://localhost:8501

🔐 Auth Flow
Register a new user in the UI (Register tab) or via API:

POST /register with JSON:

json
Copy code
{ "username": "test", "password": "secret" }
Login:

POST /token with form data:

username, password

Returns: access_token

Streamlit stores the token and sends it in Authorization headers for:

/chat

/sessions

/history/{session_id}

🧠 Routing Logic (Text vs Image)
The router uses:

Explicit mode from frontend ("text", "image", or "auto")

Keyword detection:

python
Copy code
IMAGE_KEYWORDS = {
    "image", "generate", "draw", "create", "illustrate", "picture",
    "logo", "avatar", "portrait", "scene", "render", "paint", "sketch",
    "photo", "photograph", "visual", "graphic", "design", "cinematic", "4k"
}
Special case:

If the prompt mentions code or function, it forces text model, even if image appears in the prompt.

📦 Database
Uses SQLite via SQLModel.

Models:

User: id, username, hashed_password

ChatHistory: id, user_id, session_id, prompt, response, model_used, timestamp

Database file: router_database.db (can be ignored in .gitignore if you don’t want to track it)

🔮 Future Improvements (Ideas)
Refresh tokens + logout endpoint.

Per-model usage stats per user.

Export chat history as Markdown / JSON.

Add support for more models (OpenAI, local models, etc.).

Dockerize backend + frontend for easy deployment.

📝 License
Add your preferred license here (MIT, Apache-2.0, etc.).

yaml
Copy code

---

If you want, next step I can also:

- Give you a `requirements.txt` for this exact project.
- Give you a `.gitignore` that ignores `.env`, `router_database.db`, and `__pycache__`.
