import streamlit as st
import google.generativeai as genai
import PyPDF2
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Mon Super Prof IA", page_icon="🎓", layout="wide")

# --- CONNEXION GEMINI ---
# On sécurise la récupération de la clé
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ Clé API introuvable. Assure-toi qu'elle est bien dans les Secrets Streamlit.")
    st.stop()

# CORRECTION DU MODÈLE : On passe à la version Flash (plus rapide et compatible)
MODEL_NAME = "gemini-1.5-flash" 

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
    # Message d'accueil du système
    st.session_state.messages.append({
        "role": "model", 
        "content": "Salut ! Je suis ton assistant d'études. Envoie-moi un PDF de cours dans la barre latérale pour commencer."
    })

# --- BARRE LATÉRALE (UPLOAD) ---
with st.sidebar:
    st.header("📂 Tes Cours")
    uploaded_file = st.file_uploader("Charge ton PDF ici", type=["pdf"])
    
    # Bouton Reset
    if st.button("🗑️ Nouvelle discussion"):
        st.session_state.messages = []
        st.rerun()

    # Traitement du PDF s'il vient d'être chargé
    if uploaded_file and "pdf_processed" not in st.session_state:
        with st.spinner("Analyse du cours en cours..."):
            raw_text = get_pdf_text(uploaded_file)
            if raw_text:
                # On injecte le cours directement dans la mémoire de l'IA
                prompt_context = f"Voici le contenu du cours PDF de l'étudiant. Utilise ces informations pour répondre à ses futures questions :\n\n{raw_text}"
                st.session_state.messages.append({"role": "user", "content": prompt_context})
                st.session_state.messages.append({"role": "model", "content": "J'ai lu ton document ! Je suis prêt à t'aider. Pose-moi une question dessus."})
                st.session_state.pdf_processed = True # Marqueur pour ne pas recharger en boucle

# --- INTERFACE DE CHAT ---
st.title("🎓 Assistant d'Études Intelligent")

# Afficher l'historique (on masque le gros pavé de texte du PDF pour que ce soit propre)
for msg in st.session_state.messages:
    # On n'affiche pas les messages "système" trop longs (le contenu du PDF)
    if msg["role"] == "user" and "Voici le contenu du cours PDF" in msg["content"]:
        continue 
    
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Zone de saisie
if prompt := st.chat_input("Pose ta question sur le cours..."):
    # 1. Afficher message utilisateur
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Générer réponse
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # On envoie tout l'historique à Gemini pour qu'il ait le contexte
            model = genai.GenerativeModel(MODEL_NAME)
            
            # Formatage de l'historique pour l'API Gemini
            history_gemini = []
            for m in st.session_state.messages:
                # Adaptation des rôles (model -> model, user -> user)
                role = "model" if m["role"] == "assistant" or m["role"] == "model" else "user"
                history_gemini.append({"role": role, "parts": [m["content"]]})
            
            # On retire le dernier message (le prompt actuel) car send_message le prend en argument ou on utilise generate_content sur la liste
            # Méthode simple : chat session
            chat = model.start_chat(history=history_gemini[:-1])
            response = chat.send_message(prompt, stream=True)
            
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
            # 3. Sauvegarder réponse
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"Erreur API : {e}")