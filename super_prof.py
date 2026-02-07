import google.generativeai as genai

# --- 1. LE MANAGER (Architecte) ---
def get_manager_plan(api_key, user_goal, pdf_text=""):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es le Manager Pédagogique.
    TON RÔLE :
    1. Analyse l'objectif et le PDF.
    2. Découpe l'apprentissage en étapes numérotées.
    3. Reste synthétique. Ne donne pas le cours, fais le sommaire.
    """
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    prompt = f"Objectif : {user_goal}\n\nContexte PDF : {pdf_text[:10000]}..." 
    return model.generate_content(prompt).text

# --- 2. LE PROFESSEUR (Enseignant) ---
def get_professor_response(api_key, history, current_question, plan):
    genai.configure(api_key=api_key)
    system_prompt = f"""
    Tu es un Professeur Expert.
    Ton guide est ce plan : {plan}
    Explique clairement, étape par étape. Sois pédagogue et patient.
    """
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return chat.send_message(current_question).text

# --- 3. LE SCRIBE (Synthétiseur & Fusionneur) ---
def get_scribe_summary(api_key, history, mode="fiche"):
    genai.configure(api_key=api_key)
    
    if mode == "fusion":
        # Résumé pour le dossier parent
        instruction = "Tu es le Scribe. Résume ce sous-module en un paragraphe dense pour informer le dossier parent de ce qui a été acquis."
    else:
        # Fiche de révision pour l'élève
        instruction = "Tu es le Scribe. Fais une Fiche de Révision claire (Markdown), avec définitions, formules et points clés."

    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=instruction)
    chat = model.start_chat(history=history)
    return chat.send_message("Fais le travail demandé sur la conversation ci-dessus.").text

# --- 4. L'EXAMINATEUR (Testeur) ---
def get_examiner_quiz(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es l'Examinateur Piègeur.
    Pose 3 questions (QCM ou Ouvertes) sur la conversation actuelle pour vérifier si l'étudiant a VRAIMENT compris.
    Ne donne pas les réponses tout de suite. Attends sa réponse.
    """
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return chat.send_message("Teste l'étudiant maintenant.").text

# --- 5. LE COACH (Motivateur) ---
def get_coach_advice(api_key, history):
    genai.configure(api_key=api_key)
    system_prompt = """
    Tu es le Coach Mental.
    Ton élève semble bloqué ou demande de l'aide.
    1. Donne un conseil de méthodologie (ex: Pomodoro, Feynman).
    2. Donne une phrase de motivation liée au sujet actuel.
    Sois bref, énergique et tutorie l'élève.
    """
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    chat = model.start_chat(history=history)
    return chat.send_message("Donne-moi un conseil ou de la force.").text
