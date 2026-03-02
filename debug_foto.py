import sqlite3
import os

# --- CONFIGURAZIONE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'centro_fisioterapia.db')
FOTO_DIR = os.path.join(BASE_DIR, 'foto')

def normalizza(testo):
    """Pulisce il testo per il confronto (toglie maiuscole, estensioni, spazi extra)"""
    if not testo: return ""
    return testo.lower().replace("-", " ").replace("_", " ").replace("disegno", "").strip()

def run_debug():
    print(f"🕵️  AVVIO DIAGNOSTICA FOTO")
    print(f"📂 Cartella Foto attesa: {FOTO_DIR}")
    
    if not os.path.exists(FOTO_DIR):
        print("❌ ERRORE GRAVE: La cartella 'foto' non esiste!")
        return

    # 1. ELENCO FILE REALI
    files_reali = [f for f in os.listdir(FOTO_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    print(f"📸 Trovate {len(files_reali)} immagini fisiche nella cartella.")
    for f in files_reali:
        print(f"   -> File: {f}")
    
    print("-" * 40)

    # 2. ANALISI DATABASE
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    esercizi = c.execute("SELECT id, nome, foto_path FROM esercizi").fetchall()
    
    print(f"🏋️  Trovati {len(esercizi)} esercizi nel database.")
    
    count_riparati = 0
    
    for es_id, es_nome, es_path_db in esercizi:
        print(f"\n🔍 Controllo: '{es_nome}'")
        print(f"   [DB Attuale]: {es_path_db if es_path_db else 'NESSUNO'}")
        
        # Logica di ricerca
        nome_es_clean = normalizza(es_nome)
        file_trovato = None
        
        # Cerchiamo un match tra i file
        for f in files_reali:
            f_clean = normalizza(os.path.splitext(f)[0]) # Nome file senza estensione e pulito
            
            # Match lasco: se il nome del file è contenuto nel nome esercizio o viceversa
            if f_clean == nome_es_clean or f_clean in nome_es_clean or nome_es_clean in f_clean:
                file_trovato = f
                break
        
        if file_trovato:
            # Abbiamo trovato il file!
            nuovo_valore = file_trovato # Salviamo SOLO il nome file, es: "squat.jpg"
            
            if es_path_db != nuovo_valore:
                print(f"   ✅ TROVATO FILE CORRISPONDENTE: {file_trovato}")
                c.execute("UPDATE esercizi SET foto_path = ? WHERE id = ?", (nuovo_valore, es_id))
                print(f"   🛠️  DATABASE AGGIORNATO!")
                count_riparati += 1
            else:
                print(f"   🆗 Già corretto.")
        else:
            print(f"   ❌ NESSUN FILE CORRISPONDENTE TROVATO NELLA CARTELLA.")

    conn.commit()
    conn.close()
    
    print("\n" + "="*40)
    print(f"RAPPORTO FINALE: Riparati {count_riparati} collegamenti.")
    print("Premi INVIO per chiudere...")
    input()

if __name__ == "__main__":
    run_debug()