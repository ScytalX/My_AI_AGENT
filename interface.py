import streamlit as st
import PyPDF2
from google.cloud import firestore
from google.oauth2 import service_account
import json
import uuid
import datetime
import super_prof  # Ton fichier Cerveau

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="Super Prof - Mode Commande", page_icon="🎓", layout="wide")

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

# --- 2. GESTION SESSION & AUTH ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
if "current_session_title" not in st.session_state:
    st.session_state.current_session_title = None

# FONCTION : CHERCHER OU CRÉER UNE SESSION PAR TITRE
def get_or_create_session(title):
    # 1. On cherche si ce titre existe déjà pour cet utilisateur
    docs = db.collection("sessions")\
             .where("username", "==", st.session_state.username)\
             .where("title", "==", title)\
             .stream()
    
    found_sessions = list(docs)
    
    if found_sessions:
        # SI OUI : On récupère l'ID de la session existante
        session_data = found_sessions[0].to_dict()
        return session_data["session_id"], False # False = Ce n'est pas nouveau
    else:
        # SI NON : On crée une nouvelle session
        new_id = str(uuid.uuid4())
        db.collection("sessions").document(new_id).set({
            "session_id": new_id,
            "username": st.session_state.username,
            "title": title,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return new_id, True # True = C'est nouveau

# FONCTION : CHARGER LES MESSAGES
def load_messages(session_id):
    docs = db.collection("chat_history")\
             .where("session_id", "==", session_id)\
             .order_by("timestamp")\
             .stream()
    return [doc.to_dict() for doc in docs]

# FONCTION : SAUVEGARDER
def save_msg(session_id, role, content):
    db.collection("chat_history").add({
        "session_id": session_id,
        "username": st.session_state.username,
        "role": role,
        "content": content,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

# --- 3. LOGIN ---
if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    with st.form("login"):
        user = st.text_input("Pseudo").strip().lower()
        pwd = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer"):
            if user in st.secrets["passwords"] and st.secrets["passwords"][user] == pwd:
                st.session_state.authenticated = True
                st.session_state.username = user
                st.rerun()
            else:
                st.error("Identifiants incorrects")
    st.stop()

# --- 4. CHOIX DU DOSSIER (TITRE) ---
# Si aucune session n'est active, on demande le TITRE
if not st.session_state.current_session_title:
    st.title(f"Bonjour {st.session_state.username.capitalize()} 👋")
    st.markdown("### Sur quel dossier veux-tu travailler ?")
    
    # On affiche les dossiers existants pour info
    st.info("💡 Astuce : Tape le nom d'un dossier existant pour le reprendre, ou un nouveau nom pour le créer.")
    
    titre_input = st.text_input("Nom du dossier (ex: MATH1, PHYSIQUE, PROJET_A)", key="titre_start").strip().upper()
    
    if st.button("Lancer la session") and titre_input:
        session_id, is_new = get_or_create_session(titre_input)
        st.session_state.current_session_id = session_id
        st.session_state.current_session_title = titre_input
        st.session_state.messages = load_messages(session_id)
        st.session_state.plan_du_manager = None # On reset le plan temporaire
        st.rerun()
    
    st.stop() # On arrête l'affichage ici tant qu'on a pas choisi

# --- 5. INTERFACE DE CHAT ---

# Barre du haut
col1, col2 = st.columns([3, 1])
with col1:
    st.title(f"📂 Dossier : {st.session_state.current_session_title}")
with col2:
    if st.button("Fermer le dossier"):
        st.session_state.current_session_title = None
        st.rerun()

# Affichage des messages
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(f"**#{i+1}** : {msg['content']}")

# ZONE DE SAISIE (LA COMMANDE MAGIQUE EST ICI)
if user_input := st.chat_input(f"Parle au Prof ({st.session_state.current_session_title})..."):
    
    # --- 🛑 INTERCEPTION : COMMANDE MAGIQUE "PREVIEW" ---
    if user_input.strip().upper().startswith("PREVIEW"):
        # L'utilisateur veut changer de dossier !
        nouveau_titre = user_input[7:].strip().upper() # On récupère ce qu'il y a après "PREVIEW "
        
        if nouveau_titre:
            with st.spinner(f"🔄 Changement vers le dossier {nouveau_titre}..."):
                # On cherche ou crée la nouvelle session
                new_sess_id, _ = get_or_create_session(nouveau_titre)
                
                # On met à jour l'état
                st.session_state.current_session_id = new_sess_id
                st.session_state.current_session_title = nouveau_titre
                st.session_state.messages = load_messages(new_sess_id)
                st.session_state.plan_du_manager = None
                
            st.success(f"Tu es maintenant sur : {nouveau_titre}")
            st.rerun()
        else:
            st.warning("⚠️ Tu dois dire un nom après PREVIEW (ex: PREVIEW MATH2)")
    
    # --- SINON : C'EST UN MESSAGE NORMAL POUR L'IA ---
    else:
        # 1. User
        current_num = len(st.session_state.messages) + 1
        st.session_state.messages.append({"role": "user", "content": user_input})
        save_msg(st.session_state.current_session_id, "user", user_input)
        with st.chat_message("user"):
            st.markdown(f"**#{current_num}** : {user_input}")

        # 2. Logique IA (Manager ou Prof)
        # Si c'est le tout début et pas de plan -> Manager
        if len(st.session_state.messages) == 1 and not st.session_state.plan_du_manager:
            with st.spinner("Le Manager initialise le dossier..."):
                plan = super_prof.get_manager_plan(st.secrets["GOOGLE_API_KEY"], user_input)
                st.session_state.plan_du_manager = plan
                
                st.session_state.messages.append({"role": "assistant", "content": plan})
                save_msg(st.session_state.current_session_id, "assistant", plan)
                st.rerun()
        
        # Sinon -> Professeur
        else:
            # Historique
            history_gemini = []
            for i, m in enumerate(st.session_state.messages[:-1]):
                role_gemini = "user" if m["role"] == "user" else "model"
                history_gemini.append({"role": role_gemini, "parts": [f"[Message #{i+1}] {m['content']}"]})

            with st.spinner("Le Professeur réfléchit..."):
                response = super_prof.get_professor_response(
                    st.secrets["GOOGLE_API_KEY"],
                    history_gemini,
                    f"[Message #{current_num}] {user_input}",
                    st.session_state.plan_du_manager if st.session_state.plan_du_manager else "Contexte général"
                )
            
            # Affichage réponse
            next_num = len(st.session_state.messages) + 1
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_msg(st.session_state.current_session_id, "assistant", response)
            st.rerun()
