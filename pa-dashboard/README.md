# 🏛️ PA Trasparenza — Dashboard Dipendenti Pubblici Italiani

Dashboard locale per esplorare dati pubblici su dipendenti e incarichi della Pubblica Amministrazione italiana.

## 📡 Fonti Dati (Pubbliche e Ufficiali)

| Fonte | Contenuto | URL |
|-------|-----------|-----|
| **dati.gov.it** | Dataset PA nazionali e locali | https://www.dati.gov.it |
| **OpenBDAP (MEF)** | Spesa pubblica e personale | https://bdap-opendata.mef.gov.it |
| **ANAC** | Incarichi, appalti, anticorruzione | https://dati.anticorruzione.it |

## 🚀 Installazione

### Requisiti
- **Python 3.8+** — https://python.org/downloads
- Connessione Internet (per interrogare le API pubbliche)

### Windows
1. Scarica e decomprimi la cartella
2. Doppio clic su `avvia_windows.bat`
3. Il browser si apre automaticamente su http://localhost:5050

### Mac / Linux
```bash
chmod +x avvia_mac_linux.sh
./avvia_mac_linux.sh
```

### Manuale
```bash
pip install -r requirements.txt
python app.py
```

## 🔍 Funzionalità

- **Ricerca libera** su tutte le fonti (es: "dirigenti comune di Roma", "retribuzioni insegnanti")
- **3 sezioni**: dati.gov.it / ANAC / OpenBDAP MEF
- **Aggiornamento automatico** ogni 5 minuti
- **Link diretti** ai dataset originali
- **Statistiche** sul numero di dataset disponibili per tema

## ⚠️ Note Legali

Tutti i dati provengono da fonti ufficiali italiane, pubblicamente accessibili ai sensi del:
- D.Lgs. 33/2013 (Trasparenza PA)
- D.Lgs. 97/2016 (FOIA italiano)
- Licenze aperte (CC-BY, IODL)

L'uso è consentito per finalità di ricerca, giornalismo e interesse pubblico.

## 🛑 Fermare l'app

Premi `CTRL+C` nel terminale.
