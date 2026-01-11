import streamlit as st
import requests
from supabase_client import get_supabase_client   # your Supabase client setup

BACKEND_URL = "http://127.0.0.1:8000/chat"
st.set_page_config(page_title="Groq Chatbot", page_icon="🤖")

# Track login state
if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------- AUTH PAGE ----------------
def show_auth_page():
    st.title("🔑 Login to Groq Chatbot")

    tab1, tab2 = st.tabs(["Sign Up", "Login"])

    with tab1:
        st.subheader("Create an Account")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Sign Up"):
            try:
                supabase = get_supabase_client()
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
                    st.session_state.access_token = result.session.access_token  # JWT
                    st.rerun()   # reload to show chatbot
                else:
                    st.error("❌ Login failed.")
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- CHATBOT PAGE ----------------
def show_chatbot():
    st.title("🤖 Groq Chatbot (FastAPI + Streamlit)")
    st.success(f"Welcome, {st.session_state.user.email}!")

    # Display previous messages
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).markdown(msg["content"])

    # Input box
    if prompt := st.chat_input("Type your message..."):
        # Show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        # Send to FastAPI backend with JWT
        headers = {}
        if st.session_state.access_token:
            headers["Authorization"] = f"Bearer {st.session_state.access_token}"

        try:
            response = requests.post(BACKEND_URL, json={"message": prompt}, headers=headers)
            reply = response.json().get("reply", "Error: No reply received")
        except Exception as e:
            reply = f"⚠️ Backend error: {e}"

        # Show assistant reply
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.chat_message("assistant").markdown(reply)

    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.access_token = None
        st.session_state.messages = []
        st.rerun()

# ---------------- ROUTING ----------------
if st.session_state.user:
    show_chatbot()
else:
    show_auth_page()