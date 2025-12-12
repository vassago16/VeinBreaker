import os
import sys
from openai import OpenAI
from openai import OpenAIError


api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    sys.exit("Missing OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=api_key)

try:
    response = client.responses.create(
        model="gpt-5-nano",
        input="write a haiku about ai",
        store=True,
    )
    print(response.output_text)
except OpenAIError as e:
    sys.exit(f"API error: {e}")
