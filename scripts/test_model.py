
import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
model = os.getenv("GEMINI_MODEL")

print(f"Testing connectivity with model: {model}")

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model=model,
        contents="Hello, simply say 'OK'.",
    )
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
