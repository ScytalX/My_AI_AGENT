import google.generativeai as genai

# --- 1. LE MANAGER (Architecte) ---
def get_manager_plan(api_key, user_goal, pdf_text=""):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es le Manager Pédagogique.
    TON RÔLE :
    1. Analyse l'objectif et le PDF.
    2. Découpe l'apprentissage en étapes numérotées.
    3. Reste synthétique.
    """
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    prompt = f"Objectif : {user_goal}\n\nContexte PDF : {pdf_text[:10000]}..." 
    return model.generate_content(prompt).text

# --- 2. LE PROFESSEUR (Pédagogue) ---
def get_professor_response(api_key, history, current_question, plan):
    genai.configure(api_key=api_key)
    system_prompt = f"""
    Tu es un Professeur Expert.
    Ton guide est ce plan : {plan}
    Explique clairement, étape par étape. Si l'étudiant pose une question sur un résumé de sous-dossier, intègre-le au cours.
    """
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return chat.send_message(current_question).text

# --- 3. LE SCRIBE (Pour la fusion des dossiers) ---
def get_merge_summary(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es le Scribe. Ton but est de résumer une sous-conversation pour le dossier parent.
    Rédige un paragraphe concis qui commence par : "Dans ce sous-module, nous avons vu..."
    Liste les points clés appris.
    """
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return chat.send_message("Fais le résumé de fusion maintenant.").text
