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
import base64

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=key)

app = FastAPI()

# Available free Gemini models
AVAILABLE_MODELS = {
    "gemini-2.5-flash":  "Gemini 2.5 Flash (Fastest, Recommended)",
    "gemini-2.0-flash": "Gemini 2.0 Flash (Fast)",
    "gemini-1.5-flash": "Gemini 1.5 Flash (Balanced)",
    "gemini-1.5-pro": "Gemini 1.5 Pro (Most Capable)",
}

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    image_base64: str | None = None
    image_mime_type: str | None = None
    model: str = "gemini-2.5-flash"

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

@app.get("/available-models")
async def get_available_models():
    """Get list of available Gemini models"""
    return {
        "models":  AVAILABLE_MODELS,
        "default_model": "gemini-2.5-flash"
    }

@app.post("/new-chat")
async def new_chat(authorization: str | None = Header(default=None)):
    """Create a new conversation and return conversation_id"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    supabase = get_supabase_client(jwt)
    try:
        user = supabase.auth.get_user(jwt)
    except Exception as e:  
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
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
    
    supabase = get_supabase_client(jwt)
    try:
        user = supabase.auth.get_user(jwt)
    except Exception as e:   
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    user_id = user.user. id
    admin_supabase = get_supabase_admin_client()
    
    try:
        response = admin_supabase.table("Chat_history_new").select(
            "conversation_id, messages, created_at, updated_at"
        ).eq("user_id", user_id).order("updated_at", desc=True).execute()
        
        conversations = []
        for chat in response.data:
            preview = "Empty chat"
            if chat["messages"] and len(chat["messages"]) > 0:
                for msg in chat["messages"]: 
                    if msg["role"] == "user":
                        preview = msg["content"][: 50] + "..." if len(msg["content"]) > 50 else msg["content"]
                        break
            
            conversations.append({
                "conversation_id": chat["conversation_id"],
                "preview": preview,
                "updated_at": chat["updated_at"],
                "created_at": chat["created_at"],
                "message_count": len(chat["messages"])
            })
        
        return {"conversations": conversations}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chat history: {str(e)}")

@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id:  str, authorization: str | None = Header(default=None)):
    """Get a specific conversation's messages"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    supabase = get_supabase_client(jwt)
    try:
        user = supabase.auth.get_user(jwt)
    except Exception as e:  
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    user_id = user.user.id
    admin_supabase = get_supabase_admin_client()
    
    try:
        response = admin_supabase. table("Chat_history_new").select("messages").eq(
            "conversation_id", conversation_id
        ).eq("user_id", user_id).single().execute()
        
        return {
            "conversation_id": conversation_id,
            "messages": response.data["messages"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=404, detail="Conversation not found")

@app.post("/chat")
async def chat(request: ChatRequest, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing JWT")
    
    jwt = authorization.split(" ", 1)[1]
    
    supabase = get_supabase_client(jwt)
    
    try:  
        user = supabase. auth.get_user(jwt)
    except Exception as e:  
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    user_id = user.user.id
    
    # Validate model selection
    selected_model = request.model if request.model in AVAILABLE_MODELS else "gemini-2.5-flash"
    
    # Build content list for Gemini
    content_parts = [request.message]
    
    # Add image if provided
    if request.image_base64 and request.image_mime_type:
        try:
            image_data = base64.b64decode(request. image_base64)
            # Use the correct Gemini format for images
            content_parts.append({
                "mime_type": request.image_mime_type,
                "data":  image_data
            })
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image data: {str(e)}")
    
    # Generate response from Gemini
    try:
        model = genai.GenerativeModel(selected_model)
        response = model. generate_content(content_parts)
        reply = response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")
    
    # Use admin client for insert/update
    admin_supabase = get_supabase_admin_client()
    
    conversation_id = request.conversation_id or str(uuid.uuid4())
    current_time_ist = datetime.now(IST).isoformat()
    
    # Create message objects
    new_message = {
        "role": "user",
        "content": request.message,
        "timestamp":  current_time_ist,
        "has_image": request.image_base64 is not None
    }
    
    new_reply = {
        "role": "assistant",
        "content": reply,
        "timestamp": current_time_ist,
        "model_used": selected_model
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
            "updated_at":  current_time_ist
        }).execute()
    
    return {
        "reply":  reply,
        "conversation_id": conversation_id,
        "model_used": selected_model
    }
