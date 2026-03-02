import streamlit as st
import os
import pandas as pd
import altair as alt
import tempfile
from datetime import datetime, date, timedelta
from fpdf import FPDF
from PIL import Image
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
from db_supabase import (
    get_supabase, query_df_raw, query_df_filter,
    insert, update, delete, delete_filter, registra_log,
    get_scheda_paziente, get_distribuzione_distretti,
    get_trend_iscrizioni, get_pazienti_in_scadenza,
    get_protocollo_esercizi, get_report_esercizi,
    upload_foto, get_foto_url
)

# --- 1. CONFIGURAZIONE E PERCORSI ASSOLUTI ---
st.set_page_config(page_title="Centro Medico For Me", layout="wide", page_icon="🏥")

# Calcolo percorsi assoluti
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOTO_DIR = os.path.join(BASE_DIR, "foto")
PDF_DIR = os.path.join(BASE_DIR, "report_pdf")
DB_FILE = os.path.join(BASE_DIR, "centro_fisioterapia.db")

# Creazione cartelle se non esistono (solo locale, può fallire su cloud)
try:
    if not os.path.exists(FOTO_DIR): os.makedirs(FOTO_DIR)
    if not os.path.exists(PDF_DIR): os.makedirs(PDF_DIR)
except Exception:
    pass

# --- 🔐 GESTIONE SICUREZZA ---
UTENTI = {
    "admin": {"name": "Direzione", "password": "admin", "role": "admin"},
    "fisio1": {"name": "Fisioterapia", "password": "fisio", "role": "user"},
}

if 'authentication_status' not in st.session_state:
    st.session_state.authentication_status = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'username' not in st.session_state:
    st.session_state.username = None

# Definizione Variabili Colori
PRIMARY_COLOR = "#006D77"
SECONDARY_COLOR = "#83C5BE"
BG_COLOR = "#F8F9FA"
TEXT_COLOR = "#333333"

# Iniezione CSS
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Open+Sans:wght@400;600&display=swap');
        .stApp {{ font-family: 'Open Sans', sans-serif; color: {TEXT_COLOR}; background-color: #FFFFFF; }}
        h1, h2, h3, h4, .st-emotion-cache-10trblm {{ font-family: 'Montserrat', sans-serif; font-weight: 700; color: {PRIMARY_COLOR} !important; }}
        section[data-testid="stSidebar"] {{ background-color: {BG_COLOR}; border-right: 1px solid #EFEFEF; }}
        div.stButton > button {{ font-family: 'Montserrat', sans-serif; font-weight: 600; border-radius: 8px; border: none; background-color: {PRIMARY_COLOR}; color: white; transition: all 0.3s ease; }}
        div.stButton > button:hover {{ background-color: {SECONDARY_COLOR}; color: {PRIMARY_COLOR}; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        div.stButton > button[kind="primary"] {{ background-color: #E76F51; }}
        div.stButton > button[kind="primary"]:hover {{ background-color: #F4A261; }}
        .st-emotion-cache-1r6slb0, .st-emotion-cache-10y5sf6 {{ border: 1px solid #E0E0E0; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        .main-title {{ font-family: 'Montserrat', sans-serif; color: {PRIMARY_COLOR}; text-align: center; font-size: 2.5rem; font-weight: 700; margin-bottom: 0px; padding-top: 10px; }}
        hr {{ border-color: #EFEFEF; }}
        [data-testid="stSidebar"] {{ display: {'block' if st.session_state.authentication_status else 'none'}; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. CONNESSIONE SUPABASE ---
# La connessione è gestita dal modulo db_supabase.py
# I secrets (SUPABASE_URL / SUPABASE_KEY) vengono letti da:
#   - Locale: .streamlit/secrets.toml
#   - Cloud:  Streamlit Cloud → App Settings → Secrets

def _log(azione, dettagli):
    """Wrapper per registra_log che usa il session_state per l'utente."""
    utente = st.session_state.get("username", "sistema")
    registra_log(utente, azione, dettagli)

# --- LOGIN ---
def check_login():
    if st.session_state.authentication_status: return
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        img_logo = os.path.join(BASE_DIR, "Immagine1.png")
        if os.path.exists(img_logo): st.image(img_logo, use_container_width=True)
        else: st.markdown('<div class="main-title">Centro Medico For Me</div>', unsafe_allow_html=True)
        
        st.markdown("<h4 style='text-align: center; color: #666;'>Portale Accesso Riservato</h4>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Nome Utente")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Entra 🔐", use_container_width=True)
            if submit:
                if username in UTENTI and UTENTI[username]['password'] == password:
                    st.session_state.authentication_status = True
                    st.session_state.user_role = UTENTI[username]['role']
                    st.session_state.username = UTENTI[username]['name']
                    _log("Login", f"Accesso: {username}")
                    st.rerun()
                else: st.error("Credenziali non valide.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        img_info = os.path.join(BASE_DIR, "infografica.png")
        if os.path.exists(img_info): st.image(img_info, use_container_width=True)

if not st.session_state.authentication_status:
    check_login()
    st.stop()

# --- CARICAMENTO STATO ---
if 'pagina_attiva' not in st.session_state: st.session_state.pagina_attiva = "🏠 Home & Statistiche"
if 'paziente_target_id' not in st.session_state: st.session_state.paziente_target_id = None
if 'edit_esercizio_id' not in st.session_state: st.session_state.edit_esercizio_id = None

# --- 3. MOTORE PDF (FIX IMMAGINI DOPPIE) ---
class PDF(FPDF):
    def header(self):
        logo_path = os.path.join(BASE_DIR, "Immagine1.png")
        if os.path.exists(logo_path): 
            try: self.image(logo_path, 160, 8, 35)
            except: pass
        
        self.set_font('Arial', 'B', 18)
        self.set_text_color(0, 109, 119)
        self.cell(0, 10, 'Centro Medico For Me', 0, 1, 'L') 

        self.set_draw_color(0, 109, 119)
        self.set_line_width(0.5)
        self.line(10, 20, 200, 20)
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def normalizza_immagine_per_pdf(path_originale):
    """
    Crea un file temporaneo UNIVOCE per ogni immagine per evitare che FPDF
    usi la cache e ripeta la stessa immagine.
    """
    try:
        # Crea un nome file temporaneo unico basato sul nome originale
        nome_univoco = f"temp_{os.path.basename(path_originale)}"
        # Assicura estensione .jpg
        nome_univoco = os.path.splitext(nome_univoco)[0] + ".jpg"
        temp_path = os.path.join(BASE_DIR, nome_univoco)

        with Image.open(path_originale) as img:
            img.convert('RGB').save(temp_path, "JPEG", quality=90)
        return temp_path
    except Exception as e:
        print(f"Errore conversione immagine {path_originale}: {e}")
        return None

def genera_pdf_fisico(paziente, esercizi_df, data_report, nome_fisio):
    pdf = PDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    
    # Intestazione paziente compatta
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(10, pdf.get_y(), 190, 18, 'F')
    pdf.set_xy(12, pdf.get_y()+2)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 6, f"Paziente: {paziente['nome_completo']}", ln=0)
    pdf.cell(85, 6, f"Fisioterapista: {nome_fisio}", ln=1, align='R')
    pdf.set_x(12)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, f"Data Nascita: {paziente['data_nascita']}", ln=0)
    pdf.cell(85, 6, f"Data Scheda: {data_report.strftime('%d/%m/%Y')}", ln=1, align='R')
    
    pdf.ln(2)
    # Diagnosi inline (label e testo sulla stessa riga)
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0, 0, 0)
    try:
        diag_txt = paziente.get('diagnosi') or '-'
        diag_txt = diag_txt.encode('latin-1', 'replace').decode('latin-1')
    except:
        diag_txt = str(paziente.get('diagnosi', '-'))
    pdf.multi_cell(0, 6, f"Diagnosi / Obiettivi:  {diag_txt}", border=0, fill=True)
    pdf.cell(0, 2, "", fill=True, ln=True)
    pdf.set_fill_color(255, 255, 255)
    pdf.ln(3)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # Layout
    PHOTO_W = 55
    PHOTO_H = 50
    ROW_H = 58
    TEXT_X_START = 70
    TEXT_W = 130
    PAGE_LIMIT_Y = 270

    for _, row in esercizi_df.iterrows():
        if pdf.get_y() + ROW_H > PAGE_LIMIT_Y:
            pdf.add_page()
            pdf.ln(5)

        start_y = pdf.get_y()
        
        # --- GESTIONE FOTO (supporta file locali e URL Supabase) ---
        path_db = row.get('foto_path') or ''
        img_source = None
        
        # 1. Prova file locale
        if path_db and not path_db.startswith('http'):
            filename = os.path.basename(path_db)
            local_path = os.path.join(FOTO_DIR, filename)
            if os.path.exists(local_path):
                img_source = local_path
        
        # 2. Prova URL Supabase → scarica in temp
        if not img_source and path_db.startswith('http'):
            try:
                import urllib.request, tempfile
                from urllib.parse import unquote
                url_filename = unquote(path_db.split('/')[-1])
                tmp_file = os.path.join(tempfile.gettempdir(), f"pdf_{url_filename}")
                urllib.request.urlretrieve(path_db, tmp_file)
                img_source = tmp_file
            except Exception:
                img_source = None
        
        if img_source:
            safe_img = normalizza_immagine_per_pdf(img_source)
            if safe_img:
                try:
                    # Calcola dimensioni proporzionali nel box PHOTO_W x PHOTO_H
                    with Image.open(safe_img) as img_tmp:
                        w_px, h_px = img_tmp.size
                    ratio = w_px / h_px
                    # Adatta al box mantenendo proporzioni
                    if ratio >= (PHOTO_W / PHOTO_H):
                        # Immagine più larga: limita per larghezza
                        img_w = PHOTO_W
                        img_h = PHOTO_W / ratio
                    else:
                        # Immagine più alta: limita per altezza
                        img_h = PHOTO_H
                        img_w = PHOTO_H * ratio
                    # Centra nello spazio (orizzontale e verticale)
                    img_x = 10 + (PHOTO_W - img_w) / 2
                    img_y = start_y + (PHOTO_H - img_h) / 2
                    pdf.image(safe_img, x=img_x, y=img_y, w=img_w, h=img_h)
                except Exception:
                    pdf.set_xy(10, start_y)
                    pdf.set_font("Arial", 'B', 8)
                    pdf.set_text_color(255, 0, 0)
                    pdf.cell(PHOTO_W, PHOTO_H, "ERR FORMATO", border=1, align='C')
            else:
                 pdf.set_xy(10, start_y)
                 pdf.set_font("Arial", 'B', 8)
                 pdf.set_text_color(255, 0, 0)
                 pdf.cell(PHOTO_W, PHOTO_H, "ERR CONV", border=1, align='C')
        else:
            pdf.set_xy(10, start_y)
            pdf.set_font("Arial", 'I', 8)
            pdf.set_text_color(200,200,200)
            pdf.cell(PHOTO_W, PHOTO_H, "No Foto", border=1, align='C')

        # --- QR CODE VIDEO (in basso, sotto la foto) ---
        video_url = row.get('video_url') or ''
        if video_url and HAS_QRCODE:
            try:
                QR_SIZE = 15
                qr = qrcode.QRCode(version=1, box_size=5, border=1)
                qr.add_data(video_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_path = os.path.join(tempfile.gettempdir(), f"qr_{row['id']}.png")
                qr_img.save(qr_path)
                # Posiziona QR a destra della foto
                qr_x = 10 + PHOTO_W + 2
                qr_y = start_y + PHOTO_H - QR_SIZE
                pdf.image(qr_path, x=qr_x, y=qr_y, w=QR_SIZE, h=QR_SIZE)
                pdf.set_xy(qr_x, qr_y + QR_SIZE)
                pdf.set_font("Arial", 'I', 5)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(QR_SIZE, 3, "Video", align='C')
            except Exception:
                pass

        # --- TESTO ---
        pdf.set_xy(TEXT_X_START, start_y)
        try: nome_clean = row['nome'].encode('latin-1', 'replace').decode('latin-1')
        except: nome_clean = row['nome']
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(0, 109, 119)
        pdf.multi_cell(TEXT_W, 6, f"{row['ordine']}. {nome_clean}", align='L')

        pdf.set_x(TEXT_X_START)
        pdf.set_font("Arial", 'B', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(230, 240, 240)
        pdf.cell(TEXT_W, 6, f"  Serie: {row['serie']}", ln=True, fill=True)
        pdf.set_x(TEXT_X_START)
        pdf.cell(TEXT_W, 6, f"  Ripetizioni: {row['rip']}", ln=True, fill=True)
        pdf.set_x(TEXT_X_START)
        pdf.cell(TEXT_W, 6, f"  Recupero: {row['recupero']}", ln=True, fill=True)
        
        pdf.set_x(TEXT_X_START)
        pdf.set_font("Arial", '', 10)
        if row['descrizione']:
            try: desc_clean = row['descrizione'].encode('latin-1', 'replace').decode('latin-1')
            except: desc_clean = row['descrizione']
            pdf.multi_cell(TEXT_W, 5, desc_clean, align='L')
        
        if row['note']:
            pdf.set_x(TEXT_X_START)
            pdf.set_font("Arial", 'I', 10)
            pdf.set_text_color(200, 50, 50)
            try: note_clean = row['note'].encode('latin-1', 'replace').decode('latin-1')
            except: note_clean = row['note']
            pdf.multi_cell(TEXT_W, 5, f"NOTA: {note_clean}", align='L')
            pdf.set_text_color(0, 0, 0)

        # --- SPAZIATURA FISSA ---
        final_y = start_y + ROW_H
        
        pdf.set_draw_color(220, 220, 220)
        pdf.line(10, final_y, 200, final_y)
        pdf.set_y(final_y + 2)

    filename = f"Scheda_{paziente['nome_completo'].replace(' ', '_')}_{data_report}.pdf"
    path = os.path.join(PDF_DIR, filename)
    pdf.output(path)
    
    # --- PULIZIA FILE TEMPORANEI ---
    # Cancella tutti i file che iniziano con temp_ e finiscono con .jpg
    for f in os.listdir(BASE_DIR):
        if f.startswith("temp_") and f.endswith(".jpg"):
            try: os.remove(os.path.join(BASE_DIR, f))
            except: pass
            
    return filename, path

def selettore_paziente_ricerca(label, chiave, solo_attivi=True):
    if solo_attivi:
        df = query_df_filter("pazienti", "stato", "Attivo", order="nome_completo")
    else:
        df = query_df_raw("pazienti", order="nome_completo")
    if df.empty: return None
    index_pre = 0
    if st.session_state.paziente_target_id is not None:
        try:
            match = df[df['id'] == st.session_state.paziente_target_id]
            if not match.empty:
                nome_target = match.iloc[0]['nome_completo']
                lista_nomi = [""] + df['nome_completo'].tolist()
                if nome_target in lista_nomi: index_pre = lista_nomi.index(nome_target)
        except: pass
    scelta = st.selectbox(label, options=[""] + df['nome_completo'].tolist(), index=index_pre, key=chiave)
    if scelta != "" and st.session_state.paziente_target_id:
        curr_id = df[df['nome_completo'] == scelta].iloc[0]['id']
        if curr_id != st.session_state.paziente_target_id: st.session_state.paziente_target_id = None
    return df[df['nome_completo'] == scelta].iloc[0] if scelta != "" else None

# --- SIDEBAR ---
menu = ["🏠 Home & Statistiche", "👤 Anagrafica Pazienti", "👨‍⚕️ Team Fisioterapisti", "🏋️ Catalogo Esercizi", "📋 Protocolli", "📝 Assegna a Paziente", "📑 Report & Storico"]
if st.session_state.user_role == 'admin': menu.append("💾 Backup & Ripristino")
try: nav_index = menu.index(st.session_state.pagina_attiva)
except: nav_index = 0

with st.sidebar:
    img_logo = os.path.join(BASE_DIR, "Immagine1.png")
    if os.path.exists(img_logo): st.image(img_logo, use_container_width=True)
    else: st.title("Centro Medico For Me")
    # QR code accesso rapido
    if HAS_QRCODE:
        import io, base64
        app_url = "https://fisiomanager-app-uwlds5nytmqvq4xzsyzdvh.streamlit.app/"
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(app_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#006D77", back_color="white")
        buf = io.BytesIO()
        qr_img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        st.markdown(f'<div style="text-align:center;margin:-5px 0 5px"><img src="data:image/png;base64,{b64}" width="90"><br><span style="font-size:9px;color:#999">📱 Accesso telefono</span></div>', unsafe_allow_html=True)
    
    st.write(f"👤 **{st.session_state.username}**") 
    if st.button("Esci / Logout"):
        _log("Logout", "Uscita utente")
        st.session_state.authentication_status = None
        st.rerun()
    st.markdown("---")
    scelta = st.radio("Menu", menu, index=nav_index, label_visibility="collapsed")
    st.markdown("---")
    
    st.markdown("**ℹ️ Guida all'uso**")
    percorso_pdf = os.path.join(BASE_DIR, "ManualeUtente.pdf")
    if os.path.exists(percorso_pdf):
        with open(percorso_pdf, "rb") as pdf_file:
            st.download_button("📘 Scarica Manuale", data=pdf_file, file_name="ManualeUtente.pdf", mime="application/pdf", key="btn_manuale_sidebar")
    else: st.caption("Manuale non trovato.")

if scelta != st.session_state.pagina_attiva:
    st.session_state.pagina_attiva = scelta
    st.session_state.paziente_target_id = None
    st.rerun()

st.markdown('<div class="main-title">Centro Medico For Me</div>', unsafe_allow_html=True)
st.markdown("---")

# =======================================================
# PAGINA 1: HOME
# =======================================================
if scelta == "🏠 Home & Statistiche":
    st.subheader("Dashboard & Analytics")
    try:
        tot_paz = len(query_df_raw("pazienti", select="id"))
        tot_es = len(query_df_raw("esercizi", select="id"))
        with st.container(border=True):
            c_a, c_b = st.columns(2)
            c_a.metric("Totale Storico Pazienti", tot_paz)
            c_b.metric("Esercizi in Catalogo", tot_es)
    except: pass
    st.subheader("📊 Statistiche Centro")
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.markdown("**Distretti Corporei**")
        df_dist = get_distribuzione_distretti()
        if not df_dist.empty:
            chart_torta = alt.Chart(df_dist).mark_arc(innerRadius=60).encode(theta=alt.Theta(field="conteggio", type="quantitative"), color=alt.Color(field="distretto", type="nominal", scale=alt.Scale(scheme='tealblues')), tooltip=["distretto", "conteggio"])
            st.altair_chart(chart_torta, use_container_width=True)
        else: st.info("Dati insufficienti.")
    with col_stat2:
        st.markdown("**Trend Iscrizioni**")
        try:
            df_trend = get_trend_iscrizioni()
            if not df_trend.empty:
                chart_linea = alt.Chart(df_trend).mark_bar(color=PRIMARY_COLOR).encode(x=alt.X('mese:O', axis=alt.Axis(title='Mese')), y=alt.Y('nuovi_pazienti:Q', title='Iscritti'), tooltip=['mese', 'nuovi_pazienti']).interactive()
                st.altair_chart(chart_linea, use_container_width=True)
            else: st.info("Dati insufficienti.")
        except: st.warning("Attendere dati.")
    st.markdown("---")
    st.subheader("⚠️ Scadenze e Revisioni")
    df_alt = get_pazienti_in_scadenza(date.today().isoformat())
    if not df_alt.empty:
        st.error(f"⚠️ {len(df_alt)} Pazienti richiedono Revisione")
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown("**Paziente**")
            c2.markdown("**Scadenza & Nota**")
            c3.markdown(" ")
            st.divider()
            for _, row in df_alt.iterrows():
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{row['nome_completo']}**")
                nota_display = f" - *{row['nota_revisione']}*" if row['nota_revisione'] else ""
                c2.markdown(f":red[{str(row['data_revisione'])[:10]}] {nota_display}")
                if c3.button("Vai ➡️", key=f"btn_alert_{row['id']}"):
                    st.session_state.pagina_attiva = "📑 Report & Storico"
                    st.session_state.paziente_target_id = row['id']
                    st.rerun()
                st.divider()
    else: st.success("✅ Nessuna revisione in scadenza.")

# =======================================================
# PAGINA 2: ANAGRAFICA
# =======================================================
elif scelta == "👤 Anagrafica Pazienti":
    t1, t2, t3, t4, t5 = st.tabs(["🆕 Registra", "✏️ Modifica/Dimetti", "🗑️ Elimina", "🔎 Ricerca", "📖 Diario Clinico"])
    with t1:
        with st.form("p_new"):
            n = st.text_input("Nome e Cognome")
            d_n = st.date_input("Nascita", value=date(1980,1,1), min_value=date(1900,1,1), max_value=date(2300,12,31))
            dia = st.text_area("Diagnosi Iniziale")
            rev_default = date.today() + timedelta(days=30)
            if st.form_submit_button("Salva"):
                insert("pazienti", {"nome_completo": n, "data_nascita": str(d_n), "diagnosi": dia, "data_registrazione": str(date.today()), "data_revisione": str(rev_default), "stato": "Attivo"})
                _log("Nuovo Paziente", f"Creato: {n}")
                st.success("Registrato!")
    with t2:
        p_mod = selettore_paziente_ricerca("Cerca paziente", "p_mod_key", solo_attivi=False)
        if p_mod is not None:
            with st.form("p_edit"):
                un = st.text_input("Nome", p_mod['nome_completo'])
                try: d_orig = datetime.strptime(p_mod['data_nascita'], '%Y-%m-%d').date()
                except: d_orig = date(1980,1,1)
                try: r_orig = datetime.strptime(p_mod['data_revisione'], '%Y-%m-%d').date()
                except: r_orig = date.today()
                ud_n = st.date_input("Nascita", value=d_orig, min_value=date(1900,1,1), max_value=date(2300,12,31))
                c_rev_d, c_rev_n = st.columns([1, 2])
                ud_rev = c_rev_d.date_input("Data Revisione", value=r_orig)
                ud_nota_rev = c_rev_n.text_input("Nota per Revisione", value=p_mod['nota_revisione'] if p_mod['nota_revisione'] else "")
                us = st.selectbox("Stato", ["Attivo", "Dimesso"], index=0 if p_mod['stato']=='Attivo' else 1)
                ud = st.text_area("Diagnosi (Statica)", p_mod['diagnosi'])
                if st.form_submit_button("Aggiorna"):
                    update("pazienti", {"nome_completo": un, "data_nascita": str(ud_n), "stato": us, "diagnosi": ud, "data_revisione": str(ud_rev), "nota_revisione": ud_nota_rev}, "id", int(p_mod['id']))
                    _log("Modifica Paziente", f"Aggiornato ID: {p_mod['id']}")
                    st.rerun()
    with t3:
        if st.session_state.user_role == 'admin':
            p_del = selettore_paziente_ricerca("Elimina definitivamente", "p_del_key", solo_attivi=False)
            if p_del is not None:
                st.error("Attenzione: irreversibile.")
                if st.button("CONFERMA ELIMINAZIONE TOTALE", type="primary"):
                    pid_del = int(p_del['id'])
                    delete_filter("schede_pazienti", {"paziente_id": pid_del})
                    delete_filter("storico_report", {"paziente_id": pid_del})
                    delete_filter("diario_clinico", {"paziente_id": pid_del})
                    delete("pazienti", "id", pid_del)
                    _log("Eliminazione Paziente", f"Cancellato: {p_del['nome_completo']}")
                    st.rerun()
        else: st.warning("Solo l'amministratore può eliminare definitivamente.")
    with t4:
        st.subheader("Ricerca per Patologia")
        search_query = st.text_input("🔎 Cerca Patologia:", "")
        if search_query:
            df_ric = query_df_raw("pazienti", select="nome_completo,data_nascita,diagnosi,stato", order="nome_completo")
            if not df_ric.empty:
                results = df_ric[df_ric['diagnosi'].str.contains(search_query, case=False, na=False)]
                if not results.empty:
                    st.success(f"Trovati {len(results)} pazienti.")
                    st.dataframe(results, use_container_width=True)
                else: st.warning("Nessun risultato.")
    with t5:
        st.subheader("📖 Diario Clinico & Follow-up")
        p_diario = selettore_paziente_ricerca("Seleziona Paziente per il Diario", "sel_diario_key")
        if p_diario is not None:
            with st.container(border=True):
                st.write(f"**Aggiungi Nota per {p_diario['nome_completo']}**")
                c_d, c_f = st.columns([1, 1])
                d_visita = c_d.date_input("Data Visita", date.today())
                try: fisio_list = query_df_raw("fisioterapisti", select="nome_completo")['nome_completo'].tolist()
                except: fisio_list = []
                sel_fisio = c_f.selectbox("Fisioterapista", [""] + fisio_list)
                nota_visita = st.text_area("Dettagli clinici / Evoluzione", height=100)
                if st.button("💾 Salva Nota nel Diario"):
                    if nota_visita and sel_fisio:
                        insert("diario_clinico", {"paziente_id": int(p_diario['id']), "data_visita": str(d_visita), "nota": nota_visita, "fisioterapista": sel_fisio})
                        _log("Nuova Nota Diario", f"Paziente: {p_diario['nome_completo']}")
                        st.success("Nota aggiunta!")
                        st.rerun()
                    else: st.warning("Compila Nota e seleziona Fisioterapista.")
            st.divider()
            st.write("#### 🕰️ Storico Visite")
            storico_note = query_df_filter("diario_clinico", "paziente_id", int(p_diario['id']), order="data_visita")
            if not storico_note.empty:
                storico_note = storico_note.sort_values("data_visita", ascending=False)
                for _, row_n in storico_note.iterrows():
                    fisio_label = row_n['fisioterapista'] if row_n['fisioterapista'] else "N/D"
                    with st.expander(f"📅 {row_n['data_visita']}  -  Dr. {fisio_label}"):
                        st.write(row_n['nota'])
                        if st.session_state.user_role == 'admin':
                            if st.button("Elimina nota", key=f"del_nota_{row_n['id']}"):
                                delete("diario_clinico", "id", int(row_n['id']))
                                _log("Eliminazione Nota", f"ID Nota: {row_n['id']}")
                                st.rerun()
            else: st.info("Il diario è vuoto.")

# =======================================================
# PAGINA 2B: TEAM
# =======================================================
elif scelta == "👨‍⚕️ Team Fisioterapisti":
    st.subheader("Gestione Team")
    c_ins, c_vis = st.columns([1, 2])
    with c_ins:
        with st.form("new_fisio"):
            st.write("**Nuovo Fisioterapista**")
            nf = st.text_input("Nome e Cognome")
            albo = st.text_input("N. Iscrizione Albo (Opzionale)")
            if st.form_submit_button("Aggiungi al Team"):
                insert("fisioterapisti", {"nome_completo": nf, "iscrizione_albo": albo})
                _log("Nuovo Fisio", f"Nome: {nf}")
                st.success("Aggiunto!")
                st.rerun()
    with c_vis:
        st.write("**Membri del Team**")
        df_fisio = query_df_raw("fisioterapisti")
        if not df_fisio.empty:
            for _, r in df_fisio.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"🧑‍⚕️ **{r['nome_completo']}**")
                    c2.write(f"Albo: {r['iscrizione_albo']}")
                    if st.session_state.user_role == 'admin':
                        if c3.button("🗑️", key=f"del_fisio_{r['id']}"):
                            delete("fisioterapisti", "id", int(r['id']))
                            _log("Eliminazione Fisio", f"ID: {r['id']}")
                            st.rerun()
        else: st.info("Nessun fisioterapista registrato.")

# =======================================================
# PAGINA 3: CATALOGO
# =======================================================
elif scelta == "🏋️ Catalogo Esercizi":
    t_v, t_a, t_d = st.tabs(["📚 Catalogo", "➕ Aggiungi Esercizio", "⚙️ Gestione Distretti"])
    try: lista_distretti = query_df_raw("distretti", select="nome", order="nome")['nome'].tolist()
    except: lista_distretti = ["Spalla", "Ginocchio", "Schiena"]
    with t_a:
        with st.form("es_new"):
            nome_es = st.text_input("Nome Esercizio")
            dist = st.selectbox("Distretto", lista_distretti)
            c1, c2, c3 = st.columns(3)
            s, r, rec = c1.text_input("Serie Std"), c2.text_input("Rip Std"), c3.text_input("Rec Std")
            desc = st.text_area("Descrizione")
            video_url = st.text_input("🎬 Link Video YouTube (opzionale)", placeholder="https://youtu.be/...")
            foto = st.file_uploader("Foto", type=['jpg', 'png'])
            if st.form_submit_button("Salva Esercizio"):
                foto_url = ""
                if foto:
                    foto_url = upload_foto(nome_es, foto.getvalue())
                insert("esercizi", {"nome": nome_es, "distretto": dist, "descrizione": desc, "foto_path": foto_url, "serie_std": s, "rip_std": r, "recupero": rec, "video_url": video_url or None})
                _log("Nuovo Esercizio", f"Nome: {nome_es}")
                st.success("Esercizio creato!")
    with t_v:
        col_filter, _ = st.columns([1, 3])
        with col_filter:
            selected_dist = st.selectbox("🔍 Filtra per Distretto", ["Tutti"] + lista_distretti)
        if selected_dist != "Tutti":
            df_es = query_df_filter("esercizi", "distretto", selected_dist, order="nome")
        else:
            df_es = query_df_raw("esercizi", order="nome")
        
        if st.session_state.edit_esercizio_id:
            es_id = st.session_state.edit_esercizio_id
            try:
                es_rows = query_df_filter("esercizi", "id", es_id)
                if es_rows.empty: raise ValueError
                es_data = es_rows.iloc[0]
                # --- Navigazione tra esercizi ---
                ids_list = [int(x) for x in df_es['id'].tolist()]
                es_id_int = int(es_id)
                try: curr_idx = ids_list.index(es_id_int)
                except ValueError: curr_idx = 0
                total = len(ids_list)
                nav_l, nav_info, nav_r = st.columns([1, 2, 1])
                if curr_idx > 0:
                    if nav_l.button("◀ Precedente", key="nav_prev_es"):
                        st.session_state.edit_esercizio_id = ids_list[curr_idx - 1]
                        st.rerun()
                nav_info.markdown(f"<p style='text-align:center;margin-top:8px'><b>{curr_idx+1} / {total}</b></p>", unsafe_allow_html=True)
                if curr_idx < total - 1:
                    if nav_r.button("Successivo ▶", key="nav_next_es"):
                        st.session_state.edit_esercizio_id = ids_list[curr_idx + 1]
                        st.rerun()
                st.markdown(f"### ✏️ Modifica: {es_data['nome']}")
                # --- Anteprima foto attuale + fotocamera ---
                col_foto_prev, col_form = st.columns([1, 2])
                with col_foto_prev:
                    foto_url_attuale = get_foto_url(es_data.get('foto_path'))
                    if foto_url_attuale:
                        st.image(foto_url_attuale, caption="📷 Foto attuale", use_container_width=True)
                    else:
                        st.info("🖼️ Nessuna foto associata.")
                    # Fotocamera posteriore (su mobile apre la cam dietro)
                    st.markdown("**📸 Scatta / Carica foto:**")
                    nuova_foto = st.file_uploader("Scegli o scatta foto", type=['jpg', 'png', 'jpeg'], key=f"foto_upload_{es_id}", label_visibility="collapsed")
                    if nuova_foto:
                        if st.button("✅ Usa questa foto", key=f"use_foto_{es_id}", type="primary"):
                            new_url = upload_foto(es_data['nome'], nuova_foto.getvalue())
                            update("esercizi", {"foto_path": new_url}, "id", es_id)
                            _log("Foto Caricata", f"Esercizio ID: {es_id}")
                            st.success("Foto aggiornata!")
                            st.rerun()
                    # Upload video
                    st.markdown("**🎬 Registra / Carica video:**")
                    nuovo_video = st.file_uploader("Scegli o registra video", type=['mp4', 'mov', 'avi'], key=f"video_upload_{es_id}", label_visibility="collapsed")
                    if nuovo_video:
                        if st.button("✅ Carica video", key=f"use_video_{es_id}", type="primary"):
                            video_filename = f"{es_data['nome'].replace(' ', '_')}_{es_id}.mp4"
                            sb = get_supabase()
                            sb.storage.from_("foto-esercizi").upload(
                                f"video/{video_filename}",
                                nuovo_video.getvalue(),
                                {"content-type": nuovo_video.type, "upsert": "true"}
                            )
                            video_public_url = sb.storage.from_("foto-esercizi").get_public_url(f"video/{video_filename}")
                            update("esercizi", {"video_url": video_public_url}, "id", es_id)
                            _log("Video Caricato", f"Esercizio ID: {es_id}")
                            st.success("Video caricato e QR code aggiornato!")
                            st.rerun()
                with st.form("edit_es_form"):
                    e_nome = st.text_input("Nome", es_data['nome'])
                    try: d_idx = lista_distretti.index(es_data['distretto'])
                    except: d_idx = 0
                    e_dist = st.selectbox("Distretto", lista_distretti, index=d_idx)
                    c1, c2, c3 = st.columns(3)
                    e_s = c1.text_input("Serie", es_data['serie_std'])
                    e_r = c2.text_input("Rip", es_data['rip_std'])
                    e_rec = c3.text_input("Rec", es_data['recupero'])
                    e_desc = st.text_area("Descrizione", es_data['descrizione'])
                    e_video = st.text_input("🎬 Link Video YouTube", value=es_data.get('video_url') or '', placeholder="https://youtu.be/...")
                    e_foto = st.file_uploader("🔄 Sostituisci Foto (opzionale)", type=['jpg', 'png'])
                    if st.form_submit_button("💾 Salva Modifiche"):
                        new_url = es_data['foto_path']
                        if e_foto:
                            new_url = upload_foto(e_nome, e_foto.getvalue())
                        update("esercizi", {"nome": e_nome, "distretto": e_dist, "descrizione": e_desc, "serie_std": e_s, "rip_std": e_r, "recupero": e_rec, "foto_path": new_url, "video_url": e_video or None}, "id", es_id)
                        _log("Modifica Esercizio", f"ID: {es_id}")
                        st.session_state.edit_esercizio_id = None
                        st.success("Aggiornato!")
                        st.rerun()
                if st.button("✖ Chiudi Modifica", key="close_edit_es"):
                    st.session_state.edit_esercizio_id = None
                    st.rerun()
                st.divider()
            except Exception: st.session_state.edit_esercizio_id = None

        if not df_es.empty:
            for _, row in df_es.iterrows():
                with st.expander(f"{row['nome']} ({row['distretto']})"):
                    c1, c2 = st.columns([1, 2])
                    foto_url = get_foto_url(row['foto_path'])
                    if foto_url: c1.image(foto_url, width=200)
                    else: c1.write("🖼️ [No Foto]")
                    c2.write(row['descrizione'])
                    col_btn_1, col_btn_2 = st.columns([1, 4])
                    if col_btn_1.button("✏️", key=f"edit_{row['id']}"):
                        st.session_state.edit_esercizio_id = row['id']
                        st.rerun()
                    if st.session_state.user_role == 'admin':
                        if col_btn_2.button("🗑️ Elimina", key=f"cat_{row['id']}", type="primary"):
                            delete("esercizi", "id", int(row['id']))
                            _log("Eliminazione Esercizio", f"ID: {row['id']}")
                            st.rerun()
        else: st.info("Nessun esercizio trovato.")
    with t_d:
        st.subheader("Gestione Categorie / Distretti")
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.form("add_dist"):
                new_dist = st.text_input("Nuovo Distretto")
                if st.form_submit_button("Aggiungi"):
                    if new_dist:
                        insert("distretti", {"nome": new_dist})
                        st.success("Aggiunto!")
                        st.rerun()
        with c2:
            st.write("Elenco Distretti:")
            for d_name in lista_distretti:
                col_name, col_del = st.columns([3, 1])
                col_name.write(f"- {d_name}")
                if st.session_state.user_role == 'admin':
                    if col_del.button("❌", key=f"del_d_{d_name}"):
                        sb = get_supabase()
                        sb.table("distretti").delete().eq("nome", d_name).execute()
                        st.rerun()

# =======================================================
# PAGINA 4: PROTOCOLLI
# =======================================================
elif scelta == "📋 Protocolli":
    st.header("Gestione Protocolli")
    t_c, t_g = st.tabs(["🆕 Crea Protocolli", "⚙️ Gestisci e Modifica"])
    with t_c:
        with st.form("prot_n"):
            np = st.text_input("Nome Protocollo")
            desc_p = st.text_area("Descrizione Protocollo")
            if st.form_submit_button("Crea"):
                insert("protocolli_info", {"nome_protocollo": np, "descrizione_protocollo": desc_p})
                _log("Nuovo Protocollo", f"Nome: {np}")
                st.success("Creato!")
    with t_g:
        prots = query_df_raw("protocolli_info")
        if not prots.empty:
            ps = st.selectbox("Seleziona Protocollo", prots['nome_protocollo'].tolist())
            pid = int(prots[prots['nome_protocollo'] == ps]['id'].values[0])
            with st.expander("✏️ Modifica Intestazione"):
                with st.form("edit_head"):
                    new_name = st.text_input("Nome", ps)
                    new_desc = st.text_area("Descrizione")
                    if st.form_submit_button("Aggiorna"):
                        update("protocolli_info", {"nome_protocollo": new_name, "descrizione_protocollo": new_desc}, "id", pid)
                        st.rerun()
            with st.expander("➕ Aggiungi Esercizio"):
                es_list = query_df_raw("esercizi", select="id,nome")
                es_sel = st.selectbox("Scegli Esercizio", es_list['nome'].tolist())
                if st.button("Aggiungi"):
                    eid = int(es_list[es_list['nome'] == es_sel]['id'].values[0])
                    pe_df = query_df_filter("protocolli_esercizi", "protocollo_id", pid, select="ordine")
                    new_ord = 1 if pe_df.empty else int(pe_df['ordine'].max()) + 1
                    insert("protocolli_esercizi", {"protocollo_id": pid, "esercizio_id": eid, "ordine": new_ord, "serie": "3", "rip": "10", "recupero": "60s"})
                    st.rerun()
            st.divider()
            df_pe = get_protocollo_esercizi(pid)
            if not df_pe.empty:
                for _, row in df_pe.iterrows():
                    with st.container(border=True):
                        c_img, c_dati = st.columns([1, 4])
                        with c_img:
                            foto_url = get_foto_url(row['foto_path'])
                            if foto_url: st.image(foto_url, use_container_width=True)
                            else: st.write("No Foto")
                        with c_dati:
                            st.markdown(f"**{row['nome']}**")
                            with st.form(f"row_edit_{row['id']}"):
                                c1, c2, c3, c4 = st.columns(4)
                                n_ord = c1.number_input("Ord", value=int(row['ordine']), key=f"o_{row['id']}")
                                n_ser = c2.text_input("Ser", value=row['serie'], key=f"s_{row['id']}")
                                n_rip = c3.text_input("Rip", value=row['rip'], key=f"r_{row['id']}")
                                n_rec = c4.text_input("Rec", value=row['recupero'], key=f"re_{row['id']}")
                                col_upd, col_del = st.columns([1, 1])
                                if col_upd.form_submit_button("Salva"):
                                    update("protocolli_esercizi", {"ordine": n_ord, "serie": n_ser, "rip": n_rip, "recupero": n_rec}, "id", int(row['id']))
                                    st.rerun()
                                if col_del.form_submit_button("Rimuovi"):
                                    delete("protocolli_esercizi", "id", int(row['id']))
                                    st.rerun()
            if st.session_state.user_role == 'admin':
                if st.button("💣 ELIMINA PROTOCOLLO", type="primary"):
                    delete_filter("protocolli_esercizi", {"protocollo_id": pid})
                    delete("protocolli_info", "id", pid)
                    _log("Eliminazione Protocollo", f"ID: {pid}")
                    st.rerun()

# =======================================================
# PAGINA 5: ASSEGNA A PAZIENTE
# =======================================================
elif scelta == "📝 Assegna a Paziente":
    paz = selettore_paziente_ricerca("Cerca Paziente", "ass_paz")
    if paz is not None:
        st.subheader(f"Scheda di {paz['nome_completo']}")
        t1, t2, t3 = st.tabs(["➕ Singolo", "👯 Copia", "📑 Protocollo"])
        try: r_date = datetime.strptime(paz['data_revisione'], '%Y-%m-%d').date()
        except: r_date = date.today()
        new_rev = st.date_input("📅 Data Prossima Revisione (Aggiorna per Alert)", value=r_date)
        if str(new_rev) != str(paz['data_revisione']):
            update("pazienti", {"data_revisione": str(new_rev)}, "id", int(paz['id']))
            st.toast("Data revisione aggiornata!")
            st.rerun()
        st.divider()
        with t1:
            col_in, col_riep = st.columns([2, 1])
            with col_riep:
                st.write("**Già in scheda:**")
                df_e = get_scheda_paziente(int(paz['id']))
                if not df_e.empty:
                    disp = df_e[['ordine','nome','serie','rip','recupero','note']].rename(columns={'ordine':'Pos','nome':'Esercizio'})
                    st.dataframe(disp, hide_index=True, use_container_width=True)
            with col_in:
                try: lista_distretti = query_df_raw("distretti", select="nome", order="nome")['nome'].tolist()
                except: lista_distretti = ["Tutti"]
                filter_dist = st.selectbox("Filtra Distretto", ["Tutti"] + lista_distretti)
                if filter_dist == "Tutti": esercizi = query_df_raw("esercizi", order="nome")
                else: esercizi = query_df_filter("esercizi", "distretto", filter_dist, order="nome")
                if not esercizi.empty:
                    es_sel = st.selectbox("Esercizio", esercizi['nome'].tolist())
                    d_es = esercizi[esercizi['nome']==es_sel].iloc[0]
                    foto_url = get_foto_url(d_es['foto_path'])
                    if foto_url: st.image(foto_url, width=150)
                    with st.form("ass_sing"):
                        c1, c2, c3, c4 = st.columns(4)
                        df_e2 = get_scheda_paziente(int(paz['id']))
                        ord_v = c1.number_input("Pos", 1, value=len(df_e2)+1)
                        s_v, r_v, rec_v = c2.text_input("Serie", d_es['serie_std']), c3.text_input("Rip", d_es['rip_std']), c4.text_input("Rec", d_es['recupero'])
                        note = st.text_area("Note")
                        if st.form_submit_button("Inserisci"):
                            insert("schede_pazienti", {"paziente_id": int(paz['id']), "esercizio_id": int(d_es['id']), "ordine": ord_v, "serie": s_v, "rip": r_v, "recupero": rec_v, "note": note})
                            st.rerun()
                else: st.warning("Nessun esercizio.")
        with t3:
            prots = query_df_raw("protocolli_info")
            if not prots.empty:
                ps = st.selectbox("Scegli Protocollo", prots['nome_protocollo'].tolist())
                pid = int(prots[prots['nome_protocollo'] == ps]['id'].values[0])
                anteprima_df = get_protocollo_esercizi(pid)
                if not anteprima_df.empty:
                    st.dataframe(anteprima_df[['nome','serie','rip']], hide_index=True)
                if st.button("Carica Protocollo su Paziente"):
                    es_p = query_df_filter("protocolli_esercizi", "protocollo_id", pid)
                    for _, r in es_p.iterrows():
                        insert("schede_pazienti", {"paziente_id": int(paz['id']), "esercizio_id": int(r['esercizio_id']), "ordine": int(r['ordine']), "serie": r['serie'], "rip": r['rip'], "recupero": r['recupero']})
                    st.success("Caricato!")
                    st.rerun()

# =======================================================
# PAGINA 6: REPORT
# =======================================================
elif scelta == "📑 Report & Storico":
    paz = selettore_paziente_ricerca("Visualizza Report", "rep_paz", solo_attivi=False)
    if paz is not None:
        col_mode, col_date = st.columns([1, 1])
        mode = col_mode.radio("Modalità", ["✏️ Modifica Scheda (Date Alert)", "🖨️ Genera PDF (Data Stampa)"], horizontal=True)
        rep_date = col_date.date_input("📅 Data del Documento PDF", date.today())
        st.divider()
        st.markdown(f"### 🏥 Scheda: {paz['nome_completo']}")
        st.markdown(f"**Diagnosi:** {paz['diagnosi']}")
        if mode.startswith("✏️"):
            st.info("Imposta qui sotto quando vuoi rivedere il paziente. Questa data fa scattare l'Alert in Home Page.")
            try: r_date = datetime.strptime(paz['data_revisione'], '%Y-%m-%d').date()
            except: r_date = date.today()
            c_alert_d, c_alert_n = st.columns([1, 2])
            new_rev = c_alert_d.date_input("📅 Data Prossima Revisione", value=r_date)
            new_nota_rev = c_alert_n.text_input("Nota per l'Alert (es. Controllo plantari)", value=paz['nota_revisione'] if paz['nota_revisione'] else "")
            if c_alert_n.button("💾 Aggiorna Scadenza e Nota"):
                update("pazienti", {"data_revisione": str(new_rev), "nota_revisione": new_nota_rev}, "id", int(paz['id']))
                st.toast("Alert Aggiornato!")
                st.rerun()
        st.divider()
        df_rep = get_report_esercizi(int(paz['id']))
        if mode.startswith("✏️"):
            for _, r in df_rep.iterrows():
                with st.container(border=True):
                    h1, h2 = st.columns([4, 1])
                    h1.subheader(f"{r['ordine']}. {r['nome']}")
                    new_o = h2.number_input("Pos", 1, value=int(r['ordine']), key=f"o_{r['id']}")
                    if new_o != r['ordine']:
                        update("schede_pazienti", {"ordine": new_o}, "id", int(r['id']))
                        st.rerun()
                    c1, c2 = st.columns([1, 2])
                    foto_url = get_foto_url(r['foto_path'])
                    if foto_url: c1.image(foto_url, width=200)
                    c2.write(f"**{r['serie']}x{r['rip']}** | Rec: {r['recupero']}")
                    c2.write(r['descrizione'])
                    if r['note']: st.warning(f"Note: {r['note']}")
                    if st.button("🗑️ Rimuovi", key=f"del_r_{r['id']}", type="primary"):
                        delete("schede_pazienti", "id", int(r['id']))
                        st.rerun()
        else:
            if not df_rep.empty:
                fisio_list = query_df_raw("fisioterapisti", select="nome_completo")['nome_completo'].tolist()
                nome_fisio = st.selectbox("Seleziona Fisioterapista per il Report:", [""] + fisio_list)
                if st.button("📄 SALVA REPORT DEFINITIVO IN PDF"):
                    if not nome_fisio: st.error("Seleziona un Fisioterapista!")
                    else:
                        nome_file, path_file = genera_pdf_fisico(paz, df_rep, rep_date, nome_fisio)
                        insert("storico_report", {"paziente_id": int(paz['id']), "data_creazione": str(rep_date), "nome_file": nome_file, "path_file": path_file, "fisioterapista": nome_fisio})
                        _log("Creazione Report PDF", f"Paziente: {paz['nome_completo']}")
                        st.success(f"PDF Salvato: {nome_file}")
                        st.rerun()
                for _, r in df_rep.iterrows():
                    with st.container(border=True):
                        col_img, col_txt = st.columns([1, 3])
                        with col_img:
                            foto_url = get_foto_url(r['foto_path'])
                            if foto_url: st.image(foto_url, use_container_width=True)
                            else: st.write("🖼️ [No Foto]")
                        with col_txt:
                            st.markdown(f"#### {r['ordine']}. {r['nome']}")
                            st.markdown(f"💪 **{r['serie']}** x **{r['rip']}** | ⏱️ **Rec:** {r['recupero']}")
                            st.markdown(f"_{r['descrizione']}_")
                            if r['note']: st.info(f"Nota: {r['note']}")
            else: st.info("Nessun esercizio.")
        st.divider()
        st.subheader("🗂️ Archivio Report PDF")
        storico_df = query_df_filter("storico_report", "paziente_id", int(paz['id']), order="data_creazione")
        if not storico_df.empty:
            storico_df = storico_df.sort_values("data_creazione", ascending=False)
            with st.container(border=True):
                for _, pdf_row in storico_df.iterrows():
                    c1, c2, c3 = st.columns([2, 3, 1])
                    c1.write(f"📅 {pdf_row['data_creazione']}")
                    c1.caption(f"Fisio: {pdf_row['fisioterapista'] if pdf_row['fisioterapista'] else 'N/D'}")
                    c2.write(f"📄 {pdf_row['nome_file']}")
                    full_path = os.path.join(PDF_DIR, os.path.basename(str(pdf_row['path_file'] or "")))
                    if os.path.exists(full_path):
                        with open(full_path, "rb") as f: c3.download_button("⬇️ Scarica", f, file_name=pdf_row['nome_file'], key=f"dl_{pdf_row['id']}")
                    else: c3.error("Perso")
                    st.divider()
        else: st.write("Nessun report in archivio.")

# =======================================================
# PAGINA 7: BACKUP & LOG
# =======================================================
elif scelta == "💾 Backup & Ripristino" and st.session_state.user_role == 'admin':
    st.header("Amministrazione Sistema")
    t_back, t_log = st.tabs(["💾 Backup", "🕵️ Log Attività"])
    with t_back:
        st.info("☁️ I dati sono ora su **Supabase**. Per esportarli vai su supabase.com → il tuo progetto → Table Editor → Export.")
    with t_log:
        st.subheader("Audit Log - Controllo Responsabilità")
        try:
            df_log = query_df_raw("log_attivita", order="data_ora")
            if not df_log.empty:
                df_log = df_log.sort_values("data_ora", ascending=False)
            st.dataframe(df_log, use_container_width=True)
        except: st.error("Log non disponibile.")
