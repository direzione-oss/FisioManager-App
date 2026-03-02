"""
db_supabase.py — Layer database Supabase per FisioManager Pro
Sostituisce sqlite3 con chiamate alle API di Supabase.
"""
import streamlit as st
import pandas as pd
from typing import Optional
from supabase import create_client, Client
from datetime import datetime

# -------------------------------------------------------
# CONNESSIONE (singleton via session_state)
# -------------------------------------------------------
def get_supabase() -> Client:
    if "supabase_client" not in st.session_state:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        st.session_state.supabase_client = create_client(url, key)
    return st.session_state.supabase_client


# -------------------------------------------------------
# FUNZIONE GENERICA: query tabella → DataFrame
# -------------------------------------------------------
def query_df(table: str, select: str = "*", filters: dict = None,
             order: str = None, single: bool = False) -> pd.DataFrame:
    sb = get_supabase()
    q = sb.table(table).select(select)
    if filters:
        for col, val in filters.items():
            q = q.eq(col, val)
    if order:
        q = q.order(order)
    resp = q.execute()
    data = resp.data
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


def query_df_raw(table: str, select: str = "*", order: str = None) -> pd.DataFrame:
    """Query senza filtri."""
    return query_df(table, select=select, order=order)


def query_df_filter(table: str, col: str, val, select: str = "*",
                    order: str = None) -> pd.DataFrame:
    """Query con un singolo filtro di uguaglianza."""
    return query_df(table, select=select, filters={col: val}, order=order)


def query_sql(sql: str, params: tuple = ()) -> pd.DataFrame:
    """
    Esegue una query SQL arbitraria via Supabase RPC o POST /rest/v1/rpc.
    Per JOIN complessi usiamo la procedura stored 'run_query' (opzionale).
    Strategia alternativa: recuperiamo le tabelle singolarmente e facciamo merge in pandas.
    """
    # Questo metodo viene usato come fallback — le query con JOIN sono
    # gestite direttamente nelle funzioni specifiche sottostanti.
    raise NotImplementedError("Usa le funzioni specifiche per le query con JOIN.")


# -------------------------------------------------------
# INSERT / UPDATE / DELETE generici
# -------------------------------------------------------
def insert(table: str, data: dict) -> dict:
    sb = get_supabase()
    resp = sb.table(table).insert(data).execute()
    if resp.data:
        return resp.data[0]
    return {}


def update(table: str, data: dict, col: str, val) -> None:
    sb = get_supabase()
    sb.table(table).update(data).eq(col, val).execute()


def delete(table: str, col: str, val) -> None:
    sb = get_supabase()
    sb.table(table).delete().eq(col, val).execute()


def delete_filter(table: str, filters: dict) -> None:
    sb = get_supabase()
    q = sb.table(table).delete()
    for col, val in filters.items():
        q = q.eq(col, val)
    q.execute()


# -------------------------------------------------------
# LOG ATTIVITÀ
# -------------------------------------------------------
def registra_log(utente: str, azione: str, dettagli: str) -> None:
    try:
        insert("log_attivita", {
            "utente": utente,
            "azione": azione,
            "dettagli": dettagli,
            "data_ora": datetime.now().isoformat()
        })
    except Exception:
        pass


# -------------------------------------------------------
# QUERY CON JOIN (implementate in pandas)
# -------------------------------------------------------
def get_scheda_paziente(paziente_id: int) -> pd.DataFrame:
    """Restituisce la scheda esercizi di un paziente con dettagli esercizio."""
    schede = query_df_filter("schede_pazienti", "paziente_id", paziente_id)
    if schede.empty:
        return pd.DataFrame(columns=["id","ordine","nome","serie","rip","recupero","note","foto_path","descrizione"])
    esercizi = query_df_raw("esercizi")
    if esercizi.empty:
        return pd.DataFrame()
    merged = schede.merge(
        esercizi[["id","nome","foto_path","descrizione"]],
        left_on="esercizio_id", right_on="id", suffixes=("","_es")
    )
    merged = merged.rename(columns={"id": "id"})
    return merged.sort_values("ordine")


def get_distribuzione_distretti() -> pd.DataFrame:
    """Distribuzione distretti corporei dalla scheda pazienti."""
    schede = query_df_raw("schede_pazienti", select="esercizio_id")
    esercizi = query_df_raw("esercizi", select="id,distretto")
    if schede.empty or esercizi.empty:
        return pd.DataFrame()
    merged = schede.merge(esercizi, left_on="esercizio_id", right_on="id")
    return merged.groupby("distretto").size().reset_index(name="conteggio")


def get_trend_iscrizioni() -> pd.DataFrame:
    """Trend mensile iscrizioni pazienti."""
    df = query_df_raw("pazienti", select="data_registrazione")
    if df.empty or "data_registrazione" not in df.columns:
        return pd.DataFrame()
    df["data_registrazione"] = pd.to_datetime(df["data_registrazione"], errors="coerce")
    df["mese"] = df["data_registrazione"].dt.strftime("%Y-%m")
    return df.groupby("mese").size().reset_index(name="nuovi_pazienti").sort_values("mese")


def get_pazienti_in_scadenza(oggi_str: str) -> pd.DataFrame:
    """Pazienti attivi con data_revisione <= oggi."""
    df = query_df_filter("pazienti", "stato", "Attivo",
                         select="id,nome_completo,data_revisione,nota_revisione")
    if df.empty:
        return pd.DataFrame()
    df["data_revisione"] = pd.to_datetime(df["data_revisione"], errors="coerce")
    scaduti = df[df["data_revisione"] <= pd.to_datetime(oggi_str)]
    return scaduti.sort_values("data_revisione")


def get_protocollo_esercizi(protocollo_id: int) -> pd.DataFrame:
    """Esercizi di un protocollo con dettagli."""
    pe = query_df_filter("protocolli_esercizi", "protocollo_id", protocollo_id)
    if pe.empty:
        return pd.DataFrame()
    es = query_df_raw("esercizi")
    if es.empty:
        return pd.DataFrame()
    merged = pe.merge(es[["id","nome","foto_path"]], left_on="esercizio_id", right_on="id", suffixes=("","_es"))
    return merged.sort_values("ordine")


def get_report_esercizi(paziente_id: int) -> pd.DataFrame:
    """Come get_scheda_paziente ma con colonna descrizione completa per il PDF."""
    return get_scheda_paziente(paziente_id)


# -------------------------------------------------------
# SUPABASE STORAGE — Foto Esercizi
# -------------------------------------------------------
BUCKET = "foto-esercizi"


def upload_foto(nome_esercizio: str, file_bytes: bytes, mime: str = "image/jpeg") -> str:
    """
    Carica la foto su Supabase Storage.
    Restituisce l'URL pubblico da salvare nel DB.
    """
    sb = get_supabase()
    filename = f"{nome_esercizio.replace(' ', '_')}.jpg"
    try:
        sb.storage.from_(BUCKET).remove([filename])
    except Exception:
        pass
    sb.storage.from_(BUCKET).upload(
        filename,
        file_bytes,
        {"content-type": mime, "upsert": "true"}
    )
    url = sb.storage.from_(BUCKET).get_public_url(filename)
    return url


def get_foto_url(foto_path: str) -> Optional[str]:
    """
    Dato il valore foto_path salvato nel DB, restituisce un URL utilizzabile.
    Compatibile sia con i vecchi path locali (ignorati) che con gli URL Supabase.
    """
    if not foto_path:
        return None
    if foto_path.startswith("http"):
        return foto_path
    # Vecchio path locale: non utilizzabile sul cloud
    return None
