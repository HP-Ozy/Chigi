"""
# Copyright (C) 2026 osvaldo roscani
# Questo file è parte di Chigi.
# Licenza: GNU GPL v3 — vedi LICENSE per i dettagli.
"""

import re
import threading
import time
import webbrowser
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
HEADERS = {"User-Agent": "PA-Dashboard/4.0 (ricerca pubblica trasparenza)"}
cache_data  = {}
last_update = {}

# ─────────────────────────────────────────────────────────────
# SEDI TERRITORIALI
# ─────────────────────────────────────────────────────────────
SEDI = {
    "VALLE D'AOSTA":       ("Aosta",       "Piazza Chanoux 1, 11100 Aosta AO"),
    "PIEMONTE":            ("Torino",       "Via Bogino 9, 10123 Torino TO"),
    "LOMBARDIA":           ("Milano",       "Via Moscova 46, 20121 Milano MI"),
    "TRENTINO":            ("Trento",       "Piazza Dante 15, 38122 Trento TN"),
    "ALTO ADIGE":          ("Bolzano",      "Via Cassa di Risparmio 12, 39100 Bolzano BZ"),
    "VENETO":              ("Venezia",      "San Marco 2662, 30124 Venezia VE"),
    "FRIULI":              ("Trieste",      "Via Mazzini 2, 34121 Trieste TS"),
    "LIGURIA":             ("Genova",       "Via Roma 11, 16121 Genova GE"),
    "EMILIA":              ("Bologna",      "Piazza Maggiore 6, 40124 Bologna BO"),
    "TOSCANA":             ("Firenze",      "Via de' Ginori 10, 50123 Firenze FI"),
    "UMBRIA":              ("Perugia",      "Corso Vannucci 48, 06123 Perugia PG"),
    "MARCHE":              ("Ancona",       "Piazza Roma 2, 60121 Ancona AN"),
    "LAZIO":               ("Roma",         "Via di Campo Marzio 78, 00186 Roma RM"),
    "ABRUZZO":             ("L'Aquila",     "Via Garibaldi 5, 67100 L'Aquila AQ"),
    "MOLISE":              ("Campobasso",   "Piazza Vittorio Emanuele II 1, 86100 Campobasso CB"),
    "CAMPANIA":            ("Napoli",       "Via Santa Brigida 51, 80133 Napoli NA"),
    "PUGLIA":              ("Bari",         "Via Sparano 45, 70121 Bari BA"),
    "BASILICATA":          ("Potenza",      "Via Pretoria 16, 85100 Potenza PZ"),
    "CALABRIA":            ("Catanzaro",    "Corso Mazzini 11, 88100 Catanzaro CZ"),
    "SICILIA":             ("Palermo",      "Via Cavour 2, 90133 Palermo PA"),
    "SARDEGNA":            ("Cagliari",     "Via Roma 25, 09124 Cagliari CA"),
    "ESTERO":              ("Roma",         "Palazzo Montecitorio, Piazza di Monte Citorio 1, 00186 Roma RM"),
}

def lookup_sede(testo):
    t = (testo or "").upper()
    for k, (citta, addr) in SEDI.items():
        if k in t:
            return citta, addr
    return testo or "Roma", "Palazzo Montecitorio, Piazza di Monte Citorio 1, 00186 Roma RM"


# ─────────────────────────────────────────────────────────────
# COLORI PARTITO (per badge colorati)
# ─────────────────────────────────────────────────────────────
PARTY_COLORS = {
    "fratelli": ("#1a3a6b", "#4d8fff"),
    "pd":       ("#6b0f1a", "#ff6b6b"),
    "partito democratico": ("#6b0f1a", "#ff6b6b"),
    "lega":     ("#0d4e8a", "#63b3ed"),
    "salvini":  ("#0d4e8a", "#63b3ed"),
    "forza italia": ("#003087", "#90cdf4"),
    "berlusconi": ("#003087", "#90cdf4"),
    "movimento 5": ("#005f47", "#48bb78"),
    "stelle":   ("#005f47", "#48bb78"),
    "azione":   ("#6b2fa0", "#d69ae8"),
    "italia viva": ("#8b1a1a", "#fc8181"),
    "avs":      ("#14532d", "#86efac"),
    "alleanza verdi": ("#14532d", "#86efac"),
    "noi moderati": ("#1a4a2e", "#6ee7b7"),
    "misto":    ("#374151", "#9ca3af"),
}

def party_style(nome):
    n = (nome or "").lower()
    for k, (bg, fg) in PARTY_COLORS.items():
        if k in n:
            return f"background:{bg}22;border:1px solid {fg}55;color:{fg}"
    return "background:rgba(77,143,255,.12);border:1px solid rgba(77,143,255,.3);color:#4d8fff"


# ─────────────────────────────────────────────────────────────
# SPARQL HELPER
# ─────────────────────────────────────────────────────────────
def sparql_query(endpoint, query, timeout=35):
    try:
        r = requests.get(
            endpoint,
            params={"query": query, "format": "application/sparql-results+json"},
            headers={**HEADERS, "Accept": "application/sparql-results+json"},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("results", {}).get("bindings", [])
    except Exception as e:
        return {"__error__": str(e)}

def v(b, k):
    return (b.get(k) or {}).get("value", "") or ""


# ─────────────────────────────────────────────────────────────
# CAMERA DEI DEPUTATI  — dati.camera.it/sparql
# ─────────────────────────────────────────────────────────────
CAMERA_SPARQL = "https://dati.camera.it/sparql"

Q_DEPUTATI = """
PREFIX ocd:  <http://dati.camera.it/ocd/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dc:   <http://purl.org/dc/elements/1.1/>
PREFIX dct:  <http://purl.org/dc/terms/>
PREFIX bio:  <http://purl.org/vocab/bio/0.1/>

SELECT DISTINCT ?persona ?cognome ?nome ?foto ?dataNascita ?luogoNascita ?genere
                ?collegio ?nomeGruppo ?siglaGruppo
WHERE {
  ?persona ocd:rif_mandatoCamera ?mandato ;
           a foaf:Person ;
           foaf:surname  ?cognome ;
           foaf:firstName ?nome .
  ?mandato ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_19> .
  MINUS { ?mandato ocd:endDate ?fine. }
  OPTIONAL { ?persona foaf:depiction ?foto. }
  OPTIONAL { ?persona foaf:gender    ?genere. }
  OPTIONAL { ?persona bio:Birth ?b . ?b bio:date ?dataNascita . }
  OPTIONAL { ?persona ocd:luogoNascita ?luogoNascita. }
  OPTIONAL {
    ?mandato ocd:rif_elezione ?el .
    ?el dc:coverage ?collegio .
  }
  OPTIONAL {
    ?aderisce ocd:rif_mandatoCamera     ?mandato ;
              ocd:rif_gruppoParlamentare ?gruppo .
    MINUS { ?aderisce ocd:endDate ?fineAd. }
    ?gruppo dc:title ?nomeGruppo .
    OPTIONAL { ?gruppo dct:alternative ?siglaGruppo. }
  }
}
ORDER BY ?cognome ?nome
"""

def get_deputati():
    rows = sparql_query(CAMERA_SPARQL, Q_DEPUTATI)
    if isinstance(rows, dict):
        return {"error": f"Camera SPARQL: {rows['__error__']}", "data": []}
    seen, result = set(), []
    for r in rows:
        pid = v(r, "persona")
        if pid in seen: continue
        seen.add(pid)
        cognome  = v(r, "cognome")
        nome     = v(r, "nome")
        collegio = v(r, "collegio")
        citta, indirizzo = lookup_sede(collegio)
        genere   = v(r, "genere").lower()
        gruppo   = v(r, "nomeGruppo") or v(r, "siglaGruppo")
        result.append({
            "id":             pid.split("/")[-1],
            "nome":           nome,
            "cognome":        cognome,
            "nome_completo":  f"{cognome} {nome}".strip(),
            "circoscrizione": collegio,
            "citta":          citta,
            "indirizzo":      indirizzo,
            "partito":        gruppo,
            "sigla":          v(r, "siglaGruppo"),
            "nato_a":         v(r, "luogoNascita"),
            "data_nascita":   v(r, "dataNascita")[:10],
            "sesso":          genere,
            "uri":            f"https://www.camera.it/leg19/473?idLegislatura=19&tipopersona=deputato&id={pid.split('_')[0].split('/')[-1]}",
            "foto":           v(r, "foto"),
            "camera":         "Deputato" if genere in ("m","male") else "Deputata",
            "party_style":    party_style(gruppo),
        })
    return {"error": None, "data": result}


# ─────────────────────────────────────────────────────────────
# SENATO — 3 strategie in cascata
# ─────────────────────────────────────────────────────────────
SENATO_SPARQL = "https://dati.senato.it/sparql"

# Strategia 1: SPARQL Senato con join sul nome gruppo
Q_SENATORI_V1 = """
PREFIX osr:  <http://dati.senato.it/osr/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?senatore ?cognome ?nome ?dataNascita ?luogoNascita ?sesso
                ?regione ?nomeGruppo
WHERE {
  ?senatore a osr:Senatore ;
            foaf:lastName  ?cognome ;
            foaf:firstName ?nome .
  ?mandato osr:senatore    ?senatore ;
           osr:legislatura ?leg .
  FILTER(?leg = "19"^^xsd:integer || ?leg = 19 || str(?leg) = "19")
  MINUS { ?mandato osr:fine ?fine. }
  OPTIONAL { ?senatore osr:dataNascita   ?dataNascita. }
  OPTIONAL { ?senatore osr:luogoNascita  ?luogoNascita. }
  OPTIONAL { ?senatore osr:sesso         ?sesso. }
  OPTIONAL { ?senatore osr:collegioElezione ?regione. }
  OPTIONAL {
    ?app osr:senatore   ?senatore ;
         osr:legislatura ?legApp ;
         osr:gruppo      ?gruppoObj .
    FILTER(?legApp = "19"^^xsd:integer || ?legApp = 19 || str(?legApp) = "19")
    MINUS { ?app osr:fine ?fineApp. }
    ?gruppoObj osr:denominazione ?nomeGruppo .
  }
}
ORDER BY ?cognome ?nome
"""

# Strategia 2: SPARQL Senato senza filtro mandato aperto (più permissivo)
Q_SENATORI_V2 = """
PREFIX osr:  <http://dati.senato.it/osr/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT DISTINCT ?senatore ?cognome ?nome ?dataNascita ?luogoNascita ?sesso ?nomeGruppo
WHERE {
  ?senatore a osr:Senatore ;
            foaf:lastName  ?cognome ;
            foaf:firstName ?nome .
  ?mandato osr:senatore ?senatore .
  FILTER(CONTAINS(str(?mandato), "/19/"))
  OPTIONAL { ?senatore osr:dataNascita  ?dataNascita. }
  OPTIONAL { ?senatore osr:luogoNascita ?luogoNascita. }
  OPTIONAL { ?senatore osr:sesso        ?sesso. }
  OPTIONAL {
    ?app osr:senatore ?senatore .
    FILTER(CONTAINS(str(?app), "/19/"))
    MINUS { ?app osr:fine ?f. }
    ?app osr:gruppo ?go .
    ?go  osr:denominazione ?nomeGruppo .
  }
}
ORDER BY ?cognome ?nome
LIMIT 400
"""

# Strategia 3: Camera SPARQL ha anche i senatori nella XIX
Q_SENATORI_CAMERA = """
PREFIX ocd:  <http://dati.camera.it/ocd/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dc:   <http://purl.org/dc/elements/1.1/>
PREFIX dct:  <http://purl.org/dc/terms/>

SELECT DISTINCT ?persona ?cognome ?nome ?foto ?genere ?collegio ?nomeGruppo ?siglaGruppo
WHERE {
  ?persona ocd:rif_mandatoSenato ?mandato ;
           a foaf:Person ;
           foaf:surname  ?cognome ;
           foaf:firstName ?nome .
  ?mandato ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_19> .
  MINUS { ?mandato ocd:endDate ?fine. }
  OPTIONAL { ?persona foaf:depiction ?foto. }
  OPTIONAL { ?persona foaf:gender    ?genere. }
  OPTIONAL {
    ?mandato ocd:rif_elezione ?el .
    ?el dc:coverage ?collegio .
  }
  OPTIONAL {
    ?aderisce ocd:rif_mandatoSenato      ?mandato ;
              ocd:rif_gruppoParlamentare  ?gruppo .
    MINUS { ?aderisce ocd:endDate ?fineAd. }
    ?gruppo dc:title ?nomeGruppo .
    OPTIONAL { ?gruppo dct:alternative ?siglaGruppo. }
  }
}
ORDER BY ?cognome ?nome
"""

def _parse_senatori_rows(rows, source):
    seen, result = set(), []
    for r in rows:
        sid = v(r, "senatore") or v(r, "persona")
        if sid in seen: continue
        seen.add(sid)
        cognome = v(r, "cognome")
        nome    = v(r, "nome")
        regione = v(r, "regione") or v(r, "collegio") or ""
        citta, indirizzo = lookup_sede(regione)
        sesso   = v(r, "sesso").lower() or v(r, "genere").lower()
        gruppo  = v(r, "nomeGruppo") or v(r, "siglaGruppo") or ""
        sid_short = sid.split("/")[-1]
        result.append({
            "id":             sid_short,
            "nome":           nome,
            "cognome":        cognome,
            "nome_completo":  f"{cognome} {nome}".strip(),
            "circoscrizione": regione,
            "citta":          citta,
            "indirizzo":      indirizzo,
            "partito":        gruppo,
            "sigla":          v(r, "siglaGruppo") or "",
            "nato_a":         v(r, "luogoNascita"),
            "data_nascita":   v(r, "dataNascita")[:10],
            "sesso":          sesso,
            "uri":            f"https://www.senato.it/composizione/senatori/elenco-alfabetico/scheda-attivita?did={sid_short}",
            "foto":           v(r, "foto"),
            "camera":         "Senatore" if sesso in ("m","male","maschile") else "Senatrice",
            "party_style":    party_style(gruppo),
            "source":         source,
        })
    return result

def scrape_senatori_fallback():
    """Scarica elenco senatori direttamente dal sito del Senato (HTML)"""
    try:
        r = requests.get(
            "https://www.senato.it/leg/19/BGT/Schede/Sena/eLista.htm",
            headers=HEADERS, timeout=20
        )
        if r.status_code != 200:
            return []
        # cerca righe con nome/gruppo dalla pagina HTML del Senato
        html = r.text
        # pattern: cognome, nome — gruppo
        pattern = re.compile(
            r'scheda-attivita\?did=(\d+)[^>]*>([^<]+)</a>[^<]*<[^>]+>([^<]+)</[^>]+>',
            re.IGNORECASE
        )
        result = []
        seen = set()
        for m in pattern.finditer(html):
            did, nome_raw, gruppo = m.group(1), m.group(2).strip(), m.group(3).strip()
            if did in seen: continue
            seen.add(did)
            parti = nome_raw.split()
            cognome = parti[0] if parti else nome_raw
            nome = " ".join(parti[1:]) if len(parti) > 1 else ""
            citta, indirizzo = "Roma", "Palazzo Madama, Piazza Madama 11, 00186 Roma RM"
            result.append({
                "id": did, "nome": nome, "cognome": cognome,
                "nome_completo": nome_raw,
                "circoscrizione": "", "citta": citta, "indirizzo": indirizzo,
                "partito": gruppo, "sigla": "", "nato_a": "", "data_nascita": "",
                "sesso": "", "uri": f"https://www.senato.it/composizione/senatori/elenco-alfabetico/scheda-attivita?did={did}",
                "foto": "", "camera": "Senatore/Senatrice",
                "party_style": party_style(gruppo), "source": "scraping senato.it",
            })
        return result
    except Exception:
        return []

def get_senatori():
    # Strategia 1: SPARQL Senato v1
    rows = sparql_query(SENATO_SPARQL, Q_SENATORI_V1)
    if not isinstance(rows, dict) and len(rows) > 10:
        data = _parse_senatori_rows(rows, "dati.senato.it/sparql")
        if len(data) > 10:
            return {"error": None, "data": data}

    # Strategia 2: SPARQL Senato v2 (pattern URI)
    rows = sparql_query(SENATO_SPARQL, Q_SENATORI_V2)
    if not isinstance(rows, dict) and len(rows) > 10:
        data = _parse_senatori_rows(rows, "dati.senato.it/sparql v2")
        if len(data) > 10:
            return {"error": None, "data": data}

    # Strategia 3: Camera SPARQL (ha anche i mandati senato XIX)
    rows = sparql_query(CAMERA_SPARQL, Q_SENATORI_CAMERA)
    if not isinstance(rows, dict) and len(rows) > 10:
        data = _parse_senatori_rows(rows, "dati.camera.it/sparql (senatori)")
        if len(data) > 10:
            return {"error": None, "data": data}

    # Strategia 4: Scraping HTML senato.it
    data = scrape_senatori_fallback()
    if len(data) > 10:
        return {"error": None, "data": data}

    return {
        "error": "Nessuna fonte disponibile per i senatori. Verifica la connessione internet.",
        "data": []
    }


# ─────────────────────────────────────────────────────────────
# FONTI PA
# ─────────────────────────────────────────────────────────────
def fetch_json(url, params=None, timeout=12):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

DATI_GOV = "https://www.dati.gov.it/opendata/api/3/action"
ANAC_API = "https://dati.anticorruzione.it/opendata/api/3/action"
BDAP_API = "https://bdap-opendata.mef.gov.it/SpodCkanApi/api/3/action"

def get_dati_gov(query="dipendenti pubblici", rows=20):
    data = fetch_json(f"{DATI_GOV}/package_search", {"q":query,"rows":rows,"sort":"metadata_modified desc"})
    return [{"titolo":d.get("title","N/D"),"ente":(d.get("organization") or {}).get("title","N/D"),
             "aggiornato":(d.get("metadata_modified") or "")[:10],
             "url":f"https://www.dati.gov.it/opendata/dataset/{d.get('name','')}",
             "tag":[t.get("display_name","") for t in (d.get("tags") or [])][:4],
             "formato":[r.get("format","") for r in (d.get("resources") or [])][:3],
             "descrizione":""}
            for d in (data.get("result",{}).get("results") or [])]

def get_anac(query="incarichi", rows=15):
    data = fetch_json(f"{ANAC_API}/package_search", {"q":query,"rows":rows,"sort":"metadata_modified desc"})
    return [{"titolo":d.get("title","N/D"),"ente":"ANAC",
             "aggiornato":(d.get("metadata_modified") or "")[:10],
             "url":f"https://dati.anticorruzione.it/opendata/dataset/{d.get('name','')}",
             "tag":[],"formato":[],"descrizione":(d.get("notes") or "")[:120]}
            for d in (data.get("result",{}).get("results") or [])]

def get_bdap(query="personale", rows=15):
    data = fetch_json(f"{BDAP_API}/package_search", {"q":query,"rows":rows,"sort":"metadata_modified desc"})
    return [{"titolo":d.get("title","N/D"),"ente":"MEF / OpenBDAP",
             "aggiornato":(d.get("metadata_modified") or "")[:10],
             "url":f"https://bdap-opendata.mef.gov.it/SpodCkanApi/dataset/{d.get('name','')}",
             "tag":[],"formato":[],"descrizione":(d.get("notes") or "")[:120]}
            for d in (data.get("result",{}).get("results") or [])]

def get_stats():
    cats = {}
    for q in ["dipendenti pubblici","retribuzioni","incarichi","dirigenti"]:
        d = fetch_json(f"{DATI_GOV}/package_search",{"q":q,"rows":1})
        cats[q] = (d.get("result") or {}).get("count",0)
    return {
        "totale_dataset_dati_gov": (fetch_json(f"{DATI_GOV}/package_search",
            {"q":"pubblica amministrazione","rows":1}).get("result") or {}).get("count",0),
        "dataset_per_tema": cats,
        "ultima_verifica": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


# ─────────────────────────────────────────────────────────────
# CACHE / REFRESH
# ─────────────────────────────────────────────────────────────
def refresh_all():
    global cache_data, last_update
    print("🔄 Aggiornamento dati...")
    cache_data["deputati"] = get_deputati()
    cache_data["senatori"] = get_senatori()
    cache_data["dati_gov"] = get_dati_gov()
    cache_data["anac"]     = get_anac()
    cache_data["bdap"]     = get_bdap()
    cache_data["stats"]    = get_stats()
    last_update["ts"]      = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    nd = len((cache_data.get("deputati") or {}).get("data",[]))
    ns = len((cache_data.get("senatori") or {}).get("data",[]))
    de = (cache_data.get("deputati") or {}).get("error","")
    se = (cache_data.get("senatori") or {}).get("error","")
    print(f"✅ {last_update['ts']} | {nd} deputati{' ⚠'+de[:30] if de else ''} | {ns} senatori{' ⚠'+se[:30] if se else ''}")

def bg_worker():
    while True:
        refresh_all()
        time.sleep(300)


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────
@app.route("/api/deputati")
def api_deputati():
    q = request.args.get("q","").lower().strip()
    d = cache_data.get("deputati") or {"data":[],"error":None}
    data = d.get("data",[])
    if q:
        data = [x for x in data if q in x["nome_completo"].lower()
                or q in x["circoscrizione"].lower()
                or q in x["partito"].lower()
                or q in x["citta"].lower()]
    return jsonify({"data":data,"error":d.get("error"),"total":len(d.get("data",[]))})

@app.route("/api/senatori")
def api_senatori():
    q = request.args.get("q","").lower().strip()
    d = cache_data.get("senatori") or {"data":[],"error":None}
    data = d.get("data",[])
    if q:
        data = [x for x in data if q in x["nome_completo"].lower()
                or q in x["circoscrizione"].lower()
                or q in x["partito"].lower()
                or q in x["citta"].lower()]
    return jsonify({"data":data,"error":d.get("error"),"total":len(d.get("data",[]))})

@app.route("/api/dati-gov")
def api_dg():    return jsonify(cache_data.get("dati_gov",[]))
@app.route("/api/anac")
def api_an():    return jsonify(cache_data.get("anac",[]))
@app.route("/api/bdap")
def api_bd():    return jsonify(cache_data.get("bdap",[]))
@app.route("/api/stats")
def api_st():    return jsonify(cache_data.get("stats",{}))
@app.route("/api/last-update")
def api_lu():    return jsonify(last_update)

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    threading.Thread(target=refresh_all, daemon=True).start()
    return jsonify({"status":"avviato"})

@app.route("/api/search")
def api_search():
    q     = request.args.get("q","")
    fonte = request.args.get("fonte","dati.gov.it")
    if fonte == "anac":   return jsonify(get_anac(q))
    elif fonte == "bdap": return jsonify(get_bdap(q))
    else:                 return jsonify(get_dati_gov(q))

@app.route("/api/party-styles")
def api_party_styles():
    """Restituisce gli stili CSS per i partiti (usato dal frontend)"""
    partiti = set()
    for cat in ["deputati","senatori"]:
        for p in (cache_data.get(cat) or {}).get("data",[]):
            partiti.add(p.get("partito",""))
    return jsonify({p: party_style(p) for p in partiti if p})


# ─────────────────────────────────────────────────────────────
# FRONTEND
# ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PA Trasparenza — Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#07090f;--surface:#0d1120;--surface2:#131929;
  --border:#18213a;--border2:#1f2d4a;
  --accent:#00e5b0;--a2:#ff6b35;--a3:#4d8fff;--a4:#c77dff;--a5:#ffd60a;
  --text:#dde3f0;--muted:#3d506e;--muted2:#607090;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Syne',sans-serif;min-height:100vh;}

header{display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;
  border-bottom:1px solid var(--border);background:rgba(7,9,15,.97);
  position:sticky;top:0;z-index:200;backdrop-filter:blur(12px);}
.logo{display:flex;align-items:center;gap:.9rem;}
.logo-ico{width:38px;height:38px;background:linear-gradient(135deg,var(--accent),var(--a3));
  clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);
  display:grid;place-items:center;font-size:1rem;}
.logo h1{font-size:1rem;font-weight:800;letter-spacing:-.02em;}
.logo p{font-size:.65rem;color:var(--muted2);font-family:'DM Mono',monospace;margin-top:.1rem;}
.hdr-r{display:flex;align-items:center;gap:.7rem;}
.live-b{display:flex;align-items:center;gap:.4rem;background:rgba(0,229,176,.07);
  border:1px solid rgba(0,229,176,.22);padding:.28rem .75rem;border-radius:100px;
  font-family:'DM Mono',monospace;font-size:.65rem;color:var(--accent);}
.dot{width:5px;height:5px;background:var(--accent);border-radius:50%;animation:pulse 2s infinite;}
.btn{background:var(--surface);border:1px solid var(--border2);color:var(--text);
  padding:.38rem .9rem;border-radius:6px;font-family:'Syne',sans-serif;
  font-size:.75rem;font-weight:600;cursor:pointer;transition:all .2s;}
.btn:hover{border-color:var(--accent);color:var(--accent);}

main{max-width:1600px;margin:0 auto;padding:1.5rem 2rem;}

.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:.8rem;margin-bottom:1.4rem;}
.sc{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:.9rem 1.1rem;position:relative;overflow:hidden;animation:rise .4s ease both;}
.sc::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;}
.sc:nth-child(1)::after{background:var(--accent);}
.sc:nth-child(2)::after{background:var(--a4);}
.sc:nth-child(3)::after{background:var(--a3);}
.sc:nth-child(4)::after{background:var(--a2);}
.sc:nth-child(5)::after{background:var(--a5);}
.sc-l{font-size:.62rem;color:var(--muted2);font-family:'DM Mono',monospace;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.3rem;}
.sc-v{font-size:1.55rem;font-weight:800;letter-spacing:-.03em;}
.sc-s{font-size:.62rem;color:var(--muted);margin-top:.2rem;font-family:'DM Mono',monospace;}

.search{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:.8rem 1.1rem;display:flex;gap:.7rem;align-items:center;margin-bottom:1.1rem;}
.search input{flex:1;background:transparent;border:none;outline:none;color:var(--text);
  font-family:'DM Mono',monospace;font-size:.85rem;}
.search input::placeholder{color:var(--muted);}
.search select{background:var(--bg);border:1px solid var(--border);color:var(--text);
  padding:.32rem .65rem;border-radius:6px;font-family:'Syne',sans-serif;font-size:.75rem;outline:none;}
.btn-s{background:var(--accent);color:#000;border:none;padding:.42rem 1.2rem;
  border-radius:6px;font-weight:700;font-family:'Syne',sans-serif;cursor:pointer;
  font-size:.8rem;transition:opacity .2s;}
.btn-s:hover{opacity:.85;}

.tabs{display:flex;gap:.4rem;margin-bottom:1.1rem;flex-wrap:wrap;}
.tab{padding:.4rem 1rem;border-radius:6px;border:1px solid var(--border);background:transparent;
  color:var(--muted2);cursor:pointer;font-family:'Syne',sans-serif;font-size:.78rem;
  font-weight:600;transition:all .2s;}
.tab.active{background:var(--accent);color:#000;border-color:var(--accent);}
.tab.sen.active{background:var(--a4);border-color:var(--a4);color:#fff;}
.tab.pa.active{background:var(--a3);border-color:var(--a3);color:#fff;}
.tab:hover:not(.active){border-color:var(--muted2);color:var(--text);}

.tbl-w{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;}
table{width:100%;border-collapse:collapse;}
thead th{background:rgba(255,255,255,.025);padding:.75rem 1rem;text-align:left;
  font-family:'DM Mono',monospace;font-size:.64rem;color:var(--muted2);
  text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid var(--border);white-space:nowrap;}
tbody tr{border-bottom:1px solid rgba(24,33,58,.9);transition:background .12s;animation:rise .2s ease both;}
tbody tr:last-child{border-bottom:none;}
tbody tr:hover{background:rgba(255,255,255,.025);}
td{padding:.75rem 1rem;font-size:.82rem;vertical-align:middle;}

/* badge generici */
.bd{display:inline-block;padding:.18rem .55rem;border-radius:4px;
  font-family:'DM Mono',monospace;font-size:.64rem;white-space:nowrap;margin:.1rem;}
.bd-dep{background:rgba(0,229,176,.1);border:1px solid rgba(0,229,176,.25);color:var(--accent);}
.bd-sen{background:rgba(199,125,255,.1);border:1px solid rgba(199,125,255,.25);color:var(--a4);}
.bd-ent{background:rgba(255,107,53,.1);border:1px solid rgba(255,107,53,.25);color:var(--a2);}
.bd-tag{background:rgba(77,143,255,.08);border:1px solid rgba(77,143,255,.2);color:var(--a3);}
.bd-fmt{background:rgba(0,229,176,.07);border:1px solid rgba(0,229,176,.18);color:var(--accent);}

/* badge partito: stile dinamico via attributo style */
.bd-party{display:inline-block;padding:.2rem .6rem;border-radius:5px;
  font-family:'DM Mono',monospace;font-size:.68rem;font-weight:600;
  white-space:nowrap;letter-spacing:.02em;max-width:220px;
  overflow:hidden;text-overflow:ellipsis;}

.av{width:32px;height:32px;border-radius:50%;object-fit:cover;border:1px solid var(--border2);flex-shrink:0;}
.av-ph{width:32px;height:32px;border-radius:50%;background:var(--surface2);
  border:1px solid var(--border2);display:inline-grid;place-items:center;
  font-size:.75rem;color:var(--muted2);flex-shrink:0;font-weight:700;}
.nc{display:flex;align-items:center;gap:.65rem;}
.nm{font-weight:700;font-size:.86rem;letter-spacing:-.01em;}
.ns{font-size:.68rem;color:var(--muted2);font-family:'DM Mono',monospace;margin-top:.1rem;}
.addr{font-family:'DM Mono',monospace;font-size:.7rem;color:var(--muted2);line-height:1.5;}
.addr strong{color:var(--text);font-size:.76rem;display:block;}
.lnk{display:inline-block;color:var(--accent);text-decoration:none;
  font-family:'DM Mono',monospace;font-size:.68rem;
  border:1px solid rgba(0,229,176,.22);padding:.16rem .5rem;
  border-radius:4px;transition:all .2s;}
.lnk:hover{background:rgba(0,229,176,.08);}

.loading{text-align:center;padding:3rem;color:var(--muted);font-family:'DM Mono',monospace;font-size:.8rem;}
.spin{display:inline-block;width:20px;height:20px;border:2px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin-bottom:.7rem;}
.err{background:rgba(255,69,96,.07);border:1px solid rgba(255,69,96,.2);color:#ff8a9a;
  padding:.9rem 1.3rem;border-radius:8px;font-family:'DM Mono',monospace;font-size:.77rem;margin:1rem;line-height:1.7;}
.src-badge{font-family:'DM Mono',monospace;font-size:.6rem;color:var(--muted2);
  background:rgba(255,255,255,.04);border:1px solid var(--border);
  padding:.12rem .45rem;border-radius:3px;margin-left:.4rem;}
.foot{padding:.5rem 1rem;border-top:1px solid var(--border);
  font-family:'DM Mono',monospace;font-size:.66rem;color:var(--muted);
  display:flex;justify-content:space-between;align-items:center;}

@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes rise{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
@media(max-width:1100px){.stats{grid-template-columns:repeat(3,1fr);}}
@media(max-width:700px){.stats{grid-template-columns:1fr 1fr;}main{padding:1rem;}}
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-ico">🏛</div>
    <div>
      <h1>PA Trasparenza</h1>
      <p>Parlamentari italiani · Dipendenti pubblici · Dati ufficiali in tempo reale</p>
    </div>
  </div>
  <div class="hdr-r">
    <div class="live-b"><div class="dot"></div>LIVE</div>
    <span id="updTs" style="font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted2)"></span>
    <button class="btn" onclick="forceRefresh()">↻ Aggiorna ora</button>
  </div>
</header>

<main>
  <div class="stats">
    <div class="sc"><div class="sc-l">Deputati Camera</div><div class="sc-v" id="nDep">—</div><div class="sc-s">XIX Legislatura</div></div>
    <div class="sc"><div class="sc-l">Senatori</div><div class="sc-v" id="nSen">—</div><div class="sc-s">XIX Legislatura</div></div>
    <div class="sc"><div class="sc-l">Totale Parlamentari</div><div class="sc-v" id="nTot">—</div><div class="sc-s">Camera + Senato</div></div>
    <div class="sc"><div class="sc-l">Dataset PA Aperti</div><div class="sc-v" id="nDs">—</div><div class="sc-s">dati.gov.it</div></div>
    <div class="sc"><div class="sc-l">Ultimo Aggiorn.</div><div class="sc-v" style="font-size:.85rem;line-height:1.3" id="nTs">—</div><div class="sc-s">Auto ogni 5 min</div></div>
  </div>

  <div class="search">
    <span style="color:var(--muted);font-family:'DM Mono',monospace">⌕</span>
    <input id="sInput" type="text" placeholder="Cerca per nome, cognome, città, partito, circoscrizione..." />
    <select id="sScope">
      <option value="dep">Deputati (Camera)</option>
      <option value="sen">Senatori</option>
      <option value="dg">Dataset dati.gov.it</option>
      <option value="anac">ANAC</option>
      <option value="bdap">OpenBDAP (MEF)</option>
    </select>
    <button class="btn-s" onclick="doSearch()">Cerca</button>
  </div>

  <div class="tabs">
    <button class="tab active dep" onclick="showTab('dep')">🏛 Deputati</button>
    <button class="tab sen" onclick="showTab('sen')">⚖️ Senatori</button>
    <button class="tab pa" onclick="showTab('dg')">📂 Dati.gov.it</button>
    <button class="tab pa" onclick="showTab('anac')">🔍 ANAC</button>
    <button class="tab pa" onclick="showTab('bdap')">💶 OpenBDAP</button>
  </div>

  <div id="pDep"  class="tbl-w"><div class="loading"><div class="spin"></div><br>Connessione a dati.camera.it/sparql...</div></div>
  <div id="pSen"  class="tbl-w" style="display:none"><div class="loading"><div class="spin"></div><br>Connessione a dati.senato.it/sparql...</div></div>
  <div id="pDg"   class="tbl-w" style="display:none"><div class="loading"><div class="spin"></div><br>Caricamento da dati.gov.it...</div></div>
  <div id="pAnac" class="tbl-w" style="display:none"><div class="loading"><div class="spin"></div><br>Caricamento da ANAC...</div></div>
  <div id="pBdap" class="tbl-w" style="display:none"><div class="loading"><div class="spin"></div><br>Caricamento da OpenBDAP...</div></div>
</main>

<script>
const TABS=['dep','sen','dg','anac','bdap'];
const PANELS={dep:'pDep',sen:'pSen',dg:'pDg',anac:'pAnac',bdap:'pBdap'};
let activeTab='dep';

function showTab(n){
  activeTab=n;
  document.querySelectorAll('.tab').forEach((b,i)=>b.classList.toggle('active',TABS[i]===n));
  TABS.forEach(t=>{document.getElementById(PANELS[t]).style.display=t===n?'block':'none';});
}

function renderParl(resp, tipo){
  let top='';
  if(resp.error){
    top=`<div class="err">⚠ <strong>${resp.error}</strong><br>
      Il sistema ha provato automaticamente 4 fonti diverse. Premi <strong>Aggiorna ora</strong> tra qualche istante.</div>`;
    if(!(resp.data||[]).length) return top;
  }
  const data=resp.data||[];
  if(!data.length) return top+'<div class="loading">Nessun dato trovato</div>';

  const bc=tipo==='dep'?'bd-dep':'bd-sen';
  // raggruppa per fonte per mostrare il badge sorgente solo una volta
  const fonte = data[0]?.source || (tipo==='dep'?'dati.camera.it/sparql':'dati.senato.it/sparql');

  const rows=data.map(p=>{
    const ini=((p.nome||'')[0]||'')+((p.cognome||'')[0]||'');
    const foto=p.foto
      ?`<img class="av" src="${p.foto}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='inline-grid'">
        <span class="av-ph" style="display:none">${ini}</span>`
      :`<span class="av-ph">${ini}</span>`;
    const link=p.uri?`<a class="lnk" href="${p.uri}" target="_blank">Profilo →</a>`:'';
    const partyBadge=p.partito
      ?`<span class="bd-party" style="${p.party_style}" title="${p.partito}">${p.partito}</span>`
      :`<span style="color:var(--muted2);font-family:'DM Mono',monospace;font-size:.72rem">—</span>`;
    return `<tr>
      <td style="min-width:180px"><div class="nc">${foto}<div>
        <div class="nm">${p.cognome} ${p.nome}</div>
        <div class="ns">${p.nato_a?'🏙 '+p.nato_a:''} ${p.data_nascita?'· '+p.data_nascita:''}</div>
      </div></div></td>
      <td><span class="bd ${bc}">${p.camera}</span></td>
      <td style="min-width:200px">${partyBadge}</td>
      <td><div class="addr"><strong>${p.citta||p.circoscrizione||'—'}</strong>${p.circoscrizione||''}</div></td>
      <td style="min-width:220px"><div class="addr">${p.indirizzo||'—'}</div></td>
      <td>${link}</td>
    </tr>`;
  }).join('');

  return top+`<table>
    <thead><tr>
      <th>Parlamentare</th>
      <th>Carica</th>
      <th>🏳 Partito / Gruppo</th>
      <th>Città / Circ.</th>
      <th>Indirizzo Ufficio</th>
      <th>Link</th>
    </tr></thead>
    <tbody>${rows}</tbody></table>
    <div class="foot">
      <span>${data.length} parlamentari</span>
      <span>fonte: <span class="src-badge">${fonte}</span></span>
    </div>`;
}

function renderDs(data, tipo){
  if(!data.length) return '<div class="loading">Nessun dataset trovato</div>';
  const rows=data.map(d=>{
    const tags=(d.tag||[]).map(t=>`<span class="bd bd-tag">${t}</span>`).join('');
    const fmts=(d.formato||[]).filter(Boolean).map(f=>`<span class="bd bd-fmt">${f}</span>`).join('');
    return `<tr>
      <td style="max-width:260px;font-weight:600;font-size:.82rem">${d.titolo}</td>
      <td><span class="bd bd-ent">${d.ente}</span></td>
      <td style="font-family:'DM Mono',monospace;font-size:.7rem">${d.aggiornato||'—'}</td>
      <td>${tags}${d.descrizione?`<div style="font-size:.72rem;color:var(--muted2);margin-top:.25rem">${d.descrizione}</div>`:''}</td>
      ${tipo==='dg'?`<td>${fmts}</td>`:''}
      <td><a class="lnk" href="${d.url}" target="_blank">Apri →</a></td>
    </tr>`;
  }).join('');
  return `<table><thead><tr><th>Titolo</th><th>Ente</th><th>Aggiornato</th>
    <th>Info</th>${tipo==='dg'?'<th>Formato</th>':''}<th>Link</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <div class="foot"><span>${data.length} dataset trovati</span></div>`;
}

async function loadAll(){
  fetch('/api/deputati').then(r=>r.json()).then(d=>{
    document.getElementById('pDep').innerHTML=renderParl(d,'dep');
    document.getElementById('nDep').textContent=(d.data||[]).length||'—';
    updateTot();
  });
  fetch('/api/senatori').then(r=>r.json()).then(d=>{
    document.getElementById('pSen').innerHTML=renderParl(d,'sen');
    document.getElementById('nSen').textContent=(d.data||[]).length||'—';
    updateTot();
  });
  fetch('/api/stats').then(r=>r.json()).then(d=>{
    document.getElementById('nDs').textContent=(d.totale_dataset_dati_gov||0).toLocaleString('it-IT');
    document.getElementById('nTs').textContent=(d.ultima_verifica||'—').slice(0,16);
  });
  fetch('/api/dati-gov').then(r=>r.json()).then(d=>{document.getElementById('pDg').innerHTML=renderDs(d,'dg');});
  fetch('/api/anac').then(r=>r.json()).then(d=>{document.getElementById('pAnac').innerHTML=renderDs(d,'anac');});
  fetch('/api/bdap').then(r=>r.json()).then(d=>{document.getElementById('pBdap').innerHTML=renderDs(d,'bdap');});
  fetch('/api/last-update').then(r=>r.json()).then(d=>{
    if(d.ts) document.getElementById('updTs').textContent='Agg. '+d.ts;
  });
}
function updateTot(){
  const d=parseInt(document.getElementById('nDep').textContent)||0;
  const s=parseInt(document.getElementById('nSen').textContent)||0;
  if(d+s>0) document.getElementById('nTot').textContent=d+s;
}
async function doSearch(){
  const q=document.getElementById('sInput').value.trim();
  const sc=document.getElementById('sScope').value;
  if(!q) return;
  const panel=PANELS[sc]; showTab(sc);
  document.getElementById(panel).innerHTML='<div class="loading"><div class="spin"></div><br>Ricerca...</div>';
  if(sc==='dep'){
    fetch(`/api/deputati?q=${encodeURIComponent(q)}`).then(r=>r.json()).then(d=>{document.getElementById(panel).innerHTML=renderParl(d,'dep');});
  } else if(sc==='sen'){
    fetch(`/api/senatori?q=${encodeURIComponent(q)}`).then(r=>r.json()).then(d=>{document.getElementById(panel).innerHTML=renderParl(d,'sen');});
  } else {
    const fMap={dg:'dati.gov.it',anac:'anac',bdap:'bdap'};
    fetch(`/api/search?q=${encodeURIComponent(q)}&fonte=${fMap[sc]}`).then(r=>r.json()).then(d=>{document.getElementById(panel).innerHTML=renderDs(d,sc);});
  }
}
async function forceRefresh(){
  Object.values(PANELS).forEach(id=>{
    document.getElementById(id).innerHTML='<div class="loading"><div class="spin"></div><br>Aggiornamento...</div>';
  });
  await fetch('/api/refresh',{method:'POST'});
  setTimeout(loadAll,4500);
}
document.getElementById('sInput').addEventListener('keydown',e=>{if(e.key==='Enter')doSearch();});
loadAll();
setInterval(loadAll,300000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    threading.Thread(target=refresh_all, daemon=True).start()
    def _open():
        time.sleep(3)
        webbrowser.open("http://localhost:5050")
    threading.Thread(target=_open, daemon=True).start()
    threading.Thread(target=bg_worker, daemon=True).start()

    print("\n" + "="*60)
    print("  🏛️  PA Trasparenza Dashboard v4.0")
    print("="*60)
    print("  📡 Deputati  → dati.camera.it/sparql")
    print("  📡 Senatori  → 4 strategie (sparql × 2 + camera + scraping)")
    print("  📡 PA/Enti   → dati.gov.it · ANAC · OpenBDAP")
    print("  🏳  Partito  → colonna dedicata con badge colorati per partito")
    print("─"*60)
    print("  🌐  http://localhost:5050")
    print("  🛑  CTRL+C per fermare")
    print("="*60 + "\n")

    app.run(host="0.0.0.0", port=5050, debug=False, use_reloader=False)
