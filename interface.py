import PyPDF2
from google.cloud import firestore
from google.oauth2 import service_account
from google.api_core.exceptions import ResourceExhausted
import google.generativeai as genai
import json
import uuid
import super_prof
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Super Prof - Cockpit", page_icon="🚀", layout="wide")
# =========================================================
# 🧠 PARTIE CERVEAU (LES IA) - INTÉGRÉE DIRECTEMENT ICI
# =========================================================

# Fonction de sécurité (AIRBAG) pour éviter le ResourceExhausted
def ask_gemini_safe(model, prompt, is_chat=False, chat_session=None):
    """Essaie de générer. Si Google dit STOP, on attend et on réessaie."""
    try:
        if is_chat:
            return chat_session.send_message(prompt).text
        else:
            return model.generate_content(prompt).text
    except ResourceExhausted:
        time.sleep(10) # On fait une pause de 10 secondes
        try:
            # On réessaie une fois
            if is_chat:
                return chat_session.send_message(prompt).text
            else:
                return model.generate_content(prompt).text
        except:
            return "⚠️ Le système est surchargé. Attends 1 minute et réessaie."

# 1. LE MANAGER
def get_manager_plan(api_key, user_goal, pdf_text=""):
    genai.configure(api_key=api_key)
    system_prompt = "Tu es le Manager Pédagogique. Analyse la demande et fais un plan d'apprentissage numéroté et structuré. Ne donne pas le cours."
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    prompt = f"Objectif : {user_goal}\n\nContexte PDF : {pdf_text[:10000]}..." 
    return ask_gemini_safe(model, prompt)

# 2. LE PROFESSEUR
def get_professor_response(api_key, history, current_question, plan):
    genai.configure(api_key=api_key)
    system_prompt = f"Tu es un Professeur Expert. Ton plan à suivre est : {plan}. Sois pédagogue, clair, et procède étape par étape."
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, current_question, is_chat=True, chat_session=chat)

# 3. LE COACH
def get_coach_advice(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = "Tu es le Coach Mental. Analyse la conversation. Donne un conseil méthodologique (ex: Pomodoro) et une phrase de motivation choc. Sois bref."
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, "J'ai besoin de motivation.", is_chat=True, chat_session=chat)

# 4. L'EXAMINATEUR
def get_examiner_quiz(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = "Tu es l'Examinateur. Pose 3 questions (QCM ou pièges) sur ce qui vient d'être dit pour vérifier la compréhension. Ne donne pas la réponse tout de suite."
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, "Teste-moi maintenant.", is_chat=True, chat_session=chat)

# 5. LE SCRIBE
def get_scribe_summary(api_key, history, mode="fiche"):
    genai.configure(api_key=api_key)
    if mode == "fusion":
        system_prompt = "Tu es le Scribe. Fais un résumé dense de ce sous-module pour le dossier parent."
    else:
        system_prompt = "Tu es le Scribe. Crée une Fiche de Révision propre (Markdown) avec définitions et points clés."
    
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, "Fais le résumé demandé.", is_chat=True, chat_session=chat)


# =========================================================
# 🖥️ PARTIE INTERFACE (L'ÉCRAN)
# =========================================================

st.set_page_config(page_title="Super Prof - All in One", page_icon="🚀", layout="wide")

# --- 1. DATABASE ---
# --- DATABASE ---
@st.cache_resource
def get_db():
    try:
@@ -23,68 +96,53 @@ def get_db():

db = get_db()

# --- 2. STATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
# --- STATE ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- 3. FONCTIONS ---
# --- FONCTIONS UTILITAIRES ---
def get_all_sessions():
    if db and st.session_state.username:
        docs = db.collection("sessions")\
                 .where("username", "==", st.session_state.username)\
                 .order_by("created_at", direction=firestore.Query.DESCENDING)\
                 .stream()
        docs = db.collection("sessions").where("username", "==", st.session_state.username).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
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
            "session_id": new_id, "username": st.session_state.username,
            "title": titre, "parent_id": parent_id,
            "created_at": firestore.SERVER_TIMESTAMP
        })
    return new_id

def delete_session(session_id):
    if db:
        db.collection("sessions").document(session_id).delete()
        if st.session_state.current_session_id == session_id:
            st.session_state.current_session_id = None
        if st.session_state.current_session_id == session_id: st.session_state.current_session_id = None

def load_messages(session_id):
    if db:
        docs = db.collection("chat_history")\
                 .where("session_id", "==", session_id)\
                 .order_by("timestamp")\
                 .stream()
        docs = db.collection("chat_history").where("session_id", "==", session_id).order_by("timestamp").stream()
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
            "session_id": session_id, "username": st.session_state.username,
            "role": role, "content": content, "timestamp": firestore.SERVER_TIMESTAMP
        })

def get_session_info(session_id):
    if db and session_id:
        doc = db.collection("sessions").document(session_id).get()
        if doc.exists:
            return doc.to_dict()
        if doc.exists: return doc.to_dict()
    return None

# --- 4. LOGIN ---
# --- LOGIN ---
if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    with st.form("login"):
@@ -97,200 +155,155 @@ def get_session_info(session_id):
                st.rerun()
    st.stop()

# =========================================================
# 🎮 BARRE LATÉRALE : LE COCKPIT DE PILOTAGE
# =========================================================
# --- SIDEBAR ---
with st.sidebar:
    st.title(f"👤 {st.session_state.username.capitalize()}")

    # -----------------------------------------------------
    # ZONE 1 : COMMANDES DE LA SESSION ACTIVE (Le plus important)
    # -----------------------------------------------------
    # ZONE OUTILS
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
        st.subheader("🕹️ Commandes")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("😈", help="Quiz"): st.session_state.special_trigger = "quiz"
        with c2:
            if st.button("📣", help="Coach"): st.session_state.special_trigger = "coach"
        with c3:
            if st.button("📝", help="Fiche"): st.session_state.special_trigger = "fiche"
            
        # GESTION ARBRE
        curr = get_session_info(st.session_state.current_session_id)
        if curr:
            st.caption(f"Actif : {curr['title']}")
            with st.expander("↪️ Sous-Dossier"):
                sub = st.text_input("Titre", key="sub_in")
                if st.button("Créer") and sub:
                    cid = create_session(sub, parent_id=st.session_state.current_session_id)
                    st.session_state.current_session_id = cid
                    st.session_state.messages = []
                    st.session_state.plan_du_manager = None
                    st.rerun()
            if curr.get("parent_id"):
                if st.button("⬆️ FUSIONNER", type="primary"):
                    st.session_state.trigger_fusion = True
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
    # NAVIGATION ARBRE
    st.subheader("🗂️ Mes Dossiers")
    with st.expander("➕ Nouveau Projet"):
        rt = st.text_input("Titre")
        if st.button("Créer Racine") and rt:
            sid = create_session(rt)
            st.session_state.current_session_id = sid
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
    # Affichage Arbre
    sessions = get_all_sessions()
    roots = [s for s in sessions if not s.get("parent_id")]
    children = {}
    for s in sessions:
        pid = s.get("parent_id")
        if pid:
            if pid not in children: children[pid] = []
            children[pid].append(s)

            c1, c2 = st.columns([5, 1])
    def show_tree(lst, level=0):
        for s in lst:
            pre = "⠀" * (level*2) + ("📂" if level==0 else "↳")
            label = f"{pre} {s['title']}"
            if s['session_id'] == st.session_state.current_session_id: label = f"🔴 **{s['title']}**"
            
            c1, c2 = st.columns([5,1])
            with c1:
                if st.button(title_display, key=f"nav_{s['session_id']}"):
                if st.button(label, key=f"n_{s['session_id']}"):
                    st.session_state.current_session_id = s['session_id']
                    st.session_state.messages = load_messages(s['session_id'])
                    st.session_state.plan_du_manager = None
                    st.rerun()
            with c2:
                if st.button("x", key=f"del_{s['session_id']}"):
                if st.button("x", key=f"d_{s['session_id']}"):
                    delete_session(s['session_id'])
                    st.rerun()
            
            if s['session_id'] in children_map:
                display_tree(children_map[s['session_id']], level + 1)
            if s['session_id'] in children: show_tree(children[s['session_id']], level+1)

    display_tree(roots)


# =========================================================
# 🖥️ ZONE PRINCIPALE : LE CHAT
# =========================================================
    show_tree(roots)

# --- MAIN AREA ---
if not st.session_state.current_session_id:
    st.info("👈 Sélectionne un dossier à gauche ou crée un nouveau projet.")
    st.info("👈 Choisis un dossier.")
    st.stop()

# Infos session active
current_info = get_session_info(st.session_state.current_session_id)
if not current_info: st.stop() # Sécurité si supprimé
parent_id = current_info.get("parent_id")

# Titre simple
st.title(current_info['title'])
curr_info = get_session_info(st.session_state.current_session_id)
if not curr_info: st.stop()
st.title(curr_info['title'])

# --- LOGIQUE DE FUSION (Déclenchée depuis la Sidebar) ---
# LOGIQUE DE FUSION
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
    with st.spinner("Fusion en cours..."):
        hist = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages]
        # APPEL FONCTION INTERNE
        res = get_scribe_summary(st.secrets["GOOGLE_API_KEY"], hist, mode="fusion")
        save_msg(curr_info['parent_id'], "assistant", f"✅ **RÉSUMÉ {curr_info['title']}**\n{res}")
        st.session_state.current_session_id = curr_info['parent_id']
        st.session_state.messages = load_messages(curr_info['parent_id'])
        st.session_state.trigger_fusion = False
        st.rerun()

# --- LOGIQUE DES SPÉCIALISTES (Déclenchée depuis la Sidebar) ---
# LOGIQUE SPÉCIALE (COACH/QUIZ)
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
    trig = st.session_state.special_trigger
    hist = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages]
    with st.spinner(f"Appel {trig}..."):
        if trig == "quiz": 
            # APPEL DIRECT
            r = get_examiner_quiz(st.secrets["GOOGLE_API_KEY"], hist)
            p = "😈 **EXAMINATEUR**"
        elif trig == "coach": 
            # APPEL DIRECT
            r = get_coach_advice(st.secrets["GOOGLE_API_KEY"], hist)
            p = "📣 **COACH**"
        elif trig == "fiche": 
            # APPEL DIRECT
            r = get_scribe_summary(st.secrets["GOOGLE_API_KEY"], hist, mode="fiche")
            p = "📝 **SCRIBE**"

    full_resp = f"### {prefix}\n{resp_spec}"
    st.session_state.messages.append({"role": "assistant", "content": full_resp})
    save_msg(st.session_state.current_session_id, "assistant", full_resp)
    st.session_state.special_trigger = None # Reset
    full = f"### {p}\n{r}"
    st.session_state.messages.append({"role": "assistant", "content": full})
    save_msg(st.session_state.current_session_id, "assistant", full)
    st.session_state.special_trigger = None
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
# CHAT
up = st.file_uploader("PDF", type="pdf")
pdf_txt = ""
if up:
    read = PyPDF2.PdfReader(up)
    for p in read.pages: pdf_txt += p.extract_text()

# --- INPUT UTILISATEUR ---
if user_input := st.chat_input("Discute avec le Professeur..."):
    # User
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_msg(st.session_state.current_session_id, "user", user_input)
    with st.chat_message("user"): st.write(user_input)
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

    # IA Logic
    if len(st.session_state.messages) <= 1 and not st.session_state.plan_du_manager and not parent_id:
        with st.spinner("Le Manager prépare le plan..."):
            resp = super_prof.get_manager_plan(st.secrets["GOOGLE_API_KEY"], user_input, pdf_text)
if txt := st.chat_input("..."):
    st.session_state.messages.append({"role": "user", "content": txt})
    save_msg(st.session_state.current_session_id, "user", txt)
    with st.chat_message("user"): st.write(txt)
    
    # IA REPONSE
    if len(st.session_state.messages) <= 1 and not st.session_state.plan_du_manager and not curr_info.get("parent_id"):
        with st.spinner("Manager..."):
            # APPEL DIRECT
            resp = get_manager_plan(st.secrets["GOOGLE_API_KEY"], txt, pdf_txt)
            st.session_state.plan_du_manager = resp
    else:
        with st.spinner("Le Professeur réfléchit..."):
            hist = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages[:-1]]
            context = st.session_state.plan_du_manager if st.session_state.plan_du_manager else "Contexte libre."
            resp = super_prof.get_professor_response(st.secrets["GOOGLE_API_KEY"], hist, user_input, context)

    # Reponse IA
        with st.spinner("Professeur..."):
            h = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages[:-1]]
            c = st.session_state.plan_du_manager if st.session_state.plan_du_manager else "Contexte libre"
            # APPEL DIRECT
            resp = get_professor_response(st.secrets["GOOGLE_API_KEY"], h, txt, c)
            
    st.session_state.messages.append({"role": "assistant", "content": resp})
    save_msg(st.session_state.current_session_id, "assistant", resp)
    with st.chat_message("assistant"): st.write(resp)
