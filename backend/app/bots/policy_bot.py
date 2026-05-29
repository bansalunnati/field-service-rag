from app.retrieval.rag_pipeline import ask_question

def policy_bot(question):
    """
    Policy Assistant Bot
    """
    return ask_question(question)