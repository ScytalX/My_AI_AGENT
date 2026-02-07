import streamlit as st
import PyPDF2
from google.cloud import firestore
from google.oauth2 import service_account
from google.api_core.exceptions import ResourceExhausted, NotFound
import google.generativeai as genai
import json
import uuid
import time

# =========================================================
# 🧠 PARTIE CERVEAU (LES IA)
# =========================================================

# 🛑 JE N'AI PAS TOUCHÉ À CETTE VERSION COMME DEMANDÉ
MODEL_NAME = "models/gemini-2.5-flash"

def ask_gemini_safe(model, prompt, is_chat=False, chat_session=None):
    """Airbag anti-crash : attend si Google est surchargé"""
    try:
        if is_chat:
            return chat_session.send_message(prompt).text
        else:
            return model.generate_content(prompt).text
    except ResourceExhausted:
        time.sleep(10) # Pause de 10s
        try:
            if is_chat:
                return chat_session.send_message(prompt).text
            else:
                return model.generate_content(prompt).text
        except:
            return "⚠️ Surcharge système. Réessaie dans 1 minute."
    except NotFound:
        return f"⚠️ Erreur : Le modèle '{MODEL_NAME}' semble introuvable sur ce serveur. Vérifie s'il est disponible pour ta clé API."

# 1. LE MANAGER
def get_manager_plan(api_key, user_goal, pdf_text=""):
    genai.configure(api_key=api_key)
    system_prompt = "Tu es le Manager Pédagogique. Fais un plan numéroté et structuré."
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=system_prompt)
    prompt = f"Objectif : {user_goal}\n\nContexte PDF : {pdf_text[:10000]}..." 
    return ask_gemini_safe(model, prompt)

# 2. LE PROFESSEUR
def get_professor_response(api_key, history, current_question, plan):
    genai.configure(api_key=api_key)
    system_prompt = f"Tu es un Professeur Expert. Suis ce plan : {plan}. Sois pédagogue."
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, current_question, is_chat=True, chat_session=chat)

# 3. LE COACH
def get_coach_advice(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = "Tu es le Coach Mental. Donne un conseil court et motivant."
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, "Motive-moi.", is_chat=True, chat_session=chat)

# 4. L'EXAMINATEUR
def get_examiner_quiz(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = "Tu es l'Examinateur. Pose 3 questions pièges pour vérifier les acquis."
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, "Teste-moi.", is_chat=True, chat_session=chat)

# 5. LE SCRIBE
def get_scribe_summary(api_key, history, mode="fiche"):
    genai.configure(api_key=api_key)
    inst = "Tu es le Scribe. Fais une fiche de révision claire (Markdown)." if mode != "fusion" else "Résume ce module pour le dossier parent."
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=inst)
    chat = model.start_chat(history=history)
    return ask_gemini_safe(model, "Fais le résumé.", is_chat=True, chat_session=chat)


# =========================================================
# 🖥️ PARTIE INTERFACE (L'ÉCRAN)
# =========================================================

st.set_page_config(page_title="Super Prof", page_icon="🎓", layout="wide")

# --- DATABASE ---
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

# --- STATE ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- FONCTIONS UTILITAIRES ---
def get_all_sessions():
    if db and st.session_state.username:
        docs = db.collection("sessions").where("username", "==", st.session_state.username).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    return []

def create_session(titre, parent_id=None):
    new_id = str(uuid.uuid4())
    if db:
        db.collection("sessions").document(new_id).set({
            "session_id": new_id, "username": st.session_state.username,
            "title": titre, "parent_id": parent_id,
            "created_at": firestore.SERVER_TIMESTAMP
        })
    return new_id

def delete_session(session_id):
    if db:
        db.collection("sessions").document(session_id).delete()
        if st.session_state.current_session_id == session_id: st.session_state.current_session_id = None

def load_messages(session_id):
    if db:
        docs = db.collection("chat_history").where("session_id", "==", session_id).order_by("timestamp").stream()
        return [doc.to_dict() for doc in docs]
    return []

def save_msg(session_id, role, content):
    if db:
        db.collection("chat_history").add({
            "session_id": session_id, "username": st.session_state.username,
            "role": role, "content": content, "timestamp": firestore.SERVER_TIMESTAMP
        })

def get_session_info(session_id):
    if db and session_id:
        doc = db.collection("sessions").document(session_id).get()
        if doc.exists: return doc.to_dict()
    return None

# --- LOGIN ---
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

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"👤 {st.session_state.username.capitalize()}")
    
    # ZONE OUTILS
    if st.session_state.current_session_id:
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

    st.divider()
    
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
            
    # Affichage Arbre
    sessions = get_all_sessions()
    roots = [s for s in sessions if not s.get("parent_id")]
    children = {}
    for s in sessions:
        pid = s.get("parent_id")
        if pid:
            if pid not in children: children[pid] = []
            children[pid].append(s)

    def show_tree(lst, level=0):
        for s in lst:
            pre = "⠀" * (level*2) + ("📂" if level==0 else "↳")
            label = f"{pre} {s['title']}"
            if s['session_id'] == st.session_state.current_session_id: label = f"🔴 **{s['title']}**"
            
            c1, c2 = st.columns([5,1])
            with c1:
                if st.button(label, key=f"n_{s['session_id']}"):
                    st.session_state.current_session_id = s['session_id']
                    st.session_state.messages = load_messages(s['session_id'])
                    st.session_state.plan_du_manager = None
                    st.rerun()
            with c2:
                if st.button("x", key=f"d_{s['session_id']}"):
                    delete_session(s['session_id'])
                    st.rerun()
            if s['session_id'] in children: show_tree(children[s['session_id']], level+1)

    show_tree(roots)

# --- MAIN AREA ---
if not st.session_state.current_session_id:
    st.info("👈 Choisis un dossier.")
    st.stop()

curr_info = get_session_info(st.session_state.current_session_id)
if not curr_info: st.stop()
st.title(curr_info['title'])

# LOGIQUE DE FUSION
if st.session_state.get("trigger_fusion"):
    with st.spinner("Fusion en cours..."):
        hist = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages]
        res = get_scribe_summary(st.secrets["GOOGLE_API_KEY"], hist, mode="fusion")
        save_msg(curr_info['parent_id'], "assistant", f"✅ **RÉSUMÉ {curr_info['title']}**\n{res}")
        st.session_state.current_session_id = curr_info['parent_id']
        st.session_state.messages = load_messages(curr_info['parent_id'])
        st.session_state.trigger_fusion = False
        st.rerun()

# LOGIQUE SPÉCIALE (COACH/QUIZ)
if st.session_state.get("special_trigger"):
    trig = st.session_state.special_trigger
    hist = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages]
    with st.spinner(f"Appel {trig}..."):
        if trig == "quiz": 
            r = get_examiner_quiz(st.secrets["GOOGLE_API_KEY"], hist)
            p = "😈 **EXAMINATEUR**"
        elif trig == "coach": 
            r = get_coach_advice(st.secrets["GOOGLE_API_KEY"], hist)
            p = "📣 **COACH**"
        elif trig == "fiche": 
            r = get_scribe_summary(st.secrets["GOOGLE_API_KEY"], hist, mode="fiche")
            p = "📝 **SCRIBE**"
            
    full = f"### {p}\n{r}"
    st.session_state.messages.append({"role": "assistant", "content": full})
    save_msg(st.session_state.current_session_id, "assistant", full)
    st.session_state.special_trigger = None
    st.rerun()

# CHAT
up = st.file_uploader("PDF", type="pdf")
pdf_txt = ""
if up:
    read = PyPDF2.PdfReader(up)
    for p in read.pages: pdf_txt += p.extract_text()

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if txt := st.chat_input("..."):
    st.session_state.messages.append({"role": "user", "content": txt})
    save_msg(st.session_state.current_session_id, "user", txt)
    with st.chat_message("user"): st.write(txt)
    
    # IA REPONSE
    if len(st.session_state.messages) <= 1 and not st.session_state.plan_du_manager and not curr_info.get("parent_id"):
        with st.spinner("Manager..."):
            resp = get_manager_plan(st.secrets["GOOGLE_API_KEY"], txt, pdf_txt)
            st.session_state.plan_du_manager = resp
    else:
        with st.spinner("Professeur..."):
            h = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [m["content"]]} for m in st.session_state.messages[:-1]]
            c = st.session_state.plan_du_manager if st.session_state.plan_du_manager else "Contexte libre"
            resp = get_professor_response(st.secrets["GOOGLE_API_KEY"], h, txt, c)
            
    st.session_state.messages.append({"role": "assistant", "content": resp})
    save_msg(st.session_state.current_session_id, "assistant", resp)
    with st.chat_message("assistant"): st.write(resp)
