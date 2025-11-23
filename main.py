"""
Multi-model AI Router (Fixed & Functional)

Features:
- ⚡ Groq (Llama 3) for high-speed Text
- 🎨 Google Gemini (Imagen 3) for Image Generation
- 🛡️ Pollinations.ai (Backup) ensures images always work even if keys fail
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import asyncio
import httpx
import base64
from groq import Groq
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Multi-model AI Router")

# -------------------- Config / Environment --------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Google GenAI for Text
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.get("/")
async def root():
    return {"status": "ok", "info": "POST /chat -> {'prompt': '...', 'mode': 'auto'}"}

# -------------------- Request/Response Models --------------------
class ChatRequest(BaseModel):
    prompt: str
    mode: Optional[str] = "auto"

class ChatResponse(BaseModel):
    model_used: str
    provider: str
    output: Dict[str, Any]

# -------------------- Classifier --------------------
IMAGE_KEYWORDS = {
    "image", "generate", "draw", "create", "illustrate", "picture",
    "logo", "avatar", "portrait", "scene", "render", "paint", "sketch","photo","photograph",
    "visual", "graphic", "design","cinematic","4k","8k","ultra hd"
    
}
CODE_KEYWORDS = {"code", "python", "function", "script", "bug", "algorithm","c","c++","java",
                 "javascript","html","css","ruby","go","rust","typescript"}

def classify_prompt(prompt: str) -> str:
    pl = prompt.lower()
    # If user specifically asks to "draw code" or "write code", prioritize code
    if any(w in pl for w in CODE_KEYWORDS) and "image" not in pl:
        return "code"
    # Check for image keywords
    for w in IMAGE_KEYWORDS:
        if w in pl:
            return "image"
    return "text"

# -------------------- Adapters --------------------
class BaseAdapter:
    name: str
    provider: str
    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

class GroqAdapter(BaseAdapter):
    name = "llama-3.3-70b-versatile"
    provider = "groq"

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("GROQ_API_KEY not set")

        loop = asyncio.get_running_loop()
        def call_groq():
            try:
                # Force JSON mode if needed, otherwise standard text
                completion = self.client.chat.completions.create(
                    model=self.name,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1024,
                )
                return completion.choices[0].message.content
            except Exception as e:
                return {"error": str(e)}

        result = await loop.run_in_executor(None, call_groq)
        if isinstance(result, dict) and "error" in result:
            raise Exception(result["error"])
        return {"text": result, "type": "text"}


class GeminiImageAdapter(BaseAdapter):
    name = "imagen-3.0-generate-001"
    provider = "google-gemini"
    
    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")

        # 1. Try Official Google Imagen 3 (REST API)
        # Note: This requires your API Key to be whitelisted for Imagen 3.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.name}:predict"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"x-goog-api-key": GEMINI_API_KEY}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    b64_image = data["predictions"][0]["bytesBase64Encoded"]
                    return {"image_url": f"data:image/png;base64,{b64_image}", "type": "image"}
                
                # If 404/403, the key isn't whitelisted for Imagen. Fallback to Pollinations.
                print(f"Gemini Imagen failed ({resp.status_code}). Switching to backup.")
            except Exception as e:
                print(f"Gemini connection failed: {e}")

        # 2. Fallback: Pollinations.ai (No Key Required)
        # This ensures your frontend NEVER breaks.
        print("Using Pollinations.ai fallback")
        encoded_prompt = prompt.replace(" ", "%20")
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        return {
            "image_url": image_url, 
            "type": "image", 
            "note": "Generated via Fallback (Pollinations) due to Gemini permissions."
        }


# -------------------- Router Logic --------------------
GROQ_ADAPTER = GroqAdapter()
GEMINI_ADAPTER = GeminiImageAdapter()

async def select_adapter(prompt: str, mode_hint: Optional[str] = "auto"):
    classification = classify_prompt(prompt)
    
    # Explicit Hint Overrides
    if mode_hint == "image":
        return GEMINI_ADAPTER, {"reason": "user_hint_image"}
    if mode_hint == "text":
        return GROQ_ADAPTER, {"reason": "user_hint_text"}

    # Automatic Routing
    if classification == "image":
        return GEMINI_ADAPTER, {"reason": "keyword_image"}
    
    return GROQ_ADAPTER, {"reason": "default_text"}

# -------------------- API Endpoint --------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    prompt = req.prompt
    adapter, meta = await select_adapter(prompt, req.mode)
    
    try:







         
        out = await adapter.generate(prompt)
    except Exception as e:
        # --- FALLBACK LOGIC ---
        # Only fallback if we started with Text. 
        # (Image fallback is already handled inside GeminiAdapter to ensure we don't ask Groq to draw)
        if adapter.provider == "groq":
            # If Groq fails, you could try Gemini Text here if you implemented a GeminiTextAdapter
            raise HTTPException(status_code=500, detail=f"Groq Failed: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail=f"Image Gen Failed: {str(e)}")

    return ChatResponse(
        model_used=adapter.name,
        provider=adapter.provider,
        output={"meta": meta, "result": out}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)