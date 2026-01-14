from fastapi import FastAPI, Header, HTTPException
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from supabase_client import get_supabase_client, verify_jwt, get_supabase_admin_client
import uuid
from datetime import datetime
import pytz

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=key)

app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None

class NewChatRequest(BaseModel):
    pass

# IST timezone
IST = pytz.timezone('Asia/Kolkata')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/new-chat")
async def new_chat(authorization: str | None = Header(default=None)):
    """Create a new conversation and return conversation_id"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    # Verify token is valid
    supabase = get_supabase_client(jwt)
    try:
        user = supabase.auth.get_user(jwt)
    except Exception as e:  
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    # Generate new conversation ID
    conversation_id = str(uuid.uuid4())
    
    return {
        "conversation_id":  conversation_id,
        "message": "New chat created"
    }

@app.get("/chat-history")
async def get_chat_history(authorization: str | None = Header(default=None)):
    """Get all previous chat sessions for the user"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    # Verify token is valid
    supabase = get_supabase_client(jwt)
    try:
        user = supabase.auth.get_user(jwt)
    except Exception as e: 
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    user_id = user.user. id
    
    # Get admin client to fetch all conversations for user
    admin_supabase = get_supabase_admin_client()
    
    try:
        # Fetch all conversations for this user, ordered by updated_at descending
        response = admin_supabase.table("Chat_history_new").select(
            "conversation_id, messages, created_at, updated_at"
        ).eq("user_id", user_id).order("updated_at", desc=True).execute()
        
        conversations = []
        for chat in response.data:
            # Get the first user message as preview
            preview = "Empty chat"
            if chat["messages"] and len(chat["messages"]) > 0:
                for msg in chat["messages"]:
                    if msg["role"] == "user":
                        preview = msg["content"][: 50] + "..." if len(msg["content"]) > 50 else msg["content"]
                        break
            
            conversations.append({
                "conversation_id":  chat["conversation_id"],
                "preview": preview,
                "updated_at": chat["updated_at"],
                "created_at": chat["created_at"],
                "message_count": len(chat["messages"])
            })
        
        return {
            "conversations": conversations
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chat history:  {str(e)}")

@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str, authorization: str | None = Header(default=None)):
    """Get a specific conversation's messages"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    # Verify token is valid
    supabase = get_supabase_client(jwt)
    try:
        user = supabase.auth.get_user(jwt)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    user_id = user.user.id
    
    # Get admin client
    admin_supabase = get_supabase_admin_client()
    
    try:
        response = admin_supabase.table("Chat_history_new").select("messages").eq(
            "conversation_id", conversation_id
        ).eq("user_id", user_id).single().execute()
        
        return {
            "conversation_id": conversation_id,
            "messages":  response.data["messages"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=404, detail="Conversation not found")

@app.post("/chat")
async def chat(request: ChatRequest, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    # Pass JWT to Supabase client
    supabase = get_supabase_client(jwt)
    
    # Verify token is valid
    try: 
        user = supabase. auth.get_user(jwt)
    except Exception as e: 
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    user_id = user.user.id
    
    # Generate response from Gemini
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(request.message)
    reply = response.text if hasattr(response, "text") else str(response)
    
    # Use admin client for insert/update (bypasses RLS)
    admin_supabase = get_supabase_admin_client()
    
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    # Get current time in IST
    current_time_ist = datetime.now(IST).isoformat()
    
    # New message and reply objects
    new_message = {
        "role": "user",
        "content": request.message,
        "timestamp": current_time_ist
    }
    
    new_reply = {
        "role":  "assistant",
        "content":  reply,
        "timestamp": current_time_ist
    }
    
    # Check if conversation exists
    try:
        existing = admin_supabase.table("Chat_history_new").select("messages").eq(
            "conversation_id", conversation_id
        ).eq("user_id", user_id).single().execute()
        
        # Update existing conversation
        messages = existing.data["messages"]
        messages.append(new_message)
        messages.append(new_reply)
        
        admin_supabase.table("Chat_history_new").update({
            "messages": messages,
            "updated_at": current_time_ist
        }).eq("conversation_id", conversation_id).eq("user_id", user_id).execute()
        
    except Exception as e:
        # Create new conversation
        admin_supabase.table("Chat_history_new").insert({
            "user_id": user_id,
            "conversation_id": conversation_id,
            "messages": [new_message, new_reply],
            "created_at": current_time_ist,
            "updated_at": current_time_ist
        }).execute()
    
    return {
        "reply": reply,
        "conversation_id": conversation_id
    }
