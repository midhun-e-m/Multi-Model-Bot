import os
import asyncio
import httpx
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta

# PIP INSTALL: fastapi uvicorn sqlmodel passlib[bcrypt] python-jose groq google-generativeai python-dotenv argon2-cffi
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from passlib.context import CryptContext
from jose import JWTError, jwt
from groq import Groq
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(override=True)

# ================= CONFIGURATION =================
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key")
ALGORITHM = "HS256"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if GEMINI_API_KEY: genai.configure(api_key=GEMINI_API_KEY)

# ================= DATABASE MODELS =================
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str

class ChatHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    session_id: str = Field(index=True)
    prompt: str
    response: str
    model_used: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

sqlite_file_name = "router_database.db"
engine = create_engine(f"sqlite:///{sqlite_file_name}", connect_args={"check_same_thread": False})

def create_db_and_tables(): SQLModel.metadata.create_all(engine)
def get_session():
    with Session(engine) as session: yield session

# ================= AUTHENTICATION =================
# Using "argon2" for better compatibility than bcrypt
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_password_hash(p): return pwd_context.hash(p)
def verify_password(p, h): return pwd_context.verify(p, h)

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=60)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username: raise HTTPException(status_code=401)
    except JWTError: raise HTTPException(status_code=401)
    
    user = session.exec(select(User).where(User.username == username)).first()
    if not user: raise HTTPException(status_code=401)
    return user

# ================= AI ADAPTERS =================
class BaseAdapter:
    name: str
    provider: str
    async def generate(self, prompt: str) -> Dict[str, Any]: raise NotImplementedError

class GroqAdapter(BaseAdapter):
    name = "llama-3.3-70b-versatile"
    provider = "groq"
    def __init__(self): self.client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    
    async def generate(self, prompt: str) -> Dict[str, Any]:
        if not self.client: raise RuntimeError("GROQ_API_KEY missing")
        loop = asyncio.get_running_loop()
        def call():
            return self.client.chat.completions.create(
                model=self.name, messages=[{"role": "user", "content": prompt}]
            ).choices[0].message.content
        return {"text": await loop.run_in_executor(None, call), "type": "text"}

class GeminiImageAdapter(BaseAdapter):
    name = "imagen-3.0-generate-001"
    provider = "google-gemini"
    
    async def generate(self, prompt: str) -> Dict[str, Any]:
        # 1. Try Google Gemini
        if GEMINI_API_KEY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.name}:predict"
            headers = {"x-goog-api-key": GEMINI_API_KEY}
            payload = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        b64 = resp.json()['predictions'][0]['bytesBase64Encoded']
                        return {"image_url": f"data:image/png;base64,{b64}", "type": "image"}
                except: pass
        
        # 2. Fallback
        return {"image_url": f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}", "type": "image"}

GROQ_ADAPTER = GroqAdapter()
GEMINI_ADAPTER = GeminiImageAdapter()

# ================= ROUTER LOGIC (RESTORED) =================
IMAGE_KEYWORDS = {
    "image", "generate", "draw", "create", "illustrate", "picture",
    "logo", "avatar", "portrait", "scene", "render", "paint", "sketch",
    "photo", "photograph", "visual", "graphic", "design", "cinematic", "4k"
}

def determine_adapter(prompt: str, mode_hint: str) -> BaseAdapter:
    # 1. Force Hint
    if mode_hint == "image": return GEMINI_ADAPTER
    if mode_hint == "text": return GROQ_ADAPTER
    
    # 2. Keyword Search
    prompt_lower = prompt.lower()
    
    # If explicitly asking for code, force text even if "image" is mentioned
    if "code" in prompt_lower or "function" in prompt_lower:
        return GROQ_ADAPTER
        
    # Check for image triggers
    for word in IMAGE_KEYWORDS:
        if word in prompt_lower:
            return GEMINI_ADAPTER
            
    # Default to text
    return GROQ_ADAPTER

# ================= API ROUTES =================
app = FastAPI()

@app.on_event("startup")
def on_startup(): create_db_and_tables()

# --- Auth Routes ---
@app.post("/register")
def register(user: dict, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.username == user['username'])).first():
        raise HTTPException(400, "Username taken")
    session.add(User(username=user['username'], hashed_password=get_password_hash(user['password'])))
    session.commit()
    return {"msg": "Created"}

@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form.username)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(400, "Bad creds")
    return {"access_token": create_access_token(data={"sub": user.username}), "token_type": "bearer"}

# --- Chat Routes ---
class ChatRequest(BaseModel):
    prompt: str
    session_id: str
    mode: Optional[str] = "auto"

@app.post("/chat")
async def chat(req: ChatRequest, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    # 1. Use the robust switching logic
    adapter = determine_adapter(req.prompt, req.mode)
    
    try:
        # 2. Generate
        out = await adapter.generate(req.prompt)
        
        # 3. Save to DB with Session ID
        text_out = out.get("text") or out.get("image_url")
        session.add(ChatHistory(
            user_id=user.id, 
            session_id=req.session_id, 
            prompt=req.prompt, 
            response=str(text_out), 
            model_used=adapter.name
        ))
        session.commit()
        
        return {"output": out, "model": adapter.name}
    except Exception as e: 
        raise HTTPException(500, str(e))

@app.get("/sessions")
def get_sessions(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    # Get all history for user, ordered by time
    statement = select(ChatHistory.session_id, ChatHistory.prompt, ChatHistory.timestamp)\
        .where(ChatHistory.user_id == user.id)\
        .order_by(ChatHistory.timestamp.desc())
    results = session.exec(statement).all()
    
    # Filter to get unique sessions
    seen = set()
    unique_sessions = []
    for sid, prompt, time in results:
        if sid not in seen:
            unique_sessions.append({"id": sid, "title": prompt[:40], "time": time})
            seen.add(sid)
    return unique_sessions

@app.get("/history/{session_id}")
def get_history(session_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(ChatHistory)
                        .where(ChatHistory.user_id == user.id, ChatHistory.session_id == session_id)
                        .order_by(ChatHistory.timestamp)).all()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)