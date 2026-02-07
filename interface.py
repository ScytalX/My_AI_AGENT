import streamlit as st
import PyPDF2
from google.cloud import firestore
from google.oauth2 import service_account
import json
import uuid
import super_prof  # Ton fichier cerveau

# --- CONFIGURATION ---
st.set_page_config(page_title="Super Prof", page_icon="🎓", layout="wide")

# --- 1. CONNEXION BASE DE DONNÉES ---
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

# --- 2. GESTION UTILISATEUR ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# --- 3. FONCTIONS HISTORIQUE ---

def get_sessions():
    """Récupère la liste des conversations de l'utilisateur."""
    if db and st.session_state.username:
        docs = db.collection("sessions")\
                 .where("username", "==", st.session_state.username)\
                 .order_by("created_at", direction=firestore.Query.DESCENDING)\
                 .stream()
        return [doc.to_dict() for doc in docs]
    return []

def delete_session(session_id):
    """Supprime une conversation de la liste."""
    if db:
        db.collection("sessions").document(session_id).delete()
        # On force le rechargement
        if st.session_state.current_session_id == session_id:
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.session_state.plan_du_manager = None

def create_session(titre):
    """Crée une nouvelle conversation."""
    new_id = str(uuid.uuid4())
    if db:
        db.collection("sessions").document(new_id).set({
            "session_id": new_id,
            "username": st.session_state.username,
            "title": titre,
            "created_at": firestore.SERVER_TIMESTAMP
        })
    return new_id

def load_chat_history(session_id):
    """Charge les messages d'une session."""
    if db:
        docs = db.collection("chat_history")\
                 .where("session_id", "==", session_id)\
                 .order_by("timestamp")\
                 .stream()
        return [doc.to_dict() for doc in docs]
    return []

def save_msg(session_id, role, content):
    """Sauvegarde un message."""
    if db:
        db.collection("chat_history").add({
            "session_id": session_id,
            "username": st.session_state.username,
            "role": role,
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP
        })

# --- 4. LOGIN (ÉCRAN DE CONNEXION) ---
if not st.session_state.authenticated:
    st.title("🔐 Connexion Super Prof")
    with st.sidebar:
        user = st.text_input("Pseudo").strip().lower()
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if user in st.secrets["passwords"] and st.secrets["passwords"][user] == pwd:
                st.session_state.authenticated = True
                st.session_state.username = user
                st.rerun()
            else:
                st.error("Erreur d'identification")
    st.info("Entre ton pseudo et mot de passe à gauche.")
    st.stop()

# --- 5. BARRE LATÉRALE (HISTORIQUE) ---
with st.sidebar:
    st.title(f"👤 {st.session_state.username.capitalize()}")
    if st.button("Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()
    
    st.divider()
    st.subheader("🗂️ Tes Dossiers")
    
    # Bouton Nouvelle Session
    with st.form("new_sess"):
        new_title = st.text_input("Nouveau sujet (ex: Math)", placeholder="Titre...")
        if st.form_submit_button("➕ Créer") and new_title:
            sess_id = create_session(new_title)
            st.session_state.current_session_id = sess_id
            st.session_state.messages = []
            st.session_state.plan_du_manager = None
            st.rerun()
            
    st.divider()
    
    # Liste des sessions existantes avec bouton Supprimer
    sessions = get_sessions()
    for s in sessions:
        col_btn, col_del = st.columns([4, 1])
        with col_btn:
            # Si on clique sur le nom, on charge la session
            if st.button(f"📂 {s['title']}", key=f"btn_{s['session_id']}"):
                st.session_state.current_session_id = s['session_id']
                st.session_state.messages = load_chat_history(s['session_id'])
                # On reset le plan pour qu'il le recharge si besoin (ou on pourrait le sauvegarder en base aussi)
                st.session_state.plan_du_manager = None 
                st.rerun()
        with col_del:
            # Bouton poubelle
            if st.button("🗑️", key=f"del_{s['session_id']}"):
                delete_session(s['session_id'])
                st.rerun()

# --- 6. ZONE PRINCIPALE (CHAT) ---

# A. Si aucun dossier n'est sélectionné
if not st.session_state.current_session_id:
    st.title("👈 Choisis un dossier à gauche ou crée-en un !")
    st.stop()

# B. Si un dossier est actif
st.title(f"🎓 Cours")

# Upload PDF
uploaded_file = st.file_uploader("📎 Ajouter un PDF au contexte", type="pdf")
pdf_text = ""
if uploaded_file:
    reader = PyPDF2.PdfReader(uploaded_file)
    for page in reader.pages:
        pdf_text += page.extract_text()

# Affichage des messages
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(f"**#{i+1}** : {msg['content']}")

# Zone de texte
if user_input := st.chat_input("Pose ta question..."):
    
    # 1. Message Utilisateur
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_msg(st.session_state.current_session_id, "user", user_input)
    with st.chat_message("user"):
        st.write(user_input)
    
    # 2. IA Réfléchit
    # Cas 1 : Début de conversation (Pas de plan) -> MANAGER
    if len(st.session_state.messages) <= 1 and not st.session_state.plan_du_manager:
        with st.spinner("Le Manager prépare le plan..."):
            response = super_prof.get_manager_plan(
                st.secrets["GOOGLE_API_KEY"], 
                user_input, 
                pdf_text
            )
            st.session_state.plan_du_manager = response
            
    # Cas 2 : Conversation en cours -> PROFESSEUR
    else:
        with st.spinner("Le Professeur écrit..."):
            # Historique pour Gemini
            history_gemini = []
            for m in st.session_state.messages[:-1]:
                role_g = "user" if m["role"] == "user" else "model"
                history_gemini.append({"role": role_g, "parts": [m["content"]]})
                
            response = super_prof.get_professor_response(
                st.secrets["GOOGLE_API_KEY"],
                history_gemini,
                user_input,
                st.session_state.plan_du_manager if st.session_state.plan_du_manager else "Suis la conversation."
            )

    # 3. Réponse IA
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_msg(st.session_state.current_session_id, "assistant", response)
    with st.chat_message("assistant"):
        st.write(response)
