from pathlib import Path
import os
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"


def credentials_exist():
    return ENV_FILE.exists()


def load():
    load_dotenv(ENV_FILE)

    wskey = os.getenv("WSKEY")
    secret = os.getenv("WSKEY_SECRET")
    symbol = os.getenv("INSTITUTION_SYMBOL")

    missing = []

    if not wskey:
        missing.append("WSKEY")

    if not secret:
        missing.append("WSKEY_SECRET")

    if not symbol:
        missing.append("INSTITUTION_SYMBOL")

    if missing:
        raise ValueError(
            f"Ontbrekende variabelen in .env: {', '.join(missing)}"
        )

    return {
        "WSKEY": wskey,
        "WSKEY_SECRET": secret,
        "INSTITUTION_SYMBOL": symbol,
    }


if __name__ == "__main__":
    print(f".env gevonden: {ENV_FILE.exists()}")

    if ENV_FILE.exists():
        print(f"Locatie: {ENV_FILE}")
