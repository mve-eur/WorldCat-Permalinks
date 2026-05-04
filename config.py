#!/usr/bin/env python3
"""
config.py – Versleuteld beheer van API-sleutels voor WorldCat ISBN checker

Gebruik:
    python config.py            → interactief menu (sleutels instellen / wijzigen)
    import config; cfg = config.load(password)  → laad sleutels vanuit script

Vereiste:
    pip install cryptography
"""

import os
import sys
import json
import getpass
from pathlib import Path

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.fernet import Fernet, InvalidToken
    import base64
except ImportError:
    print("[FOUT] Installeer eerst: pip install cryptography")
    sys.exit(1)

# Pad naar het versleutelde credentials-bestand (naast dit script)
CREDENTIALS_FILE = Path(__file__).parent / "credentials.txt"

# Velden die opgeslagen worden
CREDENTIAL_FIELDS = {
    "WSKEY":               "WSKey (client key van OCLC)",
    "WSKEY_SECRET":        "WSKey Secret",
    "INSTITUTION_SYMBOL":  "Instituutssymbool (bijv. NL-HvA)",
}

SALT_SIZE   = 16   # bytes
ITERATIONS  = 390_000


# ---------------------------------------------------------------------------
# Interne hulpfuncties
# ---------------------------------------------------------------------------

def _derive_key(password: str, salt: bytes) -> bytes:
    """Leid een Fernet-sleutel af van wachtwoord + salt via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def _encrypt(data: dict, password: str) -> bytes:
    """Versleutel een dict naar bytes: [16-byte salt][Fernet-ciphertext]."""
    salt = os.urandom(SALT_SIZE)
    key  = _derive_key(password, salt)
    token = Fernet(key).encrypt(json.dumps(data).encode("utf-8"))
    return salt + token


def _decrypt(raw: bytes, password: str) -> dict:
    """Ontsleutel bytes terug naar dict. Gooit ValueError bij verkeerd wachtwoord."""
    salt  = raw[:SALT_SIZE]
    token = raw[SALT_SIZE:]
    key   = _derive_key(password, salt)
    try:
        plaintext = Fernet(key).decrypt(token)
    except InvalidToken:
        raise ValueError("Verkeerd wachtwoord of beschadigd credentials-bestand.")
    return json.loads(plaintext.decode("utf-8"))


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------

def save(data: dict, password: str, path: Path = CREDENTIALS_FILE) -> None:
    """Versleutel `data` en sla op in `path`."""
    path.write_bytes(_encrypt(data, password))
    print(f"✅ Credentials opgeslagen in: {path}")


def load(password: str, path: Path = CREDENTIALS_FILE) -> dict:
    """Laad en ontsleutel credentials uit `path`. Stopt met foutmelding bij mislukking."""
    if not path.exists():
        print(
            f"[FOUT] Geen credentials-bestand gevonden op: {path}\n"
            "       Stel eerst je API-sleutels in via:  python config.py"
        )
        sys.exit(1)
    try:
        return _decrypt(path.read_bytes(), password)
    except ValueError as exc:
        print(f"[FOUT] {exc}")
        sys.exit(1)


def credentials_exist(path: Path = CREDENTIALS_FILE) -> bool:
    return path.exists()


# ---------------------------------------------------------------------------
# Interactief menu (python config.py)
# ---------------------------------------------------------------------------

def _prompt_fields(existing: dict | None = None) -> dict:
    """Vraag om alle credentials. Toon bestaande waarde (gemaskeerd) als hint."""
    print()
    data = {}
    for key, label in CREDENTIAL_FIELDS.items():
        if existing and key in existing:
            hint = existing[key][:4] + "***"
            prompt = f"  {label} [{hint}]: "
        else:
            prompt = f"  {label}: "
        value = input(prompt).strip()
        if not value and existing and key in existing:
            value = existing[key]   # Behoud huidige waarde bij lege invoer
        data[key] = value
    return data


def _menu_setup(path: Path):
    """Stel nieuwe credentials in (of overschrijf bestaande)."""
    print("\n── Credentials instellen ──────────────────────────")
    print("Vul de API-sleutels in. Druk Enter om een bestaande waarde te behouden.\n")

    existing = None
    if path.exists():
        try:
            old_pw = getpass.getpass("Huidig wachtwoord (om bestaande waarden te tonen): ")
            existing = _decrypt(path.read_bytes(), old_pw)
        except ValueError:
            print("  Verkeerd wachtwoord – bestaande waarden kunnen niet getoond worden.")

    data = _prompt_fields(existing)

    print()
    while True:
        pw1 = getpass.getpass("Kies een wachtwoord voor versleuteling : ")
        pw2 = getpass.getpass("Bevestig wachtwoord                    : ")
        if pw1 == pw2 and pw1:
            break
        print("  Wachtwoorden komen niet overeen of zijn leeg. Probeer opnieuw.\n")

    save(data, pw1, path)


def _menu_show(path: Path):
    """Toon (gemaskeerde) opgeslagen waarden."""
    print("\n── Opgeslagen credentials (gemaskeerd) ─────────────")
    pw = getpass.getpass("Wachtwoord: ")
    try:
        data = _decrypt(path.read_bytes(), pw)
    except ValueError as exc:
        print(f"[FOUT] {exc}")
        return
    for key, label in CREDENTIAL_FIELDS.items():
        val = data.get(key, "")
        masked = val[:4] + "*" * max(0, len(val) - 4) if len(val) > 4 else "****"
        print(f"  {label:<35} {masked}")


def _menu_delete(path: Path):
    """Verwijder het credentials-bestand na bevestiging."""
    confirm = input("\nWeet je zeker dat je het credentials-bestand wilt verwijderen? (ja/nee): ")
    if confirm.strip().lower() == "ja":
        path.unlink(missing_ok=True)
        print("✅ Credentials-bestand verwijderd.")
    else:
        print("Geannuleerd.")


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║   WorldCat ISBN Checker – Credentials beheer ║")
    print("╚══════════════════════════════════════════════╝")

    while True:
        status = "aanwezig" if CREDENTIALS_FILE.exists() else "niet aanwezig"
        print(f"\nCredentials-bestand: {status}")
        print("\n  1) API-sleutels instellen / bijwerken")
        print("  2) Opgeslagen waarden tonen (gemaskeerd)")
        print("  3) Credentials-bestand verwijderen")
        print("  4) Afsluiten")

        keuze = input("\nKeuze [1-4]: ").strip()

        if keuze == "1":
            _menu_setup(CREDENTIALS_FILE)
        elif keuze == "2":
            if not CREDENTIALS_FILE.exists():
                print("  Geen credentials-bestand gevonden. Stel eerst sleutels in (optie 1).")
            else:
                _menu_show(CREDENTIALS_FILE)
        elif keuze == "3":
            if not CREDENTIALS_FILE.exists():
                print("  Geen credentials-bestand om te verwijderen.")
            else:
                _menu_delete(CREDENTIALS_FILE)
        elif keuze == "4":
            print("Tot ziens!")
            break
        else:
            print("  Ongeldige keuze.")


if __name__ == "__main__":
    main()
