import google.generativeai as genai
import time
from google.api_core.exceptions import ResourceExhausted

# --- FONCTION DE SÉCURITÉ (L'AIRBAG) ---
def generate_safe(model, prompt, is_chat=False, chat_session=None):
    """Essaie de générer une réponse. Si ça bloque, attend et réessaie."""
    try:
        if is_chat:
            return chat_session.send_message(prompt).text
        else:
            return model.generate_content(prompt).text
    except ResourceExhausted:
        # C'est ici que l'Airbag se déclenche !
        time.sleep(15) # On fait une pause de 15 secondes
        # On réessaie une dernière fois
        if is_chat:
            return chat_session.send_message(prompt).text
        else:
            return model.generate_content(prompt).text

# --- 1. LE MANAGER ---
def get_manager_plan(api_key, user_goal, pdf_text=""):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es le Manager Pédagogique.
    TON RÔLE :
    1. Analyse l'objectif et le PDF.
    2. Découpe l'apprentissage en étapes numérotées.
    3. Reste synthétique. Ne donne pas le cours, fais le sommaire.
    """
    # Remets ici le modèle que tu veux (ex: gemini-2.5-flash ou 1.5-flash)
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    prompt = f"Objectif : {user_goal}\n\nContexte PDF : {pdf_text[:10000]}..." 
    
    # Appel sécurisé
    return generate_safe(model, prompt)

# --- 2. LE PROFESSEUR ---
def get_professor_response(api_key, history, current_question, plan):
    genai.configure(api_key=api_key)
    system_prompt = f"""
    Tu es un Professeur Expert.
    Ton guide est ce plan : {plan}
    Explique clairement, étape par étape. Sois pédagogue et patient.
    """
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    
    # Appel sécurisé
    return generate_safe(model, current_question, is_chat=True, chat_session=chat)

# --- 3. LE SCRIBE ---
def get_scribe_summary(api_key, history, mode="fiche"):
    genai.configure(api_key=api_key)
    
    if mode == "fusion":
        instruction = "Tu es le Scribe. Résume ce sous-module pour le dossier parent."
    else:
        instruction = "Tu es le Scribe. Fais une Fiche de Révision claire (Markdown)."

    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=instruction)
    chat = model.start_chat(history=history)
    
    return generate_safe(model, "Fais le travail demandé.", is_chat=True, chat_session=chat)

# --- 4. L'EXAMINATEUR ---
def get_examiner_quiz(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es l'Examinateur.
    Pose 3 questions pièges sur la conversation actuelle.
    """
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    
    return generate_safe(model, "Teste l'étudiant maintenant.", is_chat=True, chat_session=chat)

# --- 5. LE COACH ---
def get_coach_advice(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es le Coach Mental.
    Donne un conseil de méthodologie et une phrase de motivation.
    """
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    
    return generate_safe(model, "Donne-moi un conseil.", is_chat=True, chat_session=chat)
