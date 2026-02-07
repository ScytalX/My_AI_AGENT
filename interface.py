import streamlit as st
import PyPDF2
from google.cloud import firestore
from google.oauth2 import service_account
import json
import super_prof  # <--- On importe ton fichier Cerveau ici !

# --- CONFIG PAGE ---
st.set_page_config(page_title="Super Prof Multi-Agent", page_icon="🎓", layout="wide")

# --- 1. SETUP BASE DE DONNÉES ---
@st.cache_resource
def get_db():
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = json.loads(st.secrets["gcp_service_account"]["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return firestore.Client(credentials=creds, project=key_dict["project_id"])
    except Exception as e:
        st.error(f"Erreur DB: {e}")
    return None

db = get_db()

# --- 2. AUTHENTIFICATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

with st.sidebar:
    st.title("🔐 Connexion")
    if not st.session_state.authenticated:
        user = st.text_input("Pseudo").strip().lower()
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if user in st.secrets["passwords"] and st.secrets["passwords"][user] == pwd:
                st.session_state.authenticated = True
                st.session_state.username = user
                st.rerun()
            else:
                st.error("Erreur d'identification")
    else:
        st.success(f"Connecté : {st.session_state.username}")
        if st.button("Déconnexion"):
            st.session_state.authenticated = False
            st.rerun()

if not st.session_state.authenticated:
    st.info("Connecte-toi pour accéder à tes cours.")
    st.stop()

# --- 3. LOGIQUE MÉMOIRE & NUMÉROTATION ---
def save_msg(role, content):
    if db:
        db.collection("chat_history").add({
            "username": st.session_state.username,
            "role": role,
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP
        })

# Initialisation des variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "plan_du_manager" not in st.session_state:
    st.session_state.plan_du_manager = None

# --- 4. INTERFACE UTILISATEUR ---
st.title(f"🎓 Super Prof IA - Session de {st.session_state.username}")

# A. UPLOAD PDF
pdf_text = ""
uploaded_file = st.file_uploader("📂 Dépose ton cours (PDF)", type="pdf")
if uploaded_file:
    reader = PyPDF2.PdfReader(uploaded_file)
    for page in reader.pages:
        pdf_text += page.extract_text()

# B. L'IA MANAGER (Se lance au début)
if not st.session_state.plan_du_manager:
    st.info("👋 Bonjour ! Je suis l'IA Manager. Dis-moi ce que tu veux apprendre aujourd'hui.")
    objectif = st.chat_input("Ex: Je veux maîtriser ce PDF pour mon examen...")
    
    if objectif:
        with st.spinner("Le Manager construit ton plan de travail..."):
            # APPEL À TON FICHIER SUPER_PROF.PY
            le_plan = super_prof.get_manager_plan(
                st.secrets["GOOGLE_API_KEY"], 
                objectif, 
                pdf_text
            )
            st.session_state.plan_du_manager = le_plan
            st.session_state.messages.append({"role": "assistant", "content": f"📋 **PLAN DU MANAGER :**\n\n{le_plan}"})
            st.rerun()

# C. L'IA PROFESSEUR (Chat principal)
else:
    # On affiche le plan en haut (dans un menu déroulant pour pas gêner)
    with st.expander("Voir le Plan du Manager"):
        st.write(st.session_state.plan_du_manager)

    # Affichage du chat avec NUMÉROS
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            # C'est ici qu'on ajoute les numéros visuels #1, #2...
            st.markdown(f"**#{i+1}** : {msg['content']}")

    # Zone de question
    if user_input := st.chat_input("Pose ta question au Professeur..."):
        # 1. User
        current_num = len(st.session_state.messages) + 1
        with st.chat_message("user"):
            st.markdown(f"**#{current_num}** : {user_input}")
        st.session_state.messages.append({"role": "user", "content": user_input})
        save_msg("user", user_input)

        # 2. Préparation de l'historique pour l'IA (avec les numéros cachés dans le texte)
        history_gemini = []
        for i, m in enumerate(st.session_state.messages[:-1]): # On exclut le dernier msg qu'on vient d'ajouter
            role_gemini = "user" if m["role"] == "user" else "model"
            content_with_id = f"[Message #{i+1}] {m['content']}"
            history_gemini.append({"role": role_gemini, "parts": [content_with_id]})

        # 3. Réponse Professeur
        with st.spinner("Le Professeur réfléchit..."):
            # APPEL À TON FICHIER SUPER_PROF.PY
            response = super_prof.get_professor_response(
                st.secrets["GOOGLE_API_KEY"],
                history_gemini,
                f"[Message #{current_num}] {user_input}",
                st.session_state.plan_du_manager
            )

        # 4. Affichage IA
        next_num = len(st.session_state.messages) + 1
        with st.chat_message("assistant"):
            st.markdown(f"**#{next_num}** : {response}")
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_msg("assistant", response)