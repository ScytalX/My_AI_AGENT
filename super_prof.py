import google.generativeai as genai

# --- C'EST ICI QU'ON DÉFINIT LES RÔLES ---

def get_manager_plan(api_key, user_goal, pdf_text=""):
    """Le Manager analyse la demande et crée un plan d'action."""
    genai.configure(api_key=api_key)
    
    # Consignes strictes pour le Manager
    system_prompt = """
    Tu es le Manager Pédagogique (Architecte de Cours).
    Ton rôle : Ne PAS donner le cours, mais STRUCTURER l'apprentissage.
    1. Analyse l'objectif de l'étudiant et le PDF fourni.
    2. Découpe l'apprentissage en étapes claires et numérotées.
    3. Donne une liste de chapitres à aborder un par un.
    Sois concis et directif.
    """
    
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=system_prompt)
    
    prompt = f"Objectif de l'étudiant : {user_goal}\n\nContenu du PDF (si dispo) : {pdf_text[:5000]}..." # On coupe si trop long
    response = model.generate_content(prompt)
    return response.text

def get_professor_response(api_key, history_with_numbers, current_question, plan_context):
    """Le Professeur explique le cours en suivant le plan du Manager."""
    genai.configure(api_key=api_key)
    
    # Consignes pour le Professeur
    system_prompt = f"""
    Tu es un Professeur Expert.
    Ton guide est ce plan établi par le Manager : {plan_context}
    
    RÈGLES :
    1. Réponds aux questions de l'étudiant.
    2. Si l'étudiant fait référence à un numéro de message (ex: "point #3"), retrouve le contexte.
    3. Ne balance pas tout le cours d'un coup, avance étape par étape.
    """
    
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=system_prompt)
    
    # On envoie l'historique formaté
    chat = model.start_chat(history=history_with_numbers)
    response = chat.send_message(current_question)
    return response.text