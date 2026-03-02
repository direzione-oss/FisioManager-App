-- =====================================================
-- FisioManager Pro — Schema Supabase (PostgreSQL)
-- Incolla questo script nell'editor SQL di Supabase
-- Project Settings → SQL Editor → New Query → RUN
-- =====================================================

-- 1. DISTRETTI
CREATE TABLE IF NOT EXISTS distretti (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL
);

-- 2. ESERCIZI
CREATE TABLE IF NOT EXISTS esercizi (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT,
    distretto TEXT,
    patologia TEXT,
    descrizione TEXT,
    foto_path TEXT,
    serie_std TEXT,
    rip_std TEXT,
    recupero TEXT,
    tipo TEXT
);

-- 3. PAZIENTI
CREATE TABLE IF NOT EXISTS pazienti (
    id BIGSERIAL PRIMARY KEY,
    nome_completo TEXT,
    data_nascita DATE,
    diagnosi TEXT,
    stato TEXT DEFAULT 'Attivo',
    data_registrazione DATE,
    data_revisione DATE,
    nota_revisione TEXT DEFAULT ''
);

-- 4. FISIOTERAPISTI
CREATE TABLE IF NOT EXISTS fisioterapisti (
    id BIGSERIAL PRIMARY KEY,
    nome_completo TEXT,
    iscrizione_albo TEXT
);

-- 5. DIARIO CLINICO
CREATE TABLE IF NOT EXISTS diario_clinico (
    id BIGSERIAL PRIMARY KEY,
    paziente_id BIGINT REFERENCES pazienti(id),
    data_visita DATE,
    nota TEXT,
    fisioterapista TEXT DEFAULT ''
);

-- 6. SCHEDE PAZIENTI
CREATE TABLE IF NOT EXISTS schede_pazienti (
    id BIGSERIAL PRIMARY KEY,
    paziente_id BIGINT REFERENCES pazienti(id),
    esercizio_id BIGINT REFERENCES esercizi(id),
    ordine INTEGER DEFAULT 1,
    serie TEXT,
    rip TEXT,
    recupero TEXT,
    note TEXT
);

-- 7. PROTOCOLLI INFO
CREATE TABLE IF NOT EXISTS protocolli_info (
    id BIGSERIAL PRIMARY KEY,
    nome_protocollo TEXT,
    descrizione_protocollo TEXT
);

-- 8. PROTOCOLLI ESERCIZI
CREATE TABLE IF NOT EXISTS protocolli_esercizi (
    id BIGSERIAL PRIMARY KEY,
    protocollo_id BIGINT REFERENCES protocolli_info(id),
    esercizio_id BIGINT REFERENCES esercizi(id),
    ordine INTEGER,
    serie TEXT,
    rip TEXT,
    recupero TEXT,
    note TEXT
);

-- 9. STORICO REPORT
CREATE TABLE IF NOT EXISTS storico_report (
    id BIGSERIAL PRIMARY KEY,
    paziente_id BIGINT REFERENCES pazienti(id),
    data_creazione DATE,
    nome_file TEXT,
    path_file TEXT,
    fisioterapista TEXT DEFAULT ''
);

-- 10. LOG ATTIVITA
CREATE TABLE IF NOT EXISTS log_attivita (
    id BIGSERIAL PRIMARY KEY,
    utente TEXT,
    azione TEXT,
    dettagli TEXT,
    data_ora TIMESTAMP
);

-- =====================================================
-- DATI DEFAULT: Distretti standard
-- =====================================================
INSERT INTO distretti (nome)
SELECT nome FROM (VALUES
    ('Spalla'), ('Ginocchio'), ('Schiena'), ('Anca'),
    ('Cervicale'), ('Gomito'), ('Polso'), ('Caviglia'), ('Altro')
) AS t(nome)
WHERE NOT EXISTS (SELECT 1 FROM distretti LIMIT 1);

-- =====================================================
-- STORAGE: Crea il bucket per le foto
-- Esegui questo DOPO aver eseguito il blocco sopra
-- =====================================================
-- Vai su: Storage → New bucket
-- Nome: foto-esercizi
-- Public: SI (spunta "Public bucket")
-- =====================================================

-- Disabilita RLS su tutte le tabelle (per semplicità)
ALTER TABLE distretti DISABLE ROW LEVEL SECURITY;
ALTER TABLE esercizi DISABLE ROW LEVEL SECURITY;
ALTER TABLE pazienti DISABLE ROW LEVEL SECURITY;
ALTER TABLE fisioterapisti DISABLE ROW LEVEL SECURITY;
ALTER TABLE diario_clinico DISABLE ROW LEVEL SECURITY;
ALTER TABLE schede_pazienti DISABLE ROW LEVEL SECURITY;
ALTER TABLE protocolli_info DISABLE ROW LEVEL SECURITY;
ALTER TABLE protocolli_esercizi DISABLE ROW LEVEL SECURITY;
ALTER TABLE storico_report DISABLE ROW LEVEL SECURITY;
ALTER TABLE log_attivita DISABLE ROW LEVEL SECURITY;
