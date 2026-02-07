import google.generativeai as genai

def get_manager_plan(api_key, user_goal, pdf_text=""):
    """Le Manager : Il structure le cours."""
    genai.configure(api_key=api_key)
    
    system_prompt = """
    Tu es le Manager Pédagogique.
    TON RÔLE :
    1. Analyse l'objectif de l'étudiant et le PDF fourni.
    2. Découpe l'apprentissage en étapes claires et numérotées.
    3. Donne une liste de chapitres à aborder.
    4. Ne donne PAS le cours maintenant, fais juste le plan.
    Sois directif et concis.
    """
    
    # On utilise le modèle Flash rapide et stable
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    
    prompt = f"Objectif : {user_goal}\n\nContexte PDF : {pdf_text[:10000]}..." 
    response = model.generate_content(prompt)
    return response.text

def get_professor_response(api_key, history, current_question, plan):
    """Le Professeur : Il explique le cours."""
    genai.configure(api_key=api_key)
    
    system_prompt = f"""
    Tu es un Professeur Expert.
    Ton guide est ce plan : {plan}
    
    RÈGLES :
    1. Réponds aux questions de l'étudiant.
    2. Explique clairement, étape par étape.
    3. Si l'étudiant dit "Ok" ou "Suivant", passe au point suivant du plan.
    """
    
    model = genai.GenerativeModel("models/gemini-2.5-flash", system_instruction=system_prompt)
    
    chat = model.start_chat(history=history)
    response = chat.send_message(current_question)
    return response.text
