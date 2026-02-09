
import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

print(f"Checking models with API key: {api_key[:5]}...")

try:
    # Use client.models.list() for google-genai SDK
    print("Listing models...")
    for m in client.models.list():
        print(f"Model: {m.name}")
        print(f"  DisplayName: {m.display_name}")
        # supported_generation_methods might be missing or different
        try:
            print(f"  SupportedActions: {m.supported_generation_methods}")
        except:
            pass
        print("-" * 20)
except Exception as e:
    print(f"Error listing models: {e}")
