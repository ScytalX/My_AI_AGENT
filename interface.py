import streamlit as st
import google.generativeai as genai
import PyPDF2
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Mon Super Prof IA", page_icon="🎓", layout="wide")

# --- CONNEXION GEMINI ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ Clé API introuvable. Vérifie tes Secrets Streamlit.")
    st.stop()

# --- CHOIX DU MODÈLE (Basé sur tes captures d'écran) ---
MODEL_NAME = "gemini-2.0-flash" 

# --- FONCTION : EXTRACTION PDF ---
def get_pdf_text(uploaded_file):
    text = ""
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        for page in reader.pages:
            text += page.extract_text()
    except Exception as e:
        return f"Erreur lecture PDF: {e}"
    return text

# --- MÉMOIRE DE LA SESSION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "model", 
        "content": "Salut ! Je suis prêt. Envoie un PDF pour commencer ou pose une question."
    })

# --- BARRE LATÉRALE (UPLOAD) ---
with st.sidebar:
    st.header("📂 Tes Cours")
    uploaded_file = st.file_uploader("Charge ton PDF ici", type=["pdf"])
    
    if st.button("🗑️ Reset"):
        st.session_state.messages = []
        st.rerun()

    # Traitement du PDF
    if uploaded_file and "pdf_processed" not in st.session_state:
        with st.spinner("Analyse du cours..."):
            raw_text = get_pdf_text(uploaded_file)
            if raw_text:
                # On injecte le cours en contexte caché
                prompt_context = f"Voici le cours de référence (PDF) :\n\n{raw_text}\n\nUtilise ce contenu pour répondre aux questions."
                st.session_state.messages.append({"role": "user", "content": prompt_context})
                st.session_state.messages.append({"role": "model", "content": "Document analysé ! Je t'écoute."})
                st.session_state.pdf_processed = True 

# --- INTERFACE DE CHAT ---
st.title("🎓 Assistant d'Études (Gemini 2.0)")

# Affichage des messages (on cache le texte brut du PDF pour la lisibilité)
for msg in st.session_state.messages:
    if msg["role"] == "user" and "Voici le cours de référence" in msg["content"]:
        continue 
    
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Zone de saisie
if prompt := st.chat_input("Pose ta question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            
            # Préparation de l'historique pour l'API
            history_gemini = []
            for m in st.session_state.messages:
                role = "model" if m["role"] == "assistant" or m["role"] == "model" else "user"
                history_gemini.append({"role": role, "parts": [m["content"]]})
            
            # Génération
            chat = model.start_chat(history=history_gemini[:-1])
            response = chat.send_message(prompt, stream=True)
            
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"Erreur API : {e}")