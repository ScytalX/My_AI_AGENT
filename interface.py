import streamlit as st
import PyPDF2
from google.cloud import firestore
from google.oauth2 import service_account
import json
import uuid
import super_prof

# --- CONFIGURATION ---
st.set_page_config(page_title="Super Prof - Cockpit", page_icon="🚀", layout="wide")

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

# --- 3. FONCTIONS ---
def get_all_sessions():
    if db and st.session_state.username:
        docs = db.collection("sessions")\
                 .where("username", "==", st.session_state.username)\
                 .order_by("created_at", direction=firestore.Query.DESCENDING)\
                 .stream()
        return [doc.to_dict() for doc in docs]
    return []

def create_session(titre, parent_id=None):
    new_id = str(uuid.uuid4())
    if db:
        db.collection("sessions").document(new_id).set({
            "session_id": new_id,
            "username": st.session_state.username,
            "title": titre,
            "parent_id": parent_id,
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
    if db and session_id:
        doc = db.collection("sessions").document(session_id).get()
        if doc.exists:
            return doc.to_dict()
    return None

# --- 4. LOGIN ---
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
    st.stop()

# =========================================================
# 🎮 BARRE LATÉRALE : LE COCKPIT DE PILOTAGE
# =========================================================
with st.sidebar:
    st.title(f"👤 {st.session_state.username.capitalize()}")
    
    # -----------------------------------------------------
    # ZONE 1 : COMMANDES DE LA SESSION ACTIVE (Le plus important)
    # -----------------------------------------------------
    if st.session_state.current_session_id:
        # Récup info session active
        curr_info = get_session_info(st.session_state.current_session_id)
        parent_id = curr_info.get("parent_id")
        
        st.markdown("### 🕹️ Commandes")
        
        # A. LES SPÉCIALISTES (Boutons d'accès rapide)
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("😈", help="Quiz Express"):
                st.session_state.special_trigger = "quiz"
        with col2:
            if st.button("📣", help="Conseil Coach"):
                st.session_state.special_trigger = "coach"
        with col3:
            if st.button("📝", help="Fiche Révision"):
                st.session_state.special_trigger = "fiche"
        
        st.divider()

        # B. GESTION ARBRE (Créer sous-dossier / Fusionner)
        st.markdown(f"**Dossier Actif :** `{curr_info['title']}`")
        
        # 1. Créer un sous-dossier (Directement ici)
        with st.expander("↪️ Créer Sous-Chapitre", expanded=False):
            sub_name = st.text_input("Titre du sous-dossier", key="input_sub")
            if st.button("Créer & Basculer"):
                if sub_name:
                    child_id = create_session(sub_name, parent_id=st.session_state.current_session_id)
                    st.session_state.current_session_id = child_id
                    st.session_state.messages = []
                    st.session_state.plan_du_manager = None
                    st.rerun()

        # 2. Fusionner vers le parent (Si on est dans un sous-dossier)
        if parent_id:
            st.warning("⚠️ Terminer ce chapitre ?")
            if st.button("⬆️ FUSIONNER VERS PARENT", type="primary"):
                # Logique de fusion (Déclenchée via un flag pour l'exécuter dans le main script)
                st.session_state.trigger_fusion = True
                st.rerun()
    
    st.divider()

    # -----------------------------------------------------
    # ZONE 2 : NAVIGATION (L'ARBRE)
    # -----------------------------------------------------
    st.subheader("🗂️ Navigateur")
    
    # Bouton Nouvelle Racine (Gros projet)
    with st.expander("➕ Nouveau Projet (Racine)"):
        root_title = st.text_input("Titre Projet")
        if st.button("Créer Projet") and root_title:
            sess_id = create_session(root_title, parent_id=None)
            st.session_state.current_session_id = sess_id
            st.session_state.messages = []
            st.session_state.plan_du_manager = None
            st.rerun()

    # Affichage de l'arbre
    all_sessions = get_all_sessions()
    roots = []
    children_map = {}
    for s in all_sessions:
        if not s.get("parent_id"): roots.append(s)
        else:
            pid = s["parent_id"]
            if pid not in children_map: children_map[pid] = []
            children_map[pid].append(s)
            
    def display_tree(session_list, level=0):
        for s in session_list:
            indent = "⠀" * (level*2) 
            icon = "📂" if level == 0 else "↳"
            title_display = f"{indent}{icon} {s['title']}"
            
            # Highlight visuel
            if s['session_id'] == st.session_state.current_session_id:
                title_display = f"🔴 **{s['title']}**"

            c1, c2 = st.columns([5, 1])
            with c1:
                if st.button(title_display, key=f"nav_{s['session_id']}"):
                    st.session_state.current_session_id = s['session_id']
                    st.session_state.messages = load_messages(s['session_id'])
                    st.session_state.plan_du_manager = None
                    st.rerun()
            with c2:
                if st.button("x", key=f"del_{s['session_id']}"):
                    delete_session(s['session_id'])
                    st.rerun()
            
            if s['session_id'] in children_map:
                display_tree(children_map[s['session_id']], level + 1)

    display_tree(roots)


# =========================================================
# 🖥️ ZONE PRINCIPALE : LE CHAT
# =========================================================

if not st.session_state.current_session_id:
    st.info("👈 Sélectionne un dossier à gauche ou crée un nouveau projet.")
    st.stop()

# Infos session active
current_info = get_session_info(st.session_state.current_session_id)
if not current_info: st.stop() # Sécurité si supprimé
parent_id = current_info.get("parent_id")

# Titre simple
st.title(current_info['title'])

# --- LOGIQUE DE FUSION (Déclenchée depuis la Sidebar) ---
if st.session_state.get("trigger_fusion"):
    with st.spinner("🚀 Le Scribe compile et fusionne vers le parent..."):
        # 1. On récupère l'historique
        hist_gemini = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages]
        # 2. On appelle le Scribe
        resume = super_prof.get_scribe_summary(st.secrets["GOOGLE_API_KEY"], hist_gemini, mode="fusion")
        # 3. On poste dans le Parent
        msg_fusion = f"✅ **MODULE TERMINÉ : {current_info['title']}**\n\n📌 *Résumé des acquis :*\n{resume}"
        save_msg(parent_id, "assistant", msg_fusion)
        # 4. On switch
        st.session_state.current_session_id = parent_id
        st.session_state.messages = load_messages(parent_id)
        st.session_state.trigger_fusion = False # Reset flag
        st.rerun()

# --- LOGIQUE DES SPÉCIALISTES (Déclenchée depuis la Sidebar) ---
if st.session_state.get("special_trigger"):
    trigger = st.session_state.special_trigger
    hist_gemini = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages]
    
    resp_spec = ""
    prefix = ""
    with st.spinner(f"Appel de l'agent {trigger}..."):
        if trigger == "quiz":
            resp_spec = super_prof.get_examiner_quiz(st.secrets["GOOGLE_API_KEY"], hist_gemini)
            prefix = "😈 **EXAMINATEUR**"
        elif trigger == "fiche":
            resp_spec = super_prof.get_scribe_summary(st.secrets["GOOGLE_API_KEY"], hist_gemini, mode="fiche")
            prefix = "📝 **SCRIBE**"
        elif trigger == "coach":
            resp_spec = super_prof.get_coach_advice(st.secrets["GOOGLE_API_KEY"], hist_gemini)
            prefix = "📣 **COACH**"
            
    full_resp = f"### {prefix}\n{resp_spec}"
    st.session_state.messages.append({"role": "assistant", "content": full_resp})
    save_msg(st.session_state.current_session_id, "assistant", full_resp)
    st.session_state.special_trigger = None # Reset
    st.rerun()

# --- AFFICHAGE CHAT ---
uploaded_file = st.file_uploader("📎 Ajouter un PDF (Contexte)", type="pdf")
pdf_text = ""
if uploaded_file:
    reader = PyPDF2.PdfReader(uploaded_file)
    for page in reader.pages: pdf_text += page.extract_text()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- INPUT UTILISATEUR ---
if user_input := st.chat_input("Discute avec le Professeur..."):
    # User
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_msg(st.session_state.current_session_id, "user", user_input)
    with st.chat_message("user"): st.write(user_input)

    # IA Logic
    if len(st.session_state.messages) <= 1 and not st.session_state.plan_du_manager and not parent_id:
        with st.spinner("Le Manager prépare le plan..."):
            resp = super_prof.get_manager_plan(st.secrets["GOOGLE_API_KEY"], user_input, pdf_text)
            st.session_state.plan_du_manager = resp
    else:
        with st.spinner("Le Professeur réfléchit..."):
            hist = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages[:-1]]
            context = st.session_state.plan_du_manager if st.session_state.plan_du_manager else "Contexte libre."
            resp = super_prof.get_professor_response(st.secrets["GOOGLE_API_KEY"], hist, user_input, context)

    # Reponse IA
    st.session_state.messages.append({"role": "assistant", "content": resp})
    save_msg(st.session_state.current_session_id, "assistant", resp)
    with st.chat_message("assistant"): st.write(resp)
