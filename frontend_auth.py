import streamlit as st
import requests
from supabase_client import get_supabase_client
import uuid
import base64
from PIL import Image
from io import BytesIO

BACKEND_URL = "http://127.0.0.1:8000/chat"
NEW_CHAT_URL = "http://127.0.0.1:8000/new-chat"
CHAT_HISTORY_URL = "http://127.0.0.1:8000/chat-history"
CONVERSATION_URL = "http://127.0.0.1:8000/conversation"
MODELS_URL = "http://127.0.0.1:8000/available-models"

st.set_page_config(page_title="Gemmini Chatbot", page_icon="🤖", layout="wide")

# Track login state
if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gemini-2. 5-flash"
if "available_models" not in st.session_state:
    st.session_state.available_models = {}
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None

# Helper functions
def get_headers():
    headers = {}
    if st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    return headers

def load_available_models():
    try:
        response = requests.get(MODELS_URL, headers=get_headers())
        data = response.json()
        st.session_state.available_models = data.get("models", {})
        return data.get("models", {})
    except Exception as e:
        st.error(f"Error loading models: {e}")
        return {}

def load_chat_history():
    try:
        response = requests.get(CHAT_HISTORY_URL, headers=get_headers())
        return response.json().get("conversations", [])
    except Exception as e:
        st.error(f"Error loading chat history: {e}")
        return []

def load_conversation(conversation_id):
    try:
        response = requests.get(f"{CONVERSATION_URL}/{conversation_id}", headers=get_headers())
        data = response.json()
        return data.get("messages", [])
    except Exception as e:
        st.error(f"Error loading conversation: {e}")
        return []

def image_to_base64(image_file):
    """Convert uploaded image to base64 string"""
    return base64.b64encode(image_file.read()).decode("utf-8")

def get_mime_type(file_name):
    """Get MIME type from file name"""
    extension = file_name.split(".")[-1].lower()
    mime_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp"
    }
    return mime_types.get(extension, "image/jpeg")

# --------AUTH PAGE --------
def show_auth_page():
    st.title("🔑 Login to Gemini Chatbot")

    tab1, tab2 = st.tabs(["Sign Up", "Login"])
    
    supabase = get_supabase_client()

    with tab1:
        st.subheader("Create an Account")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Sign Up"):
            try:
                result = supabase.auth.sign_up({"email": email, "password": password})
                if result.user:
                    st.success("✅ Account created successfully! Please log in.")
                else:
                    st.error("❌ Sign-up failed.")
            except Exception as e:  
                st.error(f"Error: {e}")

    with tab2:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            try:
                result = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if result.user and result.session:     
                    st.session_state.user = result.user
                    st.session_state.access_token = result.session.access_token
                    load_available_models()
                    st.rerun()
                else:
                    st.error("❌ Login failed.")
            except Exception as e:  
                st.error(f"Error:  {e}")

# --------CHATBOT PAGE --------
def show_chatbot():
    st.title("🤖 Gemini Chatbot")
    st.success(f"Welcome, {st.session_state.user.email}!")

    # Sidebar for chat management
    with st.sidebar:
        st.header("💬 Chat Sessions")
        
        if st.button("➕ New Chat", use_container_width=True):
            try:
                response = requests.post(NEW_CHAT_URL, headers=get_headers())
                data = response.json()
                st.session_state.conversation_id = data.get("conversation_id")
                st.session_state.messages = []
                st.session_state.uploaded_image = None
                st.rerun()
            except Exception as e:
                st.error(f"Error creating new chat: {e}")
        
        st.divider()
        
        # Model Selection
        st.subheader("🤖 Model Selection")
        
        if not st.session_state.available_models:
            load_available_models()
        
        model_options = st.session_state.available_models or {
            "gemini-2.5-flash": "Gemini 2.5 Flash (Fastest, Recommended)",
            "gemini-2.0-flash": "Gemini 2.0 Flash (Fast)",
            "gemini-1.5-flash": "Gemini 1.5 Flash (Balanced)",
            "gemini-1.5-pro": "Gemini 1.5 Pro (Most Capable)",
        }
        
        selected = st.selectbox(
            "Choose a model:",
            options=list(model_options.keys()),
            format_func=lambda x: model_options[x],
            index=list(model_options.keys()).index(st.session_state.selected_model) if st.session_state.selected_model in model_options else 0,
            key="model_selector"
        )
        
        st.session_state.selected_model = selected
        
        st.caption("💡 Flash models are faster, Pro is more capable")
        
        st.divider()
        
        st.subheader("📚 Previous Chats")
        
        conversations = load_chat_history()
        
        if conversations:
            for chat in conversations:
                is_current = chat["conversation_id"] == st.session_state.conversation_id
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    if st.button(
                        f"{'✓ ' if is_current else ''}{chat['preview'][:      30]}..      .",
                        use_container_width=True,
                        key=chat["conversation_id"]
                    ):
                        st.session_state.conversation_id = chat["conversation_id"]
                        st.session_state.messages = load_conversation(chat["conversation_id"])
                        st.session_state.uploaded_image = None
                        st.rerun()
                
                st.caption(f"{chat['message_count']} messages")
        else:
            st.info("No previous chats. Start a new one!")
        
        st.divider()
        st.write(f"**Current Chat ID:**")
        st.code(st.session_state.conversation_id or "No active chat", language="text")
        
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.access_token = None
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.session_state.selected_model = "gemini-2.5-flash"
            st.session_state.uploaded_image = None
            st.rerun()

    # Create a container for messages that will scroll
    message_container = st.container()
    
    with message_container:
        # Display current messages
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("has_image"):
                    st.caption("📷 Image attached")
                if msg["role"] == "assistant" and msg.get("model_used"):
                    st.caption(f"🤖 {msg['model_used']}")

    # Separator
    st.markdown("---")
    
    # Image preview section (ultra compact, above input)
    if st.session_state.uploaded_image:
        col_img, col_btn = st.columns([0.08, 0.02], gap="small")
        
        with col_img:
            st.image(st.session_state.uploaded_image, width=60, use_container_width=True)
        
        with col_btn:
            if st.button("✕", key="remove_image_btn", help="Remove image"):
                st.session_state.uploaded_image = None
                # Clear the file uploader by deleting its session state
                if "image_uploader" in st.session_state:
                    del st.session_state["image_uploader"]
                st.rerun()

    # Input section - ALWAYS AT BOTTOM
    col1, col2 = st.columns([0.15, 0.85], gap="small")
    
    with col1:
        uploaded_file = st.file_uploader(
            "📎",
            type=["jpg", "jpeg", "png", "gif", "webp"],
            label_visibility="collapsed",
            key="image_uploader"
        )
        # Store uploaded file in session state without rerunning
        if uploaded_file is not None:
            st.session_state.uploaded_image = uploaded_file
    
    with col2:
        prompt = st.chat_input("Type your message...")
    
    # Process message and image only when chat input is submitted
    if prompt:   
        # Display user message
        message_text = prompt
        st.session_state.messages.append({
            "role": "user",
            "content": message_text,
            "has_image": st.session_state.uploaded_image is not None
        })
        
        with st.chat_message("user"):
            st.markdown(message_text)
            if st.session_state.uploaded_image:
                st.image(st.session_state.uploaded_image, width=200)

        # Prepare image data
        image_base64 = None
        image_mime_type = None
        
        if st.session_state.uploaded_image:
            image_base64 = image_to_base64(st.session_state.uploaded_image)
            image_mime_type = get_mime_type(st.session_state.uploaded_image.name)

        # Send to backend
        try:   
            with st.spinner("🤖 Thinking...  "):
                response = requests.post(
                    BACKEND_URL,
                    json={
                        "message": prompt,
                        "conversation_id": st.session_state.conversation_id,
                        "image_base64": image_base64,
                        "image_mime_type": image_mime_type,
                        "model": st.session_state.selected_model
                    },
                    headers=get_headers()
                )
                data = response.json()
                reply = data.get("reply", "Error:  No reply received")
                st. session_state.conversation_id = data.get("conversation_id", st.session_state.conversation_id)
        except Exception as e:   
            reply = f"⚠️ Backend error: {e}"

        # Display assistant reply
        st. session_state.messages.append({
            "role": "assistant",
            "content": reply,
            "model_used": st.session_state.selected_model
        })
        
        with st.chat_message("assistant"):
            st.markdown(reply)
            st.caption(f"🤖 {st.session_state.selected_model}")
        
        # Clear uploaded image after sending - AUTOMATIC
        st.session_state.uploaded_image = None
        # Clear the file uploader by deleting its session state
        if "image_uploader" in st.session_state:
            del st.session_state["image_uploader"]
        st.rerun()

# --------ROUTING --------
if st.session_state.user:
    show_chatbot()
else:
    show_auth_page()
