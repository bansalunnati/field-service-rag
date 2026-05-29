from app.bots.policy_bot import policy_bot

question = "What PPE requirements are mentioned?"

response = policy_bot(question)

print("\nQuestion:\n")
print(question)

print("\nResponse:\n")
print(response)