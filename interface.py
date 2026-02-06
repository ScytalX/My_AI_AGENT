import streamlit as st
import google.generativeai as genai
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Mon Super Prof IA", page_icon="👨‍🏫", layout="wide")

# --- CONNEXION GEMINI ---
os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
MODEL_NAME = "gemini-pro" # Utilise la version rapide

# --- MÉMOIRE DE LA SESSION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat" not in st.session_state:
    model = genai.GenerativeModel(MODEL_NAME)
    st.session_state.chat = model.start_chat(history=[])

# --- INTERFACE ---
st.title("🎓 Assistant d'Études Intelligent")

with st.sidebar:
    st.header("📂 Documents de cours")
    pdf_file = st.file_uploader("Upload ton PDF ici", type="pdf")
    if st.button("🗑️ Effacer la discussion"):
        st.session_state.messages = []
        st.session_state.chat = genai.GenerativeModel(MODEL_NAME).start_chat(history=[])
        st.rerun()

# Affichage des messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrée utilisateur
if prompt := st.chat_input("Pose ta question ici..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Le prof réfléchit..."):
            try:
                # Gestion de l'envoi du PDF lors du premier message
                if pdf_file and len(st.session_state.messages) == 1:
                    with open("temp.pdf", "wb") as f:
                        f.write(pdf_file.getbuffer())
                    doc = genai.upload_file("temp.pdf")
                    response = st.session_state.chat.send_message([prompt, doc])
                else:
                    response = st.session_state.chat.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Erreur : {e}")