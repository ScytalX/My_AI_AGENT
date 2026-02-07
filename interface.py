import streamlit as st
import PyPDF2
from google.cloud import firestore
from google.oauth2 import service_account
import json
import uuid
import super_prof

# --- CONFIGURATION ---
st.set_page_config(page_title="Super Prof - Tree Mode", page_icon="🌳", layout="wide")

# --- 1. DATABASE ---
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

# --- 2. STATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "current_session_title" not in st.session_state: # Pour l'affichage
    st.session_state.current_session_title = ""

# --- 3. FONCTIONS CORE ---

def get_all_sessions():
    """Récupère tout pour construire l'arbre."""
    if db and st.session_state.username:
        docs = db.collection("sessions")\
                 .where("username", "==", st.session_state.username)\
                 .order_by("created_at", direction=firestore.Query.DESCENDING)\
                 .stream()
        return [doc.to_dict() for doc in docs]
    return []

def create_session(titre, parent_id=None):
    """Crée une session (Raciné ou Enfant)."""
    new_id = str(uuid.uuid4())
    if db:
        db.collection("sessions").document(new_id).set({
            "session_id": new_id,
            "username": st.session_state.username,
            "title": titre,
            "parent_id": parent_id, # Lien de parenté
            "created_at": firestore.SERVER_TIMESTAMP
        })
    return new_id

def delete_session(session_id):
    if db:
        db.collection("sessions").document(session_id).delete()
        if st.session_state.current_session_id == session_id:
            st.session_state.current_session_id = None

def load_messages(session_id):
    if db:
        docs = db.collection("chat_history")\
                 .where("session_id", "==", session_id)\
                 .order_by("timestamp")\
                 .stream()
        return [doc.to_dict() for doc in docs]
    return []

def save_msg(session_id, role, content):
    if db:
        db.collection("chat_history").add({
            "session_id": session_id,
            "username": st.session_state.username,
            "role": role,
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP
        })

def get_session_info(session_id):
    """Récupère les infos d'une session (pour trouver le parent)."""
    if db:
        doc = db.collection("sessions").document(session_id).get()
        if doc.exists:
            return doc.to_dict()
    return None

# --- 4. LOGIN ---
if not st.session_state.authenticated:
    st.title("🔐 Connexion Arbre de Savoir")
    with st.sidebar:
        user = st.text_input("Pseudo").strip().lower()
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Entrer"):
            if user in st.secrets["passwords"] and st.secrets["passwords"][user] == pwd:
                st.session_state.authenticated = True
                st.session_state.username = user
                st.rerun()
    st.stop()

# --- 5. SIDEBAR (L'ARBRE) ---
with st.sidebar:
    st.title(f"🌳 {st.session_state.username.capitalize()}")
    
    # Création Racine
    with st.form("new_root"):
        root_title = st.text_input("Nouveau Sujet Principal")
        if st.form_submit_button("➕ Créer Racine") and root_title:
            sess_id = create_session(root_title, parent_id=None)
            st.session_state.current_session_id = sess_id
            st.session_state.current_session_title = root_title
            st.session_state.messages = []
            st.session_state.plan_du_manager = None
            st.rerun()
    
    st.divider()
    
    # LOGIQUE D'AFFICHAGE DE L'ARBRE
    all_sessions = get_all_sessions()
    
    # On sépare les parents (Racines) et les enfants
    roots = [s for s in all_sessions if not s.get("parent_id")]
    children_map = {} # Dictionnaire {parent_id: [liste des enfants]}
    for s in all_sessions:
        if s.get("parent_id"):
            pid = s["parent_id"]
            if pid not in children_map: children_map[pid] = []
            children_map[pid].append(s)
            
    # Fonction récursive pour afficher l'arbre
    def display_tree(session_list, level=0):
        for s in session_list:
            indent = "&nbsp;" * (level * 4) # Décalage visuel
            icon = "📂" if level == 0 else "↳ 📑"
            
            # Layout des boutons (Nom | Poubelle)
            col_name, col_del = st.columns([5, 1])
            
            with col_name:
                # Bouton de sélection
                if st.button(f"{indent}{icon} {s['title']}", key=f"sel_{s['session_id']}"):
                    st.session_state.current_session_id = s['session_id']
                    st.session_state.current_session_title = s['title']
                    st.session_state.messages = load_messages(s['session_id'])
                    st.session_state.plan_du_manager = None
                    st.rerun()
            
            with col_del:
                if st.button("x", key=f"del_{s['session_id']}", help="Supprimer"):
                    delete_session(s['session_id'])
                    st.rerun()
            
            # Si cette session a des enfants, on les affiche en dessous
            if s['session_id'] in children_map:
                display_tree(children_map[s['session_id']], level + 1)

    st.subheader("Mes Savoirs")
    display_tree(roots)

# --- 6. ZONE PRINCIPALE ---
if not st.session_state.current_session_id:
    st.info("👈 Choisis ou crée un sujet.")
    st.stop()

# Info Session Courante
current_info = get_session_info(st.session_state.current_session_id)
parent_id = current_info.get("parent_id") if current_info else None

# HEADER
col_title, col_actions = st.columns([3, 2])
with col_title:
    st.title(f"{current_info['title'] if current_info else '...'}")

with col_actions:
    # Action 1: Créer un Sous-Dossier
    with st.expander("↪️ Approfondir (Créer sous-dossier)"):
        sub_title = st.text_input("Nom du sous-chapitre")
        if st.button("Créer") and sub_title:
            # Le titre sera "Parent / Enfant" pour être clair
            full_title = f"{sub_title}" 
            child_id = create_session(full_title, parent_id=st.session_state.current_session_id)
            # On switch direct dessus
            st.session_state.current_session_id = child_id
            st.session_state.current_session_title = full_title
            st.session_state.messages = []
            st.session_state.plan_du_manager = None
            st.rerun()
            
    # Action 2: Remonter au Parent (Fusion)
    if parent_id:
        if st.button("⬆️ Remonter & Fusionner au Parent", type="primary"):
            with st.spinner("Le Scribe résume ce dossier..."):
                # 1. Générer le résumé
                history_gemini = []
                for m in st.session_state.messages:
                    role_g = "user" if m["role"] == "user" else "model"
                    history_gemini.append({"role": role_g, "parts": [m["content"]]})
                
                resume = super_prof.get_merge_summary(st.secrets["GOOGLE_API_KEY"], history_gemini)
                
                # 2. Poster le résumé dans le Parent
                msg_fusion = f"📌 **RÉSUMÉ MODULE {current_info['title']}** :\n{resume}"
                save_msg(parent_id, "assistant", msg_fusion)
                
                # 3. Switcher vers le Parent
                st.session_state.current_session_id = parent_id
                st.session_state.messages = load_messages(parent_id)
                st.success("Fusion réussie !")
                st.rerun()

# --- CHAT UI ---

# Upload PDF
uploaded_file = st.file_uploader("📎 Ajouter un PDF", type="pdf")
pdf_text = ""
if uploaded_file:
    reader = PyPDF2.PdfReader(uploaded_file)
    for page in reader.pages:
        pdf_text += page.extract_text()

# Messages
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(f"**#{i+1}** : {msg['content']}")

# Input
if user_input := st.chat_input("..."):
    # User Msg
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_msg(st.session_state.current_session_id, "user", user_input)
    with st.chat_message("user"): st.write(user_input)

    # IA Response
    if len(st.session_state.messages) <= 1 and not st.session_state.plan_du_manager and not parent_id:
        # Seulement le Manager si c'est une RACINE pure et début
        with st.spinner("Manager..."):
            resp = super_prof.get_manager_plan(st.secrets["GOOGLE_API_KEY"], user_input, pdf_text)
            st.session_state.plan_du_manager = resp
    else:
        # Professeur (Pour les sous-dossiers ou suite conversation)
        with st.spinner("Professeur..."):
            hist = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages[:-1]]
            resp = super_prof.get_professor_response(
                st.secrets["GOOGLE_API_KEY"], 
                hist, 
                user_input, 
                st.session_state.plan_du_manager if st.session_state.plan_du_manager else "Contexte Parent/Enfant"
            )
            
    st.session_state.messages.append({"role": "assistant", "content": resp})
    save_msg(st.session_state.current_session_id, "assistant", resp)
    with st.chat_message("assistant"): st.write(resp)
