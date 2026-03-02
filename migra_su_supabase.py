# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

"""
migra_su_supabase.py -- Script di migrazione dati da SQLite a Supabase.
Da eseguire UNA SOLA VOLTA.

PREREQUISITI:
1. Credenziali in .streamlit/secrets.toml
2. supabase_schema.sql eseguito su Supabase
3. Bucket 'foto-esercizi' creato (Public)

ESECUZIONE:
   python migra_su_supabase.py
"""

import sqlite3
import os
import sys
import tomllib
from pathlib import Path
from supabase import create_client

BASE_DIR = Path(__file__).parent
DB_FILE  = BASE_DIR / "centro_fisioterapia.db"
FOTO_DIR = BASE_DIR / "foto" / "foto"
SECRETS_FILE = BASE_DIR / ".streamlit" / "secrets.toml"
BUCKET   = "foto-esercizi"

# -------------------------------------------------------
def carica_credenziali():
    if not SECRETS_FILE.exists():
        print(f"ERRORE: File non trovato: {SECRETS_FILE}")
        sys.exit(1)
    with open(SECRETS_FILE, "rb") as f:
        secrets = tomllib.load(f)
    url = secrets.get("SUPABASE_URL", "")
    key = secrets.get("SUPABASE_KEY", "")
    # service_key serve per upload Storage (bypassa RLS)
    # Se non presente nel secrets.toml, usa la anon key (potrebbe dare 403 su foto)
    service_key = secrets.get("SUPABASE_SERVICE_KEY", key)
    if "xxxx" in url or not url or not key:
        print("ERRORE: Credenziali non configurate in secrets.toml")
        sys.exit(1)
    return url, key, service_key

# -------------------------------------------------------
TABELLE_SEMPLICI = [
    "distretti", "fisioterapisti", "esercizi", "pazienti", "protocolli_info",
]
TABELLE_CON_FK = [
    "diario_clinico", "schede_pazienti", "protocolli_esercizi",
    "storico_report", "log_attivita",
]

def normalizza_valore(v):
    if v is None:
        return None
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return v

def migra_tabella(sb, sqlite_conn, nome_tabella):
    cur = sqlite_conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {nome_tabella}")
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(f"   SKIP '{nome_tabella}': {e}")
        return 0

    if not rows:
        print(f"   - {nome_tabella}: vuota")
        return 0

    # Pulisci Supabase prima
    try:
        sb.table(nome_tabella).delete().neq("id", 0).execute()
    except Exception:
        pass

    count = 0
    errori = 0
    cols = [d[0] for d in cur.description]
    for row in rows:
        data = {k: normalizza_valore(v) for k, v in zip(cols, row)}
        try:
            sb.table(nome_tabella).upsert(data).execute()
            count += 1
        except Exception as e:
            print(f"   ERRORE {nome_tabella} id={data.get('id')}: {e}")
            errori += 1

    if errori:
        print(f"   - {nome_tabella}: {count} OK, {errori} ERRORI")
    else:
        print(f"   OK {nome_tabella}: {count} righe")
    return count

# -------------------------------------------------------
def migra_foto(sb_admin):
    if not FOTO_DIR.exists():
        print("   SKIP: cartella 'foto/' non trovata.")
        return

    foto_files = [f for f in FOTO_DIR.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png')]
    if not foto_files:
        print("   Nessuna foto trovata.")
        return

    print(f"   Caricamento {len(foto_files)} foto...")
    ok = 0
    for foto_path in foto_files:
        try:
            with open(foto_path, "rb") as f:
                content = f.read()
            filename = foto_path.name
            try:
                sb_admin.storage.from_(BUCKET).remove([filename])
            except Exception:
                pass
            sb_admin.storage.from_(BUCKET).upload(
                filename, content,
                {"content-type": "image/jpeg", "upsert": "true"}
            )
            ok += 1
        except Exception as e:
            print(f"   ERRORE upload {foto_path.name}: {e}")

    print(f"   {ok}/{len(foto_files)} foto caricate")

# -------------------------------------------------------
def aggiorna_url_foto(sb):
    resp = sb.table("esercizi").select("id,foto_path").execute()
    esercizi = resp.data or []
    aggiornati = 0
    for es in esercizi:
        fp = es.get("foto_path", "")
        if not fp or fp.startswith("http"):
            continue
        filename = os.path.basename(fp)
        if not filename:
            continue
        url = sb.storage.from_(BUCKET).get_public_url(filename)
        sb.table("esercizi").update({"foto_path": url}).eq("id", es["id"]).execute()
        aggiornati += 1
    print(f"   {aggiornati} URL foto aggiornati")

# -------------------------------------------------------
def main():
    print("\n" + "="*55)
    print("  FisioManager Pro -- Migrazione a Supabase")
    print("="*55)

    if not DB_FILE.exists():
        print(f"ERRORE: Database non trovato: {DB_FILE}")
        sys.exit(1)

    print("\nConnessione a Supabase...")
    url, key, service_key = carica_credenziali()
    sb       = create_client(url, key)         # anon key per tabelle
    sb_admin = create_client(url, service_key) # service_role key per Storage
    print("   OK Connesso!")

    print("\nConnessione a SQLite...")
    sqlite_conn = sqlite3.connect(str(DB_FILE))
    sqlite_conn.row_factory = sqlite3.Row
    print("   OK Connesso!")

    print("\nMigrazione tabelle...\n")
    for tabella in TABELLE_SEMPLICI + TABELLE_CON_FK:
        migra_tabella(sb, sqlite_conn, tabella)
    sqlite_conn.close()

    print("\nUpload foto...\n")
    migra_foto(sb_admin)

    print("\nAggiornamento URL foto...\n")
    aggiorna_url_foto(sb)

    print("\n" + "="*55)
    print("  MIGRAZIONE COMPLETATA!")
    print("="*55)
    print("\nApri l'app su Streamlit Cloud per verificare.\n")
    input("Premi INVIO per chiudere...")

if __name__ == "__main__":
    main()
