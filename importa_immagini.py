import sqlite3
import os
import shutil

# --- CONFIGURAZIONE ---
DB_NAME = 'centro_fisioterapia.db'
SOURCE_FOLDER = 'nuove_foto'  # Cartella dove metti le immagini da caricare
DEST_FOLDER = 'foto'          # Cartella dove l'app legge le immagini

# Assicuriamoci che le cartelle esistano
if not os.path.exists(SOURCE_FOLDER):
    os.makedirs(SOURCE_FOLDER)
    print(f"📁 Creata cartella '{SOURCE_FOLDER}'. Mettici dentro le immagini!")
    exit()

if not os.path.exists(DEST_FOLDER):
    os.makedirs(DEST_FOLDER)

def pulisci_nome_file(filename):
    """
    Rimuove l'estensione e pulisce il nome per il confronto.
    """
    name_without_ext = os.path.splitext(filename)[0]
    name_clean = name_without_ext.replace("-disegno", "").strip()
    return name_without_ext, name_clean

def importa_foto():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    files = os.listdir(SOURCE_FOLDER)
    print(f"🔍 Trovati {len(files)} file in '{SOURCE_FOLDER}'...")
    print("------------------------------------------------")
    
    count_importati = 0
    count_sostituiti = 0
    count_non_trovati = 0

    for filename in files:
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
            
        file_path_src = os.path.join(SOURCE_FOLDER, filename)
        
        # 1. Prepara i nomi per la ricerca
        nome_originale, nome_pulito = pulisci_nome_file(filename)
        
        # 2. Cerca l'esercizio nel DB
        c.execute("SELECT id, nome, foto_path FROM esercizi WHERE nome LIKE ? OR nome LIKE ?", (nome_originale, nome_pulito))
        result = c.fetchone()
        
        if result:
            es_id, es_nome, current_foto = result
            
            # Percorso dove andrà la nuova foto
            dest_path = os.path.join(DEST_FOLDER, filename)
            
            # 3. GESTIONE VECCHIA FOTO (PULIZIA)
            vecchia_rimossa = False
            if current_foto and os.path.exists(current_foto):
                # Se il file vecchio ha un nome/percorso diverso da quello nuovo
                # (es. era .png e ora è .jpg, oppure aveva un nome diverso)
                # lo cancelliamo per non lasciare spazzatura.
                if os.path.abspath(current_foto) != os.path.abspath(dest_path):
                    try:
                        os.remove(current_foto)
                        vecchia_rimossa = True
                    except Exception as e:
                        print(f"⚠️  Impossibile eliminare vecchio file: {e}")

            # 4. Copia la nuova foto
            try:
                shutil.copy2(file_path_src, dest_path)
                
                # 5. Aggiorna il DB
                c.execute("UPDATE esercizi SET foto_path = ? WHERE id = ?", (dest_path, es_id))
                conn.commit()
                
                if vecchia_rimossa:
                    print(f"♻️  SOSTITUITO (Vecchia cancellata): '{es_nome}'")
                    count_sostituiti += 1
                elif current_foto:
                    print(f"🔄 AGGIORNATO (Sovrascrittura): '{es_nome}'")
                    count_sostituiti += 1
                else:
                    print(f"✅ NUOVO ABBINAMENTO: '{es_nome}'")
                    count_importati += 1
                    
            except Exception as e:
                print(f"❌ Errore copia file per '{es_nome}': {e}")

        else:
            print(f"⚠️  Non trovato nel DB: '{nome_originale}'")
            count_non_trovati += 1

    conn.close()
    print("-" * 30)
    print(f"Riepilogo:")
    print(f"✅ Nuovi inserimenti: {count_importati}")
    print(f"♻️  Sostituzioni:      {count_sostituiti}")
    print(f"⚠️  Non trovati:       {count_non_trovati}")
    print("-" * 30)

if __name__ == "__main__":
    importa_foto()