# -*- coding: utf-8 -*-
"""
Genera il PDF dello Stack Tecnologico di FisioManager Pro.
Eseguire: python genera_stack_pdf.py
"""
from fpdf import FPDF
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE_DIR, "StackTecnologico_FisioManager.pdf")

# Colori
TEAL = (0, 109, 119)
DARK = (51, 51, 51)
WHITE = (255, 255, 255)
LIGHT_BG = (245, 248, 250)
HEADER_BG = (0, 109, 119)
ROW_ALT = (232, 245, 243)


class StackPDF(FPDF):
    def header(self):
        logo = os.path.join(BASE_DIR, "Immagine1.png")
        if os.path.exists(logo):
            try:
                self.image(logo, 165, 8, 30)
            except:
                pass
        self.set_font("Arial", "B", 20)
        self.set_text_color(*TEAL)
        self.cell(0, 10, "FisioManager Pro", ln=True)
        self.set_font("Arial", "", 11)
        self.set_text_color(*DARK)
        self.cell(0, 6, "Stack Tecnologico Completo", ln=True)
        self.set_draw_color(*TEAL)
        self.set_line_width(0.6)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Pag. {self.page_no()}/{{nb}}", align="C")

    # ----- helpers -----
    def section_title(self, icon, title):
        if self.get_y() > 250:
            self.add_page()
        self.ln(4)
        self.set_font("Arial", "B", 14)
        self.set_text_color(*TEAL)
        self.cell(0, 8, f"  {icon}  {title}", ln=True)
        self.set_draw_color(*TEAL)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def table(self, headers, rows, col_widths=None):
        if col_widths is None:
            w = 190 / len(headers)
            col_widths = [w] * len(headers)
        # header row
        self.set_font("Arial", "B", 9)
        self.set_fill_color(*HEADER_BG)
        self.set_text_color(*WHITE)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, f" {h}", border=0, fill=True)
        self.ln()
        # data rows
        self.set_font("Arial", "", 9)
        self.set_text_color(*DARK)
        for idx, row in enumerate(rows):
            if self.get_y() > 270:
                self.add_page()
            if idx % 2 == 0:
                self.set_fill_color(*ROW_ALT)
            else:
                self.set_fill_color(*WHITE)
            max_h = 6
            # pre-calc multi-cell heights
            for i, cell in enumerate(row):
                nb = self.get_string_width(str(cell)) / (col_widths[i] - 2)
                if nb > 1:
                    max_h = max(max_h, 6 * (int(nb) + 1))
            y_before = self.get_y()
            x_start = self.get_x()
            for i, cell in enumerate(row):
                self.set_xy(x_start + sum(col_widths[:i]), y_before)
                # Draw fill rect
                self.rect(x_start + sum(col_widths[:i]), y_before, col_widths[i], max_h, "F")
                self.set_xy(x_start + sum(col_widths[:i]) + 1, y_before)
                self.multi_cell(col_widths[i] - 2, 6, str(cell), border=0)
            self.set_y(y_before + max_h)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Arial", "", 9)
        self.set_text_color(*DARK)
        x = self.get_x()
        self.cell(6, 5, chr(149))
        self.multi_cell(175, 5, text)
        if self.get_y() > 275:
            self.add_page()


def safe(t):
    """Encode per latin-1 (fpdf)."""
    try:
        return t.encode("latin-1", "replace").decode("latin-1")
    except:
        return str(t)


def main():
    pdf = StackPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── 1. Architettura Generale ──
    pdf.section_title("1.", "Architettura Generale")
    pdf.table(
        ["Livello", "Tecnologia"],
        [
            ["Tipo Applicazione", "Web App single-page, server-rendered"],
            ["Pattern", "Monolitico (frontend + backend in app.py)"],
            ["Deployment", "Locale (Windows LAN) + Cloud (Streamlit Cloud)"],
        ],
        [60, 130],
    )

    # ── 2. Linguaggio ──
    pdf.section_title("2.", "Linguaggio e Runtime")
    pdf.table(
        ["Componente", "Dettagli"],
        [
            ["Linguaggio", "Python"],
            ["Runtime", "CPython (installazione locale Windows)"],
        ],
        [60, 130],
    )

    # ── 3. Frontend / UI ──
    pdf.section_title("3.", "Frontend / UI Framework")
    pdf.table(
        ["Componente", "Dettagli"],
        [
            ["Framework UI", "Streamlit - framework Python per webapp interattive"],
            ["Tipografia", "Google Fonts (Montserrat, Open Sans)"],
            ["Stile", "CSS custom iniettato via st.markdown(unsafe_allow_html)"],
            ["Palette", "Primary #006D77, Secondary #83C5BE, BG #F8F9FA"],
            ["Grafici", "Altair - libreria dichiarativa (donut chart, bar chart)"],
        ],
        [45, 145],
    )

    # ── 4. Backend / Database ──
    pdf.section_title("4.", "Backend / Database")
    pdf.table(
        ["Componente", "Dettagli"],
        [
            ["Database Cloud", "Supabase (PostgreSQL gestito)"],
            ["Database Legacy", "SQLite (centro_fisioterapia.db, pre-migrazione)"],
            ["Query Layer", "Layer custom db_supabase.py con Supabase Python SDK"],
            ["JOIN", "In-memory con Pandas merge()"],
            ["Autenticazione DB", "Chiavi API Supabase (anon + service role) via secrets.toml"],
            ["Row Level Security", "Disabilitata su tutte le tabelle"],
        ],
        [45, 145],
    )

    # ── 5. Storage ──
    pdf.section_title("5.", "Storage e File")
    pdf.table(
        ["Componente", "Dettagli"],
        [
            ["Storage Immagini", "Supabase Storage - bucket foto-esercizi (pubblico)"],
            ["Storage Video", "Supabase Storage - sotto-cartella video/ nel bucket"],
            ["Storage PDF", "File system locale (cartella report_pdf/)"],
        ],
        [50, 140],
    )

    # ── 6. Librerie Python ──
    pdf.section_title("6.", "Librerie Python Principali")
    pdf.table(
        ["Libreria", "Uso"],
        [
            ["streamlit", "Framework web / UI"],
            ["pandas", "Manipolazione dati, DataFrame, merge"],
            ["altair", "Grafici interattivi (donut, barchart)"],
            ["fpdf", "Generazione PDF (report schede pazienti)"],
            ["Pillow (PIL)", "Manipolazione immagini (resize, convert RGB)"],
            ["supabase (supabase-py)", "Client API Supabase (DB + Storage)"],
            ["qrcode", "Generazione QR code (accesso app + video)"],
        ],
        [55, 135],
    )

    pdf.ln(2)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 6, "Librerie Standard Python utilizzate:", ln=True)
    for lib in [
        "os, sys - gestione filesystem e percorsi",
        "datetime, date, timedelta - gestione date",
        "tempfile - file temporanei per immagini PDF",
        "io, base64 - encoding QR code per embed HTML",
        "urllib.request - download immagini da URL per i PDF",
        "sqlite3 - usato nello script di migrazione",
        "tomllib - parsing del file secrets.toml (migrazione)",
        "pathlib - gestione path (migrazione)",
        "typing - type hints",
    ]:
        pdf.bullet(safe(lib))

    # ── 7. Autenticazione ──
    pdf.section_title("7.", "Autenticazione Applicativa")
    pdf.table(
        ["Componente", "Dettagli"],
        [
            ["Tipo", "Autenticazione locale/custom (dizionario Python)"],
            ["Utenti", "2 ruoli: admin (Direzione) e user (Fisioterapia)"],
            ["Sessione", "st.session_state di Streamlit"],
        ],
        [45, 145],
    )

    # ── 8. Schema DB ──
    pdf.section_title("8.", "Schema Database (10 tabelle PostgreSQL)")
    pdf.table(
        ["Tabella", "Descrizione"],
        [
            ["distretti", "Categorie di distretti corporei"],
            ["esercizi", "Catalogo esercizi (foto, video, parametri)"],
            ["pazienti", "Anagrafica pazienti"],
            ["fisioterapisti", "Team fisioterapisti"],
            ["diario_clinico", "Note cliniche per paziente"],
            ["schede_pazienti", "Esercizi assegnati ai pazienti"],
            ["protocolli_info", "Intestazioni protocolli"],
            ["protocolli_esercizi", "Esercizi nei protocolli"],
            ["storico_report", "Archivio PDF generati"],
            ["log_attivita", "Audit log delle azioni utente"],
        ],
        [50, 140],
    )

    # ── 9. Deploy ──
    pdf.section_title("9.", "Deploy e Infrastruttura")
    pdf.table(
        ["Componente", "Dettagli"],
        [
            ["Cloud Hosting", "Streamlit Cloud (fisiomanager-app-...streamlit.app)"],
            ["Hosting Locale", "Script batch START.bat - porta 8502, LAN 0.0.0.0"],
            ["Installazione", "Script batch istalla librerie.bat"],
            ["Migrazione", "Script Python migra_su_supabase.py (SQLite -> Supabase)"],
            ["Versionamento", "Git (.git/, .gitignore)"],
        ],
        [45, 145],
    )

    # ── 10. Documentazione ──
    pdf.section_title("10.", "Documentazione")
    pdf.table(
        ["Componente", "Dettagli"],
        [
            ["Manuale Utente", "ManualeUtente.pdf + ManualeUtente.docx"],
            ["Presentazione", "Presentazione_FisioManager_Pro.pdf"],
            ["Schema SQL", "supabase_schema.sql"],
        ],
        [50, 140],
    )

    # ── Riepilogo finale ──
    pdf.ln(6)
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_draw_color(*TEAL)
    y0 = pdf.get_y()
    pdf.rect(10, y0, 190, 30, "FD")
    pdf.set_xy(14, y0 + 3)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 6, "Riepilogo", ln=True)
    pdf.set_x(14)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(
        180,
        5,
        safe(
            "FisioManager Pro e' un'applicazione web monolitica scritta in Python con Streamlit come "
            "framework UI, Supabase (PostgreSQL) come database cloud con storage integrato per media, "
            "Pandas per la manipolazione dati, Altair per i grafici, FPDF + Pillow per la generazione "
            "PDF e QRCode per i codici QR. Deployata su Streamlit Cloud e utilizzabile in locale su "
            "Windows via rete LAN."
        ),
    )

    pdf.output(OUTPUT)
    print(f"\nPDF generato: {OUTPUT}")


if __name__ == "__main__":
    main()
