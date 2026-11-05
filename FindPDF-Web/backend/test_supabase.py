
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Locate the .env file in the pdf-chatbot root folder.
project_root = Path(__file__).resolve().parents[2]
env_path = project_root / ".env"

load_dotenv(env_path)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise SystemExit(
        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env"
    )

try:
    client = create_client(url, key)

    result = (
        client.table("documents")
        .select("id")
        .limit(1)
        .execute()
    )

    print("Supabase connection successful!")
    print("Documents table is accessible.")
    print("Existing document rows:", len(result.data))

except Exception as exc:
    print("Supabase connection test failed.")
    print(type(exc).__name__ + ":", str(exc))
