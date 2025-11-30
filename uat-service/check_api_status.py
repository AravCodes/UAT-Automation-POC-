"""
Quick script to check OpenAI API key status.
Run this anytime to verify your API key configuration.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ OPENAI_API_KEY not set in environment or .env file")
    print("\nTo fix:")
    print("1. Create uat-service/.env file")
    print("2. Add: OPENAI_API_KEY=sk-your-key-here")
else:
    print(f"✅ API Key configured: {api_key[:10]}...{api_key[-4:]}")
    print("\nTesting connection...")
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        print("✅ API is working!")
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "insufficient_quota" in error_msg.lower():
            print("⚠️  API Key is valid but QUOTA EXCEEDED")
            print("\nTo fix:")
            print("1. Go to https://platform.openai.com/account/billing")
            print("2. Add payment method and credits")
            print("3. Or upgrade your plan")
        elif "invalid" in error_msg.lower() or "401" in error_msg:
            print("❌ Invalid API Key")
            print("Get a new key at: https://platform.openai.com/api-keys")
        else:
            print(f"❌ Error: {error_msg}")

