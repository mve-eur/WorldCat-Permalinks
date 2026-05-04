#!/usr/bin/env python3
"""
WorldCat Search API v2 - ISBN naar OCN holding checker (met LHR-verificatie)

Gebaseerd op de officiele OpenAPI-spec:
https://developer.api.oclc.org/docs/wcapi/v2/openapi-external-prod.yaml

Workflow per ISBN:
  1. /bibs-holdings?isbn=...&heldBySymbol=...
       -> alleen OCNs waarop jouw instelling een holding heeft (gefilterd)
  2. Per OCN: /my-holdings?oclcNumber=...
       -> controleer of er ook een LHR aan vastzit
  3. Eerste OCN met LHR wordt opgeslagen; zonder LHR -> eerste OCN toch ingevuld.

Statuskolom-waarden:
  "Holding gevonden (1 OCN)"    - een OCN gevonden, LHR aanwezig
  "Holding gevonden (N OCNs)"   - meerdere OCNs gevonden, eerste met LHR gebruikt
  "Geen LHR"                    - holding gevonden maar geen LHR bij jouw instelling
  "Geen holding"                - ISBN niet gevonden voor jouw instelling
  "Geen ISBN"                   - lege cel overgeslagen
  "API-fout: ..."               - technische fout

Vereisten:
    pip install requests pandas openpyxl tqdm cryptography

Stel eerst je API-sleutels in via:
    python config.py

Benodigde scopes voor je WSKey (developer.api.oclc.org):
    wcapi:view_institution_holdings
    wcapi:view_my_holdings

"""

import sys
import time
import base64
import getpass
from pathlib import Path
import requests
import pandas as pd
from tqdm import tqdm
import config as cfg

# ---------------------------------------------------------------------------
# Instellingen
# ---------------------------------------------------------------------------
TOKEN_URL    = "https://oauth.oclc.org/token"
API_BASE     = "https://americas.discovery.api.oclc.org/worldcat/search/v2"
BIB_HOLDINGS = f"{API_BASE}/bibs-holdings"   # filtert direct op heldBySymbol
MY_HOLDINGS  = f"{API_BASE}/my-holdings"

DELAY_SECONDS = 0.3

SCRIPT_DIR  = Path(__file__).parent
INPUT_FILE  = SCRIPT_DIR / "input.xlsx"

DEFAULT_OCN_COL    = "OCN"
DEFAULT_STATUS_COL = "Status"


# ---------------------------------------------------------------------------
# Authenticatie
# ---------------------------------------------------------------------------

class TokenManager:
    """Beheert het OAuth-token en vernieuwt automatisch bij verlopen."""

    def __init__(self, wskey: str, secret: str):
        self.wskey  = wskey
        self.secret = secret
        self._token = None

    def get(self) -> str:
        if not self._token:
            self._token = self._fetch()
        return self._token

    def refresh(self) -> str:
        self._token = self._fetch()
        return self._token

    def _fetch(self) -> str:
        credentials = base64.b64encode(f"{self.wskey}:{self.secret}".encode()).decode()
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": "wcapi"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"\n[FOUT] Token ophalen mislukt ({resp.status_code}): {resp.text}")
            sys.exit(1)
        return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# API-hulpfunctie
# ---------------------------------------------------------------------------

def _get(url: str, params: dict, token_mgr: TokenManager) -> dict:
    """GET met automatische token-refresh bij 401."""
    for attempt in range(2):
        try:
            resp = requests.get(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {token_mgr.get()}",
                    "Accept": "application/json",
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            return {"status": 0, "body": {}, "error": str(exc)}

        if resp.status_code == 401 and attempt == 0:
            token_mgr.refresh()
            continue

        try:
            body = resp.json()
        except Exception:
            body = {}
        return {"status": resp.status_code, "body": body}

    return {"status": 401, "body": {}}


# ---------------------------------------------------------------------------
# Stap 1: OCNs ophalen via bibs-holdings (gefilterd op instituut)
# ---------------------------------------------------------------------------

def get_ocns_for_isbn(isbn: str, symbol: str, token_mgr: TokenManager) -> list | dict:
    """
    Vraag /bibs-holdings op met isbn + heldBySymbol.
    Geeft alleen OCNs terug waarop jouw instelling een holding heeft.
    """
    result = _get(
        BIB_HOLDINGS,
        {"isbn": isbn, "heldBySymbol": symbol, "limit": 50},
        token_mgr,
    )

    if "error" in result:
        return {"error": result["error"]}
    if result["status"] == 400:
        msg = result["body"].get("message", "")
        return {"error": f"Ongeldig verzoek (400): {msg}"}
    if result["status"] != 200:
        return {"error": f"HTTP {result['status']}"}

    records = result["body"].get("briefRecords", [])
    ocns = [str(r["oclcNumber"]) for r in records if r.get("oclcNumber")]
    return ocns


# ---------------------------------------------------------------------------
# Stap 2: LHR-check per OCN
# ---------------------------------------------------------------------------

def has_lhr(ocn: str, token_mgr: TokenManager) -> bool | dict:
    """
    Vraag /my-holdings op voor dit OCN.
    Geeft True als er een LHR bestaat, False als niet, of {"error": ...}.
    """
    result = _get(MY_HOLDINGS, {"oclcNumber": ocn, "limit": 1}, token_mgr)

    if "error" in result:
        return {"error": result["error"]}
    if result["status"] == 404:
        return False
    if result["status"] != 200:
        return {"error": f"HTTP {result['status']} bij LHR-check"}

    entries = result["body"].get("detailedHoldings", [])
    return len(entries) > 0


# ---------------------------------------------------------------------------
# Verwerking per ISBN
# ---------------------------------------------------------------------------

def process_isbn(isbn: str, symbol: str, token_mgr: TokenManager) -> dict:
    """
    Stap 1: haal OCNs op via bibs-holdings (gefilterd op jouw instelling).
    Stap 2: controleer per OCN of er een LHR aan vastzit.
    Eerste OCN met LHR wint. Zonder LHR: eerste OCN toch ingevuld.
    """
    ocns = get_ocns_for_isbn(isbn, symbol, token_mgr)
    time.sleep(DELAY_SECONDS)

    if isinstance(ocns, dict):
        return {"ocn": "", "status": f"API-fout: {ocns['error']}"}

    if not ocns:
        return {"ocn": "", "status": "Geen holding"}

    ocn_count = len(ocns)

    for ocn in ocns:
        lhr = has_lhr(ocn, token_mgr)
        time.sleep(DELAY_SECONDS)

        if isinstance(lhr, dict):
            return {"ocn": ocns[0], "status": f"API-fout: {lhr['error']}"}

        if lhr:
            if ocn_count == 1:
                status = "Holding gevonden (1 OCN)"
            else:
                status = f"Holding gevonden ({ocn_count} OCNs)"
            return {"ocn": ocn, "status": status}

    # Holdings gevonden maar geen LHR - vul toch eerste OCN in
    return {"ocn": ocns[0], "status": "Geen LHR"}


# ---------------------------------------------------------------------------
# Hoofdverwerking
# ---------------------------------------------------------------------------

def main():
    print("=" * 54)
    print("  WorldCat Search API v2 - ISBN holding checker")
    print("=" * 54)

    if not INPUT_FILE.exists():
        print(f"\n[FOUT] Bestand niet gevonden: {INPUT_FILE}")
        print("Zet input.xlsx in dezelfde map als dit script.")
        sys.exit(1)

    if not cfg.credentials_exist():
        print("\n[FOUT] Geen credentials gevonden. Stel ze in via: python config.py")
        sys.exit(1)

    password = getpass.getpass("\nWachtwoord voor API-sleutels: ")
    creds    = cfg.load(password)
    del password

    token_mgr = TokenManager(creds["WSKEY"], creds["WSKEY_SECRET"])
    symbol    = creds["INSTITUTION_SYMBOL"]

    print(f"input.xlsx gevonden!")
    df = pd.read_excel(INPUT_FILE, dtype=str)
    isbn_col = "ISBN"

    df[DEFAULT_OCN_COL]    = ""
    df[DEFAULT_STATUS_COL] = ""

    total   = len(df)
    found   = 0
    multi   = 0
    no_lhr  = 0
    no_hold = 0
    errors  = 0

    print(f"\n{total} rijen verwerken...\n")

    for idx, row in tqdm(df.iterrows(), total=total, unit="ISBN"):
        raw_isbn = str(row[isbn_col]).strip()

        if not raw_isbn or raw_isbn.lower() in ("nan", "none", ""):
            df.at[idx, DEFAULT_OCN_COL]    = ""
            df.at[idx, DEFAULT_STATUS_COL] = "Geen ISBN"
            continue

        isbn   = raw_isbn.replace("-", "").replace(" ", "")
        result = process_isbn(isbn, symbol, token_mgr)

        df.at[idx, DEFAULT_OCN_COL]    = result["ocn"]
        df.at[idx, DEFAULT_STATUS_COL] = result["status"]
        df.at[idx, "Link"] = "https://eur.on.worldcat.org/oclc/" + result["ocn"]

        s = result["status"]
        if s.startswith("Holding gevonden"):
            found += 1
            if "OCNs)" in s:
                multi += 1
        elif s == "Geen LHR":
            no_lhr += 1
        elif s == "Geen holding":
            no_hold += 1
        elif s.startswith("API-fout"):
            errors += 1

    output_path = SCRIPT_DIR / "output.xlsx"
    df.to_excel(output_path, index=False)

    print(f"""
Totaal verwerkt         : {total}
Holding + LHR gevonden  : {found}  (waarvan {multi} met meerdere OCNs)
Geen LHR                : {no_lhr}
Geen holding            : {no_hold}
Fouten                  : {errors}

Script klaar! Resultaat opgeslagen in: {output_path}
""")


if __name__ == "__main__":
    main()