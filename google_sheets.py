"""
Modulo Google Sheets — versione Railway.
Legge SPREADSHEET_ID e GOOGLE_CREDENTIALS dalle variabili d'ambiente.
"""

import gspread
import os
import json
import tempfile
from google.oauth2.service_account import Credentials
from datetime import datetime

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]

def get_client():
    creds_json = os.environ["GOOGLE_CREDENTIALS"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    client = gspread.authorize(creds)
    return client

def ensure_header(sheet):
    existing = sheet.get_all_values()
    if not existing:
        header = [
            "Timestamp", "User ID", "Username", "Fantallenatore",
            "Nome Squadra", "Portiere",
            "Campo 1", "Campo 2", "Campo 3", "Campo 4",
            "Campo 5", "Campo 6", "Crediti Spesi"
        ]
        sheet.append_row(header, value_input_option="RAW")

def save_to_sheet(user, players: list, total: float, nome_squadra: str = ""):
    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet = spreadsheet.sheet1
    ensure_header(sheet)

    por = [p["nome"] for p in players if p["ruolo"] == "POR"]
    cam = [p["nome"] for p in players if p["ruolo"] == "CAM"]

    def pad(lst, n):
        return (lst + [""] * n)[:n]

    row = [
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        str(user.id),
        f"@{user.username}" if user.username else "N/A",
        f"{user.first_name} {user.last_name or ''}".strip(),
        nome_squadra,
        *pad(por, 1),
        *pad(cam, 6),
        str(total),
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")
