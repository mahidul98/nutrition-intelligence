import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
if not key:
    raise SystemExit("GEMINI_API_KEY missing in .env")

client = genai.Client(api_key=key)

print("Models your key can use for generateContent:")
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    if "generateContent" in actions and "gemini" in m.name:
        print("  ", m.name)

print("\nTest call with", model)
r = client.models.generate_content(model=model, contents="Reply with the single word: ok")
print(r.text)