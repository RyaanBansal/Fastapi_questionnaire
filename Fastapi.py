from fastapi import FastAPI, Header, HTTPException
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from supabase_client import get_supabase_client, verify_jwt, get_supabase_admin_client

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=key)

app = FastAPI()

class ChatRequest(BaseModel):
    message: str


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: ChatRequest, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    # ✅ Pass JWT to Supabase client
    supabase = get_supabase_client(jwt)
    
    # This will now work because Supabase knows the authenticated user
    try:
        user = supabase.auth.get_user(jwt)  # Verify token is valid
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    user_id = user.user. id
    
    # Generate response
    model = genai. GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(request.message)
    reply = response.text if hasattr(response, "text") else str(response)
    
    # Use admin client for insert (bypasses RLS)
    admin_supabase = get_supabase_admin_client()
    admin_supabase.table("Chat_history").insert({
        "message": request.message,
        "reply":  reply,
        "user_id": user_id
    }).execute()
    
    return {"reply": reply}