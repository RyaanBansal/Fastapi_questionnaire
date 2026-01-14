import streamlit as st
import requests
from supabase_client import get_supabase_client
import uuid

BACKEND_URL = "http://127.0.0.1:8000/chat"
NEW_CHAT_URL = "http://127.0.0.1:8000/new-chat"
CHAT_HISTORY_URL = "http://127.0.0.1:8000/chat-history"
CONVERSATION_URL = "http://127.0.0.1:8000/conversation"
st.set_page_config(page_title="Gemmini Chatbot", page_icon="🤖")

# Track login state
if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st. session_state:
    st. session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# Helper function to get auth headers
def get_headers():
    headers = {}
    if st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state. access_token}"
    return headers

# Helper function to load previous conversations
def load_chat_history():
    try:
        response = requests.get(CHAT_HISTORY_URL, headers=get_headers())
        return response.json().get("conversations", [])
    except Exception as e:
        st.error(f"Error loading chat history:  {e}")
        return []

# Helper function to load specific conversation
def load_conversation(conversation_id):
    try:
        response = requests.get(f"{CONVERSATION_URL}/{conversation_id}", headers=get_headers())
        data = response.json()
        return data.get("messages", [])
    except Exception as e: 
        st.error(f"Error loading conversation: {e}")
        return []

# ---------------- AUTH PAGE ----------------
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
                    st.success("✅ Account created successfully!  Please log in.")
                else:
                    st.error("❌ Sign-up failed.")
            except Exception as e: 
                st.error(f"Error:  {e}")

    with tab2:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            try:
                result = supabase. auth.sign_in_with_password({"email": email, "password": password})
                if result.user and result.session:
                    st.session_state.user = result.user
                    st.session_state. access_token = result.session. access_token
                    st. rerun()
                else: 
                    st.error("❌ Login failed.")
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- CHATBOT PAGE ----------------
def show_chatbot():
    st.title("🤖 Gemini Chatbot")
    st.success(f"Welcome, {st. session_state. user. email}!")

    # Sidebar for chat management
    with st. sidebar:
        st. header("💬 Chat Sessions")
        
        if st.button("➕ New Chat", use_container_width=True):
            # Create new chat
            try:
                response = requests.post(NEW_CHAT_URL, headers=get_headers())
                data = response. json()
                st.session_state.conversation_id = data. get("conversation_id")
                st.session_state.messages = []
                st.rerun()
            except Exception as e: 
                st.error(f"Error creating new chat: {e}")
        
        st.divider()
        
        st.subheader("📚 Previous Chats")
        
        # Load and display chat history
        conversations = load_chat_history()
        
        if conversations:
            for chat in conversations:
                # Highlight current conversation
                is_current = chat["conversation_id"] == st. session_state.conversation_id
                
                col1, col2 = st. columns([4, 1])
                
                with col1:
                    if st.button(
                        f"{'✓ ' if is_current else ''}{chat['preview'][: 30]}.. .",
                        use_container_width=True,
                        key=chat["conversation_id"]
                    ):
                        # Load this conversation
                        st.session_state.conversation_id = chat["conversation_id"]
                        st.session_state. messages = load_conversation(chat["conversation_id"])
                        st.rerun()
                
                # Optional: Show message count as small text
                st.caption(f"{chat['message_count']} messages")
        else:
            st.info("No previous chats.  Start a new one!")
        
        st.divider()
        st.write(f"**Current Chat ID:**")
        st.code(st.session_state.conversation_id or "No active chat", language="text")
        
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.access_token = None
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.rerun()

    # Display current messages
    for msg in st. session_state.messages:
        st.chat_message(msg["role"]).markdown(msg["content"])

    # Input box
    if prompt := st.chat_input("Type your message... "):
        # Show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        # Send to FastAPI backend
        try:
            response = requests.post(
                BACKEND_URL,
                json={
                    "message": prompt,
                    "conversation_id":  st.session_state.conversation_id
                },
                headers=get_headers()
            )
            data = response.json()
            reply = data.get("reply", "Error:  No reply received")
            st.session_state.conversation_id = data.get("conversation_id", st.session_state.conversation_id)
        except Exception as e:
            reply = f"⚠️ Backend error: {e}"

        # Show assistant reply
        st.session_state. messages.append({"role": "assistant", "content": reply})
        st.chat_message("assistant").markdown(reply)

# ---------------- ROUTING ----------------
if st.session_state.user:
    show_chatbot()
else:
    show_auth_page()
