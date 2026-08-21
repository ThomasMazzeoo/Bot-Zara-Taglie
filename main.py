#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
SCRIPT DI MONITORAGGIO DISPONIBILITÀ PRODOTTO ZARA
============================================================

INSTALLAZIONE DIPENDENZE:
    pip install schedule curl_cffi requests

UTILIZZO:
    python main.py

============================================================
"""

import time
import random
import json
import re
import platform
import sys
import os
from datetime import datetime

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    print("[ERRORE] Libreria curl_cffi non installata!")
    print("Esegui: pip install curl_cffi")
    sys.exit(1)

try:
    import requests as http_requests
except ImportError:
    print("[ERRORE] Libreria requests non installata!")
    print("Esegui: pip install requests")
    sys.exit(1)

try:
    import schedule
except ImportError:
    print("[ERRORE] Libreria schedule non installata!")
    print("Esegui: pip install schedule")
    sys.exit(1)

# ============================================================
# ⚙️ CONFIGURAZIONE GLOBALE
# ============================================================

INTERVALLO_MINUTI = 10
RITARDO_CASUALE_MAX = 5
BROWSER_IMPERSONATE = "chrome120"
NOTIFICA_SONORA_ATTIVA = False  # 🔕 Suono disattivato
MOSTRA_RISPOSTA_COMPLETA = False
COOKIES = "itxGeoData=IT|it|EUR|10704|40.0|9.0|0|0|0|0|"
CONFIG_FILE = "zara_monitor_config.json"
PRODOTTI_FILE = "prodotti.json"
STORE_ID = "10704"

# ============================================================
# 📱 CONFIGURAZIONE TELEGRAM (salvata nel file config)
# ============================================================

telegram_config = {
    "bot_token": "",
    "chat_id": "",
    "attivo": True
}

# ============================================================
# 📦 LISTA PRODOTTI
# ============================================================

prodotti_monitorati = {}

# ============================================================
# 🌍 HEADERS
# ============================================================

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.zara.com/it/",
    "Origin": "https://www.zara.com",
    "Cache-Control": "no-cache",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


# ============================================================
# 🍪 COOKIE
# ============================================================

def parse_cookies(cookie_string):
    """Parse cookie string."""
    cookies = {}
    cookie_string = cookie_string.strip()

    if not cookie_string:
        return cookies

    cookie_string = cookie_string.replace('\n', '; ').replace('\r', '')

    for item in cookie_string.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()

    return cookies


# ============================================================
# 🔗 URL E API ZARA
# ============================================================

def estrai_seo_product_id(url):
    """
    Estrae il seoProductId dall'URL della pagina prodotto Zara.
    Es: https://www.zara.com/it/it/bomber-p00993401.html → 00993401
    """
    url = url.strip()
    match = re.search(r'-p(\d{8})\.html', url)
    if match:
        return match.group(1)
    return None


def estrai_color_product_id(url):
    """
    Estrae il colorProductId dal parametro v1 dell'URL.
    Es: ?v1=503986634 → 503986634
    """
    match = re.search(r'[?&]v1=(\d+)', url)
    if match:
        return int(match.group(1))
    return None


def fetch_product_details(seo_product_id):
    """
    Chiama l'API Detail di Zara per ottenere tutti i dettagli del prodotto.
    Ritorna: {
        "nome": str,
        "seo_product_id": str,
        "colori": [
            {
                "nome": str,
                "product_id": int,
                "color_id": str,
                "taglie": [
                    {"nome": str, "sku": int, "id": int, "prezzo": int, ...}
                ]
            }
        ]
    }
    Oppure None in caso di errore.
    """
    url = f"https://www.zara.com/itxrest/2/catalog/store/{STORE_ID}/product/{seo_product_id}?locale=it_IT"

    try:
        session = curl_requests.Session()
        response = session.get(
            url,
            impersonate=BROWSER_IMPERSONATE,
            headers=HEADERS,
            cookies=parse_cookies(COOKIES),
            timeout=30
        )

        if response.status_code != 200:
            print(f"    ❌ Errore API Detail: HTTP {response.status_code}")
            return None

        data = response.json()
        result = {
            "nome": data.get("name", "Sconosciuto"),
            "seo_product_id": seo_product_id,
            "colori": []
        }

        for color in data.get("detail", {}).get("colors", []):
            color_info = {
                "nome": color.get("name", "?"),
                "product_id": color.get("productId"),
                "color_id": color.get("id", ""),
                "taglie": []
            }

            for size in color.get("sizes", []):
                color_info["taglie"].append({
                    "nome": size.get("name", "?"),
                    "sku": size.get("sku"),
                    "id": size.get("id"),
                    "prezzo": size.get("price"),
                    "prezzo_originale": size.get("originalPrice"),
                })

            result["colori"].append(color_info)

        return result

    except Exception as e:
        print(f"    ❌ Errore fetch dettagli: {e}")
        return None


def build_sku_taglia_map(product_details, color_product_id=None):
    """
    Costruisce la mappa {sku_str: nome_taglia} dai dettagli prodotto.
    Se color_product_id è specificato, usa solo quel colore.
    Altrimenti usa il primo colore disponibile.
    """
    if not product_details or not product_details.get("colori"):
        return {}

    # Trova il colore giusto
    target_color = None
    if color_product_id:
        for color in product_details["colori"]:
            if color["product_id"] == color_product_id:
                target_color = color
                break

    # Fallback al primo colore
    if not target_color:
        target_color = product_details["colori"][0]

    # Costruisci la mappa
    sku_map = {}
    for taglia in target_color.get("taglie", []):
        sku_map[str(taglia["sku"])] = taglia["nome"]

    return sku_map


def get_availability_url(color_product_id):
    """Costruisce l'URL dell'API availability per un colore specifico."""
    return f"https://www.zara.com/itxrest/1/catalog/store/{STORE_ID}/product/id/{color_product_id}/availability"


def valida_url_zara(url):
    """Verifica che sia un URL Zara valido."""
    if not url:
        return False
    url = url.strip().lower()
    return url.startswith("https://www.zara.com/") or url.startswith("http://www.zara.com/")


# ============================================================
# 💾 SALVATAGGIO E CARICAMENTO CONFIGURAZIONE
# ============================================================

def salva_configurazione():
    """Salva prodotti e configurazione Telegram nei rispettivi file."""
    global prodotti_monitorati, telegram_config

    try:
        # Salva Telegram config
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"telegram": telegram_config}, f, indent=4, ensure_ascii=False)
            
        # Salva prodotti separatamente
        with open(PRODOTTI_FILE, 'w', encoding='utf-8') as f:
            json.dump(prodotti_monitorati, f, indent=4, ensure_ascii=False)
            
        print(f"    💾 Configurazione salvata!")
        return True
    except Exception as e:
        print(f"    [!] Errore salvataggio: {e}")
        return False


def migra_prodotto_vecchio(info):
    """
    Migra un prodotto dal vecchio formato (con ha_xs e url API)
    al nuovo formato (con seo_product_id, color_product_id, sku_taglia_map).
    Ritorna il prodotto aggiornato.
    """
    # Se ha già sku_taglia_map, è già migrato
    if "sku_taglia_map" in info and info["sku_taglia_map"]:
        return info

    print(f"    🔄 Migrazione: {info.get('nome', '?')}...")

    # Migra vecchio formato taglia singola
    if 'taglia' in info and 'taglie' not in info:
        info['taglie'] = [info['taglia']]
        del info['taglia']

    # Estrai seo_product_id dall'URL pagina
    url_pagina = info.get('url_pagina', '')
    seo_id = estrai_seo_product_id(url_pagina)

    if not seo_id:
        # Prova dall'URL API vecchio
        old_url = info.get('url', '')
        match = re.search(r'/product/id/(\d+)/availability', old_url)
        if match:
            old_product_id = match.group(1)
            # L'old_product_id è il colorProductId, non il seoProductId
            info['color_product_id'] = int(old_product_id)
            print(f"    ⚠️  Impossibile estrarre seoProductId, prodotto parzialmente migrato")
            info['sku_taglia_map'] = {}
            return info

    info['seo_product_id'] = seo_id

    # Estrai color_product_id dal v1 dell'URL pagina o dall'URL API
    color_pid = estrai_color_product_id(url_pagina)
    if not color_pid:
        old_url = info.get('url', '')
        match = re.search(r'/product/id/(\d+)/availability', old_url)
        if match:
            color_pid = int(match.group(1))

    # Scarica i dettagli dal API Detail per costruire la mappa SKU→taglia
    details = fetch_product_details(seo_id)
    if details:
        info['nome'] = details['nome']  # Aggiorna nome dal API

        # Trova il colore corretto
        if color_pid:
            info['color_product_id'] = color_pid
            # Verifica se il color_pid corrisponde a uno dei colori nel detail
            found = False
            for color in details['colori']:
                if color['product_id'] == color_pid:
                    info['color_name'] = color['nome']
                    found = True
                    break
            if not found:
                # Il color_pid potrebbe essere un altro ID per lo stesso colore
                # Usa il primo colore disponibile e aggiorna il color_product_id
                if details['colori']:
                    first = details['colori'][0]
                    info['color_product_id'] = first['product_id']
                    info['color_name'] = first['nome']
                    print(f"    ⚠️  Colore {color_pid} non trovato nel detail, uso {first['nome']}")
        else:
            # Usa il primo colore
            if details['colori']:
                first = details['colori'][0]
                info['color_product_id'] = first['product_id']
                info['color_name'] = first['nome']

        # Costruisci mappa SKU→taglia
        sku_map = build_sku_taglia_map(details, info.get('color_product_id'))
        info['sku_taglia_map'] = sku_map

        # Verifica che le taglie selezionate siano ancora valide
        taglie_disponibili = list(sku_map.values())
        taglie_vecchie = info.get('taglie', [])
        taglie_valide = [t for t in taglie_vecchie if t in taglie_disponibili]
        if taglie_valide != taglie_vecchie:
            info['taglie'] = taglie_valide if taglie_valide else taglie_disponibili
            print(f"    ⚠️  Taglie aggiornate: {', '.join(info['taglie'])}")

        print(f"    ✅ Migrato! Colore: {info.get('color_name', '?')}, Taglie: {', '.join(taglie_disponibili)}")
    else:
        info['sku_taglia_map'] = {}
        print(f"    ⚠️  Migrazione parziale: impossibile contattare API Detail")

    # Rimuovi campi obsoleti
    info.pop('ha_xs', None)
    info.pop('url', None)

    return info


def carica_configurazione():
    """Carica prodotti e configurazione Telegram."""
    global prodotti_monitorati, telegram_config

    # 1. Carica Telegram config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_completa = json.load(f)
            if "telegram" in config_completa:
                telegram_config.update(config_completa["telegram"])
            
            # Retrocompatibilità: se i prodotti sono ancora in CONFIG_FILE e PRODOTTI_FILE non esiste
            if not os.path.exists(PRODOTTI_FILE):
                if "prodotti" in config_completa:
                    prodotti_monitorati = config_completa["prodotti"]
                else:
                    prodotti_monitorati = {k: v for k, v in config_completa.items() if k.startswith("prod_")}
        except Exception as e:
            print(f"    [!] Errore caricamento config: {e}")

    # Sovrascrivi con variabili d'ambiente (per GitHub Actions)
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if env_token:
        telegram_config["bot_token"] = env_token
    if env_chat_id:
        telegram_config["chat_id"] = env_chat_id

    if telegram_config.get("bot_token"):
        print(f"    📱 Telegram: configurazione caricata!")

    # 2. Carica Prodotti
    if os.path.exists(PRODOTTI_FILE):
        try:
            with open(PRODOTTI_FILE, 'r', encoding='utf-8') as f:
                prodotti_monitorati = json.load(f)
        except Exception as e:
            print(f"    [!] Errore caricamento prodotti: {e}")

    # Migra prodotti vecchi al nuovo formato
    migrato = False
    for prod_id, info in prodotti_monitorati.items():
        if "sku_taglia_map" not in info or not info["sku_taglia_map"]:
            prodotti_monitorati[prod_id] = migra_prodotto_vecchio(info)
            migrato = True

    # Se abbiamo dovuto migrare o dividere i file per la prima volta, salviamo
    if migrato or (os.path.exists(CONFIG_FILE) and not os.path.exists(PRODOTTI_FILE) and prodotti_monitorati):
        print("    💾 Salvataggio configurazione aggiornata...")
        salva_configurazione()

    print(f"    📂 Caricati {len(prodotti_monitorati)} prodotti")
    return True


# ============================================================
# 📱 FUNZIONI TELEGRAM
# ============================================================

def verifica_configurazione_telegram():
    """Verifica se Telegram è configurato."""
    return bool(telegram_config.get("bot_token") and telegram_config.get("chat_id"))


def invia_messaggio_telegram(messaggio, parse_mode="HTML"):
    """Invia messaggio Telegram."""
    if not telegram_config.get("attivo", True) or not verifica_configurazione_telegram():
        return False

    url = f"https://api.telegram.org/bot{telegram_config['bot_token']}/sendMessage"

    payload = {
        "chat_id": telegram_config["chat_id"],
        "text": messaggio,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    try:
        response = http_requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            print("    📱 Notifica Telegram inviata!")
            return True
        else:
            print(f"    ⚠️ Errore Telegram: {response.status_code}")
            return False
    except Exception as e:
        print(f"    ⚠️ Errore Telegram: {e}")
        return False


def invia_notifica_disponibile_telegram(nome_prodotto, taglie_disponibili, url_prodotto_pagina):
    """Invia notifica Telegram con link diretto al prodotto."""

    taglie_str = ", ".join(taglie_disponibili)

    link_html = f"\n\n🔗 <a href='{url_prodotto_pagina}'>APRI PRODOTTO SU ZARA</a>" if url_prodotto_pagina else ""

    messaggio = f"""
🚨🚨🚨 <b>PRODOTTO DISPONIBILE!</b> 🚨🚨🚨

📦 <b>{nome_prodotto}</b>

👕 Taglie: <b>{taglie_str}</b>

⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M:%S')}
{link_html}

🏃‍♂️ <b>Affrettati prima che finisca!</b>
"""

    return invia_messaggio_telegram(messaggio)


def invia_notifica_avvio_telegram():
    """Notifica avvio monitoraggio."""

    attivi = sum(1 for p in prodotti_monitorati.values() if p.get('attivo', True))
    tot_taglie = sum(
        len(info.get('taglie', []))
        for info in prodotti_monitorati.values()
        if info.get('attivo', True)
    )

    lista_prodotti = ""
    for info in prodotti_monitorati.values():
        if info.get('attivo', True):
            taglie = info.get('taglie', [])
            if isinstance(taglie, str):
                taglie = [taglie]
            colore = info.get('color_name', '')
            colore_str = f" [{colore}]" if colore else ""
            lista_prodotti += f"\n• {info['nome']}{colore_str} ({', '.join(taglie)})"

    messaggio = f"""
🚀 <b>Monitoraggio Zara Avviato!</b>

📦 Prodotti: <b>{attivi}</b>
👕 Taglie totali: <b>{tot_taglie}</b>
⏰ Controllo ogni: <b>{INTERVALLO_MINUTI} min</b>

<b>Prodotti monitorati:</b>{lista_prodotti}

Ti avviserò quando qualcosa sarà disponibile! 🔔
"""

    return invia_messaggio_telegram(messaggio)


def test_telegram():
    """Test notifica Telegram."""

    if not verifica_configurazione_telegram():
        print("\n    ⚠️ Telegram non configurato!")
        return False

    messaggio = f"""
✅ <b>Test Zara Monitor</b>

La configurazione Telegram funziona!

⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🔗 <a href='https://www.zara.com/it/'>Apri Zara</a>
"""

    print("\n    📱 Invio test...")
    result = invia_messaggio_telegram(messaggio)

    if result:
        print("    ✅ Test riuscito!")
    else:
        print("    ❌ Test fallito.")

    return result


def configura_telegram():
    """Configura Telegram interattivamente."""
    global telegram_config

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    📱 CONFIGURAZIONE TELEGRAM                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  1. Cerca @BotFather su Telegram → /newbot → copia TOKEN            ║
║  2. Cerca @userinfobot → /start → copia il tuo ID                   ║
║  3. IMPORTANTE: Cerca il tuo bot e invia /start                     ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Mostra stato attuale
    token_display = "***" + telegram_config["bot_token"][-10:] if telegram_config.get(
        "bot_token") else "Non configurato"
    chat_display = telegram_config.get("chat_id") if telegram_config.get("chat_id") else "Non configurato"

    print(f"    Token attuale: {token_display}")
    print(f"    Chat ID attuale: {chat_display}")
    print(f"    Notifiche: {'Attive' if telegram_config.get('attivo', True) else 'Disattive'}")

    print("\n    (Premi INVIO per mantenere il valore attuale)\n")

    # Bot Token
    nuovo_token = input("    Bot Token: ").strip()
    if nuovo_token:
        telegram_config["bot_token"] = nuovo_token

    # Chat ID
    nuovo_id = input("    Chat ID: ").strip()
    if nuovo_id:
        telegram_config["chat_id"] = nuovo_id

    # Salva subito la configurazione
    salva_configurazione()

    if verifica_configurazione_telegram():
        print("\n    ✅ Configurazione Telegram salvata!")
        print("    💡 Usa opzione 8 per testare.")
    else:
        print("\n    ⚠️ Configurazione incompleta")


# ============================================================
# 🔔 NOTIFICHE LOCALI
# ============================================================

def mostra_notifica_disponibile(nome_prodotto, taglie_disponibili, url_pagina=""):
    """Banner disponibilità."""

    taglie_str = ", ".join(taglie_disponibili)

    banner = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║      🚨🚨🚨  ATTENZIONE! PRODOTTO DISPONIBILE!  🚨🚨🚨                   ║
║                                                                          ║
║      ██████╗ ██╗███████╗██████╗  ██████╗ ███╗   ██╗██╗██████╗           ║
║      ██╔══██╗██║██╔════╝██╔══██╗██╔═══██╗████╗  ██║██║██╔══██╗          ║
║      ██║  ██║██║███████╗██████╔╝██║   ██║██╔██╗ ██║██║██████╔╝          ║
║      ██║  ██║██║╚════██║██╔═══╝ ██║   ██║██║╚██╗██║██║██╔══██╗          ║
║      ██████╔╝██║███████║██║     ╚██████╔╝██║ ╚████║██║██████╔╝          ║
║      ╚═════╝ ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═══╝╚═╝╚═════╝          ║
║                                                                          ║
║      📦 {nome_prodotto[:55]:<55}  ║
║      👕 Taglie: {taglie_str:<52}  ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)

    if url_pagina:
        print(f"    🔗 Link: {url_pagina}\n")


# ============================================================
# 👕 SELEZIONE TAGLIE (usa taglie reali dall'API)
# ============================================================

def seleziona_taglie(taglie_disponibili):
    """
    Selezione multipla taglie.
    taglie_disponibili: lista di nomi taglia reali dal prodotto (es. ["XS", "S", "M", "L", "XL"])
    """
    print(f"\n👕 SELEZIONE TAGLIE")
    print(f"   Disponibili: {', '.join(taglie_disponibili)}")
    print(f"\n   Inserisci:")
    print(f"   • Singola: M")
    print(f"   • Multiple: S, M, L")
    print(f"   • Tutte: tutte")
    print(f"   • Range: S-XL")

    while True:
        input_taglie = input(f"\n   Taglie: ").strip().upper()

        if not input_taglie:
            print("    ⚠️ Seleziona almeno una taglia")
            continue

        taglie_selezionate = []
        # Lista upper delle taglie disponibili per confronto
        taglie_upper = [t.upper() for t in taglie_disponibili]

        if input_taglie in ['TUTTE', 'ALL', '*']:
            taglie_selezionate = taglie_disponibili.copy()

        elif '-' in input_taglie and ',' not in input_taglie:
            parti = input_taglie.split('-')
            if len(parti) == 2:
                try:
                    idx_inizio = taglie_upper.index(parti[0].strip())
                    idx_fine = taglie_upper.index(parti[1].strip())
                    if idx_inizio <= idx_fine:
                        taglie_selezionate = taglie_disponibili[idx_inizio:idx_fine + 1]
                except ValueError:
                    print("    ⚠️ Range non valido")
                    continue

        else:
            for t in input_taglie.replace(' ', ',').split(','):
                t = t.strip()
                if t in taglie_upper:
                    idx = taglie_upper.index(t)
                    nome_reale = taglie_disponibili[idx]
                    if nome_reale not in taglie_selezionate:
                        taglie_selezionate.append(nome_reale)

        if taglie_selezionate:
            # Ordina secondo l'ordine originale
            taglie_selezionate.sort(key=lambda x: taglie_disponibili.index(x))
            print(f"\n    ✓ Selezionate: {', '.join(taglie_selezionate)}")

            if input("    Confermi? (s/n): ").strip().lower() in ['s', 'si', 'sì', 'y', '']:
                return taglie_selezionate
        else:
            print("    ⚠️ Nessuna taglia valida selezionata")


# ============================================================
# ➕ AGGIUNGI PRODOTTO (AUTOMATICO CON API DETAIL)
# ============================================================

def aggiungi_prodotto():
    """Aggiungi nuovo prodotto usando solo l'URL della pagina."""
    global prodotti_monitorati

    print("\n" + "=" * 60)
    print("           ➕ AGGIUNGI NUOVO PRODOTTO")
    print("=" * 60)

    # URL pagina prodotto
    while True:
        print("\n🔗 Incolla l'URL della pagina prodotto Zara")
        print("   (es. https://www.zara.com/it/it/giacca-pelle-p03918415.html)")

        url_pagina = input("\n   URL: ").strip()

        if not valida_url_zara(url_pagina):
            print("    ⚠️ URL non valido. Deve iniziare con https://www.zara.com/")
            continue

        seo_id = estrai_seo_product_id(url_pagina)
        if not seo_id:
            print("    ⚠️ Impossibile estrarre l'ID prodotto dall'URL")
            print("    L'URL deve contenere -pXXXXXXXX.html")
            continue

        print(f"    ✓ Prodotto ID: {seo_id}")
        break

    # Scarica dettagli prodotto
    print("\n    📡 Scaricamento dettagli prodotto...")
    details = fetch_product_details(seo_id)

    if not details:
        print("    ❌ Impossibile scaricare i dettagli del prodotto")
        return

    if not details["colori"]:
        print("    ❌ Nessun colore/variante trovato per questo prodotto")
        return

    nome = details["nome"]
    print(f"\n    📦 Prodotto: {nome}")

    # Selezione colore
    color_product_id_from_url = estrai_color_product_id(url_pagina)
    selected_color = None

    if len(details["colori"]) == 1:
        selected_color = details["colori"][0]
        print(f"    🎨 Colore: {selected_color['nome']}")
    else:
        # Prova a selezionare automaticamente dal v1 nell'URL
        if color_product_id_from_url:
            for c in details["colori"]:
                if c["product_id"] == color_product_id_from_url:
                    selected_color = c
                    print(f"    🎨 Colore (dall'URL): {selected_color['nome']}")
                    break

        if not selected_color:
            print(f"\n    🎨 SELEZIONA COLORE:")
            for i, c in enumerate(details["colori"], 1):
                n_taglie = len(c.get("taglie", []))
                print(f"       {i}. {c['nome']} ({n_taglie} taglie)")

            while True:
                try:
                    scelta = int(input(f"\n       Colore (1-{len(details['colori'])}): ").strip())
                    if 1 <= scelta <= len(details["colori"]):
                        selected_color = details["colori"][scelta - 1]
                        break
                except ValueError:
                    pass
                print("       ⚠️ Scelta non valida")

    if not selected_color["taglie"]:
        print("    ❌ Nessuna taglia disponibile per questo colore")
        return

    # Mostra taglie disponibili
    taglie_nomi = [t["nome"] for t in selected_color["taglie"]]
    print(f"\n    👕 Taglie disponibili: {', '.join(taglie_nomi)}")

    # Selezione taglie
    taglie_selezionate = seleziona_taglie(taglie_nomi)

    # Costruisci mappa SKU→taglia
    sku_map = {}
    for t in selected_color["taglie"]:
        sku_map[str(t["sku"])] = t["nome"]

    # Salva
    product_id = f"prod_{len(prodotti_monitorati) + 1}_{int(time.time())}"

    prodotti_monitorati[product_id] = {
        "nome": nome,
        "url_pagina": url_pagina,
        "seo_product_id": seo_id,
        "color_product_id": selected_color["product_id"],
        "color_name": selected_color["nome"],
        "taglie": taglie_selezionate,
        "sku_taglia_map": sku_map,
        "attivo": True,
        "data_aggiunta": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    print("\n" + "-" * 60)
    print("✅ PRODOTTO AGGIUNTO!")
    print(f"   📦 Nome: {nome}")
    print(f"   🎨 Colore: {selected_color['nome']}")
    print(f"   👕 Taglie monitorate: {', '.join(taglie_selezionate)}")
    print(f"   📊 Mappa SKU: {len(sku_map)} taglie mappate")
    print(f"   🔗 Pagina: {url_pagina[:60]}...")
    print("-" * 60)

    salva_configurazione()


def aggiungi_prodotto_cli(url_pagina, taglie_input):
    """Aggiunge prodotto da riga di comando (GitHub Actions)."""
    global prodotti_monitorati
    
    print(f"    📡 Analisi URL: {url_pagina}")
    
    seo_id = estrai_seo_product_id(url_pagina)
    if not seo_id:
        print("    ❌ Impossibile estrarre l'ID prodotto dall'URL")
        return False
        
    details = fetch_product_details(seo_id)
    if not details or not details["colori"]:
        print("    ❌ Impossibile scaricare dettagli o nessun colore")
        return False
        
    nome = details["nome"]
    color_product_id_from_url = estrai_color_product_id(url_pagina)
    selected_color = details["colori"][0]
    
    if color_product_id_from_url:
        for c in details["colori"]:
            if c["product_id"] == color_product_id_from_url:
                selected_color = c
                break
                
    if not selected_color.get("taglie"):
        print("    ❌ Nessuna taglia disponibile per questo colore")
        return False
        
    taglie_nomi = [t["nome"] for t in selected_color["taglie"]]
    taglie_upper = [t.upper() for t in taglie_nomi]
    taglie_selezionate = []
    
    taglie_input_upper = taglie_input.strip().upper()
    
    if taglie_input_upper in ['TUTTE', 'ALL', '*']:
        taglie_selezionate = taglie_nomi.copy()
    else:
        import re
        for t in taglie_input_upper.replace(' ', ',').split(','):
            t = t.strip()
            if not t: continue
            
            for idx, real_size_upper in enumerate(taglie_upper):
                if t == real_size_upper or re.search(r'\b' + re.escape(t) + r'\b', real_size_upper):
                    nome_reale = taglie_nomi[idx]
                    if nome_reale not in taglie_selezionate:
                        taglie_selezionate.append(nome_reale)
                    break
                    
    if not taglie_selezionate:
        print("    ⚠️ Nessuna taglia valida, prendo tutte le taglie")
        taglie_selezionate = taglie_nomi.copy()
        
    sku_map = {}
    for t in selected_color["taglie"]:
        sku_map[str(t["sku"])] = t["nome"]
        
    product_id = f"prod_{len(prodotti_monitorati) + 1}_{int(time.time())}"
    
    prodotti_monitorati[product_id] = {
        "nome": nome,
        "url_pagina": url_pagina,
        "seo_product_id": seo_id,
        "color_product_id": selected_color["product_id"],
        "color_name": selected_color["nome"],
        "taglie": taglie_selezionate,
        "sku_taglia_map": sku_map,
        "attivo": True,
        "data_aggiunta": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    salva_configurazione()
    print(f"    ✅ Aggiunto: {nome} [{selected_color['nome']}] -> {taglie_selezionate}")
    return True


# ============================================================
# 📋 LISTA PRODOTTI
# ============================================================

def mostra_lista_prodotti():
    """Mostra prodotti."""

    print("\n" + "=" * 90)
    print("                              📋 PRODOTTI MONITORATI")
    print("=" * 90)

    if not prodotti_monitorati:
        print("\n    ⚠️ Nessun prodotto configurato!")
        return

    for idx, (prod_id, info) in enumerate(prodotti_monitorati.items(), 1):
        stato = "🟢 Attivo" if info.get("attivo", True) else "🔴 Off"

        taglie = info.get('taglie', [])
        if isinstance(taglie, str):
            taglie = [taglie]

        color_name = info.get('color_name', 'N/A')
        url_pagina = info.get('url_pagina', 'Non configurato')
        sku_map = info.get('sku_taglia_map', {})
        n_mapped = len(sku_map)

        print(f"""
    ┌─ [{idx}] {'─' * 75}
    │  📦 Nome: {info.get('nome', 'N/A')}
    │  🎨 Colore: {color_name}
    │  👕 Taglie monitorate: {', '.join(taglie)}  │  {stato}
    │  📊 SKU mappati: {n_mapped}
    │  🔗 {url_pagina}
    └{'─' * 85}""")

    print(f"\n    📊 Totale: {len(prodotti_monitorati)} prodotti")
    print("=" * 90)


# ============================================================
# ❌ RIMUOVI PRODOTTO
# ============================================================

def rimuovi_prodotto():
    """Rimuovi prodotto."""
    global prodotti_monitorati

    if not prodotti_monitorati:
        print("\n    ⚠️ Nessun prodotto!")
        return

    mostra_lista_prodotti()

    prodotti_lista = list(prodotti_monitorati.items())

    try:
        scelta = input("\nNumero da rimuovere (0 = annulla): ").strip()

        if scelta == '0':
            return

        idx = int(scelta) - 1

        if 0 <= idx < len(prodotti_lista):
            prod_id, info = prodotti_lista[idx]

            if input(f"    Rimuovere '{info['nome']}'? (s/n): ").strip().lower() in ['s', 'si']:
                del prodotti_monitorati[prod_id]
                print(f"    ✓ Rimosso!")
                salva_configurazione()
    except:
        print("    ⚠️ Numero non valido")


# ============================================================
# ✏️ MODIFICA PRODOTTO
# ============================================================

def modifica_prodotto():
    """Modifica prodotto."""
    global prodotti_monitorati

    if not prodotti_monitorati:
        print("\n    ⚠️ Nessun prodotto!")
        return

    mostra_lista_prodotti()

    prodotti_lista = list(prodotti_monitorati.items())

    try:
        scelta = input("\nNumero da modificare (0 = annulla): ").strip()

        if scelta == '0':
            return

        idx = int(scelta) - 1

        if not (0 <= idx < len(prodotti_lista)):
            print("    ⚠️ Numero non valido")
            return

        prod_id, info = prodotti_lista[idx]
    except:
        print("    ⚠️ Numero non valido")
        return

    while True:
        taglie = info.get('taglie', [])
        color_name = info.get('color_name', 'N/A')

        print(f"\n    Modifica: {info['nome']} [{color_name}]")
        print(f"\n    1. Nome")
        print(f"    2. Taglie (sostituisci)")
        print(f"    3. Aggiungi taglia")
        print(f"    4. Rimuovi taglia")
        print(f"    5. Attiva/Disattiva")
        print(f"    6. URL Pagina (e ricalcola tutto)")
        print(f"    7. 🔄 Aggiorna mappa SKU (riscarica dal sito)")
        print(f"    0. ← Indietro")

        opzione = input("\n    Scelta: ").strip()

        if opzione == '0':
            break

        elif opzione == '1':
            nuovo = input("    Nuovo nome: ").strip()
            if nuovo:
                prodotti_monitorati[prod_id]['nome'] = nuovo
                info['nome'] = nuovo
                salva_configurazione()

        elif opzione == '2':
            sku_map = info.get('sku_taglia_map', {})
            taglie_disponibili = list(sku_map.values())
            if taglie_disponibili:
                nuove = seleziona_taglie(taglie_disponibili)
                prodotti_monitorati[prod_id]['taglie'] = nuove
                info['taglie'] = nuove
                salva_configurazione()
            else:
                print("    ⚠️ Mappa SKU vuota! Usa opzione 7 per riscaricarla")

        elif opzione == '3':
            sku_map = info.get('sku_taglia_map', {})
            taglie_disponibili = list(sku_map.values())
            taglie_attuali = info.get('taglie', [])
            mancanti = [t for t in taglie_disponibili if t not in taglie_attuali]

            if mancanti:
                print(f"    Disponibili: {', '.join(mancanti)}")
                nuova = input("    Aggiungi: ").strip().upper()
                mancanti_upper = [m.upper() for m in mancanti]
                if nuova in mancanti_upper:
                    idx_m = mancanti_upper.index(nuova)
                    taglie_attuali.append(mancanti[idx_m])
                    taglie_attuali.sort(key=lambda x: taglie_disponibili.index(x) if x in taglie_disponibili else 999)
                    prodotti_monitorati[prod_id]['taglie'] = taglie_attuali
                    salva_configurazione()
                else:
                    print("    ⚠️ Taglia non valida")
            else:
                print("    ⚠️ Tutte le taglie già aggiunte")

        elif opzione == '4':
            taglie_attuali = info.get('taglie', [])
            if len(taglie_attuali) > 1:
                print(f"    Attuali: {', '.join(taglie_attuali)}")
                rimuovi = input("    Rimuovi: ").strip().upper()
                attuali_upper = [t.upper() for t in taglie_attuali]
                if rimuovi in attuali_upper:
                    idx_r = attuali_upper.index(rimuovi)
                    taglie_attuali.pop(idx_r)
                    prodotti_monitorati[prod_id]['taglie'] = taglie_attuali
                    salva_configurazione()
                else:
                    print("    ⚠️ Taglia non trovata")
            else:
                print("    ⚠️ Devi tenere almeno una taglia")

        elif opzione == '5':
            nuovo_stato = not info.get('attivo', True)
            prodotti_monitorati[prod_id]['attivo'] = nuovo_stato
            info['attivo'] = nuovo_stato
            print(f"    ✓ {'Attivato' if nuovo_stato else 'Disattivato'}")
            salva_configurazione()

        elif opzione == '6':
            print(f"\n    URL attuale: {info.get('url_pagina', 'N/A')}")
            nuovo_url = input("    Nuovo URL pagina: ").strip()

            if valida_url_zara(nuovo_url):
                seo_id = estrai_seo_product_id(nuovo_url)
                if seo_id:
                    print(f"    📡 Ricalcolo dettagli per {seo_id}...")
                    details = fetch_product_details(seo_id)
                    if details:
                        info['url_pagina'] = nuovo_url
                        info['seo_product_id'] = seo_id
                        info['nome'] = details['nome']

                        # Selezione colore
                        color_pid = estrai_color_product_id(nuovo_url)
                        sel_color = None
                        if color_pid:
                            for c in details['colori']:
                                if c['product_id'] == color_pid:
                                    sel_color = c
                                    break
                        if not sel_color and details['colori']:
                            if len(details['colori']) == 1:
                                sel_color = details['colori'][0]
                            else:
                                print(f"\n    🎨 SELEZIONA COLORE:")
                                for i, c in enumerate(details['colori'], 1):
                                    print(f"       {i}. {c['nome']}")
                                try:
                                    sc = int(input(f"\n       Colore (1-{len(details['colori'])}): ").strip())
                                    sel_color = details['colori'][sc - 1]
                                except:
                                    sel_color = details['colori'][0]

                        if sel_color:
                            info['color_product_id'] = sel_color['product_id']
                            info['color_name'] = sel_color['nome']
                            sku_map = {}
                            for t in sel_color['taglie']:
                                sku_map[str(t['sku'])] = t['nome']
                            info['sku_taglia_map'] = sku_map

                            taglie_disp = [t['nome'] for t in sel_color['taglie']]
                            info['taglie'] = seleziona_taglie(taglie_disp)

                        prodotti_monitorati[prod_id] = info
                        salva_configurazione()
                        print("    ✅ Prodotto aggiornato!")
                    else:
                        print("    ❌ Impossibile scaricare i dettagli")
                else:
                    print("    ⚠️ Impossibile estrarre ID prodotto dall'URL")
            else:
                print("    ⚠️ URL non valido")

        elif opzione == '7':
            seo_id = info.get('seo_product_id', '')
            if not seo_id:
                seo_id = estrai_seo_product_id(info.get('url_pagina', ''))

            if seo_id:
                print(f"    📡 Riscariamento mappa SKU per {seo_id}...")
                details = fetch_product_details(seo_id)
                if details:
                    sku_map = build_sku_taglia_map(details, info.get('color_product_id'))
                    if sku_map:
                        info['sku_taglia_map'] = sku_map
                        prodotti_monitorati[prod_id] = info
                        salva_configurazione()
                        print(f"    ✅ Mappa aggiornata: {len(sku_map)} SKU")
                        for sku, nome in sku_map.items():
                            print(f"       {sku} → {nome}")
                    else:
                        print("    ❌ Mappa vuota")
                else:
                    print("    ❌ Impossibile contattare API")
            else:
                print("    ⚠️ Nessun seoProductId disponibile")


# ============================================================
# 🌐 CONTROLLO PRODOTTO
# ============================================================

def controlla_prodotto(prod_id, info):
    """Controlla disponibilità prodotto."""

    nome = info.get('nome', 'Sconosciuto')
    url_pagina = info.get('url_pagina', '')
    color_product_id = info.get('color_product_id')
    color_name = info.get('color_name', '')
    sku_taglia_map = info.get('sku_taglia_map', {})

    taglie_cercate = info.get('taglie', [])
    if isinstance(taglie_cercate, str):
        taglie_cercate = [taglie_cercate]

    print(f"\n    📦 {nome} [{color_name}]")
    print(f"    👕 Cercate: {', '.join(taglie_cercate)}")
    print(f"    {'─' * 50}")

    if not info.get('attivo', True):
        print(f"    ⏸️  Disattivato")
        return False, []

    if not color_product_id:
        print(f"    ❌ Nessun color_product_id configurato")
        return False, []

    # Se la mappa SKU è vuota, prova a ricostruirla
    if not sku_taglia_map:
        seo_id = info.get('seo_product_id', '')
        if not seo_id:
            seo_id = estrai_seo_product_id(url_pagina)
        if seo_id:
            print(f"    🔄 Ricostruzione mappa SKU...")
            details = fetch_product_details(seo_id)
            if details:
                sku_taglia_map = build_sku_taglia_map(details, color_product_id)
                if sku_taglia_map:
                    info['sku_taglia_map'] = sku_taglia_map
                    prodotti_monitorati[prod_id] = info

    try:
        session = curl_requests.Session()

        availability_url = get_availability_url(color_product_id)

        response = session.get(
            availability_url,
            impersonate=BROWSER_IMPERSONATE,
            headers=HEADERS,
            cookies=parse_cookies(COOKIES),
            timeout=30
        )

        if response.status_code != 200:
            print(f"    ❌ Errore HTTP {response.status_code}")
            return False

        data = response.json()
        skus = data.get("skusAvailability", [])

        if not skus:
            print(f"    ❌ Nessun SKU trovato")
            return False

        print(f"    📊 Stato:")

        disponibili = []
        taglie_stato_lista = []

        for sku_info in skus:
            sku_id = str(sku_info.get("sku", ""))
            avail = sku_info.get("availability", "N/A")

            # Usa la mappa reale SKU→taglia
            taglia = sku_taglia_map.get(sku_id, f"SKU:{sku_id}")

            simbolo = {"in_stock": "🟢", "low_on_stock": "🟡", "back_soon": "🟠"}.get(avail, "🔴")

            is_cercata = taglia in taglie_cercate
            marcatore = " 👈" if is_cercata else ""

            if is_cercata and avail in ["in_stock", "low_on_stock"]:
                disponibili.append((taglia, avail))
                
            taglie_stato_lista.append({
                "nome": taglia,
                "stato": avail,
                "is_cercata": is_cercata
            })

            print(f"       {simbolo} {taglia:>4}{marcatore}")

        print(f"\n    🎯 RISULTATO:")

        if disponibili:
            taglie_disp = [f"{t} {'⚠️' if s == 'low_on_stock' else ''}" for t, s in disponibili]

            print(f"    ╔════════════════════════════════════════════════════╗")
            print(f"    ║  ✅ DISPONIBILI: {', '.join(taglie_disp):<34} ║")
            print(f"    ╚════════════════════════════════════════════════════╝")

            taglie_nomi = [t for t, _ in disponibili]

            # Notifica console
            mostra_notifica_disponibile(nome, taglie_nomi, url_pagina)

            # Notifica Telegram
            invia_notifica_disponibile_telegram(nome, taglie_nomi, url_pagina)

            return True, taglie_stato_lista
        else:
            print(f"    ╔════════════════════════════════════════════════════╗")
            print(f"    ║  ❌ Nessuna taglia cercata disponibile             ║")
            print(f"    ╚════════════════════════════════════════════════════╝")

            return False, taglie_stato_lista

    except Exception as e:
        print(f"    ❌ Errore: {e}")
        return False, []


# ============================================================
# 🔄 CONTROLLO TUTTI
# ============================================================

def genera_dashboard_html(risultati, timestamp):
    os.makedirs('public', exist_ok=True)
    
    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zara Monitor Dashboard</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --success: #22c55e;
            --warning: #eab308;
            --danger: #ef4444;
            --border: #334155;
        }}
        * {{ box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }}
        body {{ background: var(--bg-color); color: var(--text-main); margin: 0; padding: 20px; line-height: 1.5; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid var(--border); padding-bottom: 20px; flex-wrap: wrap; gap: 15px; }}
        .header h1 {{ margin: 0; font-size: 24px; display: flex; align-items: center; gap: 10px; }}
        .time {{ color: var(--text-muted); font-size: 14px; background: var(--card-bg); padding: 5px 12px; border-radius: 20px; border: 1px solid var(--border); }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
        .card {{ background: var(--card-bg); border-radius: 12px; padding: 20px; border: 1px solid var(--border); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-2px); border-color: var(--text-muted); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; gap: 10px; }}
        .card-title {{ margin: 0; font-size: 16px; font-weight: 600; line-height: 1.3; }}
        .card-color {{ color: var(--text-muted); font-size: 13px; margin-top: 4px; }}
        .status-badge {{ padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; white-space: nowrap; }}
        .status-badge.active {{ background: rgba(34, 197, 94, 0.1); color: var(--success); border: 1px solid rgba(34, 197, 94, 0.2); }}
        .status-badge.inactive {{ background: rgba(148, 163, 184, 0.1); color: var(--text-muted); border: 1px solid rgba(148, 163, 184, 0.2); }}
        .sizes-container {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px; }}
        .size-badge {{ padding: 6px 10px; border-radius: 6px; font-size: 13px; font-weight: 500; border: 1px solid var(--border); background: rgba(0,0,0,0.2); display: flex; align-items: center; gap: 6px; }}
        .size-badge.cercata {{ border-color: var(--accent); }}
        .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
        .dot.in_stock {{ background: var(--success); box-shadow: 0 0 8px var(--success); }}
        .dot.low_on_stock {{ background: var(--warning); }}
        .dot.back_soon {{ background: var(--warning); opacity: 0.5; }}
        .dot.out_of_stock {{ background: var(--danger); }}
        .btn {{ display: inline-block; background: var(--text-main); color: var(--bg-color); text-decoration: none; padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: 600; transition: opacity 0.2s; }}
        .btn:hover {{ opacity: 0.9; }}
        .link-icon {{ color: var(--text-muted); text-decoration: none; }}
        .link-icon:hover {{ color: var(--accent); }}
        .legend {{ margin-top: 40px; padding: 15px; background: var(--card-bg); border-radius: 8px; border: 1px solid var(--border); font-size: 13px; display: flex; gap: 20px; flex-wrap: wrap; color: var(--text-muted); }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛍️ Zara Monitor</h1>
            <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
                <span class="time">Ultimo agg: {timestamp}</span>
                <a href="https://github.com/ThomasMazzeoo/Bot-Zara-Taglie/edit/main/prodotti.json" target="_blank" class="btn">Gestisci Prodotti</a>
            </div>
        </div>
        
        <div class="grid">
"""
    for prod_id, r in risultati.items():
        info = r['info']
        attivo = info.get('attivo', True)
        nome = info.get('nome', 'Sconosciuto')
        colore = info.get('color_name', '')
        url = info.get('url_pagina', '#')
        
        status_class = "active" if attivo else "inactive"
        status_text = "ATTIVO" if attivo else "INATTIVO"
        
        html += f"""
            <div class="card">
                <div class="card-header">
                    <div>
                        <h3 class="card-title">
                            <a href="{url}" target="_blank" class="link-icon">🔗</a> 
                            {nome}
                        </h3>
                        <div class="card-color">🎨 {colore}</div>
                    </div>
                    <span class="status-badge {status_class}">{status_text}</span>
                </div>
                <div class="sizes-container">
        """
        
        if non_taglie := r.get('taglie_stato', []):
            for t in non_taglie:
                nome_taglia = t['nome']
                stato = t['stato']
                cercata = t['is_cercata']
                
                cercata_class = "cercata" if cercata else ""
                dot_class = stato if stato in ['in_stock', 'low_on_stock', 'back_soon'] else 'out_of_stock'
                
                html += f"""
                    <div class="size-badge {cercata_class}" title="Stato: {stato}{' (Monitorata)' if cercata else ''}">
                        <div class="dot {dot_class}"></div>
                        {nome_taglia}
                    </div>
                """
        else:
            html += """<div class="card-color">Nessun dato SKU. Attendi il prossimo controllo.</div>"""
            
        html += """
                </div>
            </div>
        """

    html += """
        </div>
        
        <div class="legend">
            <div class="legend-item"><div class="dot in_stock"></div> Disponibile</div>
            <div class="legend-item"><div class="dot low_on_stock"></div> Pochi pezzi</div>
            <div class="legend-item"><div class="dot back_soon"></div> Torna presto</div>
            <div class="legend-item"><div class="dot out_of_stock"></div> Esaurito</div>
            <div class="legend-item"><div class="size-badge cercata" style="padding: 2px 6px;">Bordo blu</div> Taglia monitorata</div>
        </div>
    </div>
</body>
</html>
"""

    with open('public/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"    🌐 Dashboard HTML generata in public/index.html")


def controlla_tutti_prodotti(da_actions=False):
    """Controlla tutti i prodotti."""

    if not prodotti_monitorati:
        print("\n    ⚠️ Nessun prodotto!")
        return

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    attivi = sum(1 for p in prodotti_monitorati.values() if p.get('attivo', True))

    print(f"\n{'═' * 70}")
    print(f"[{timestamp}] 🔍 CONTROLLO DISPONIBILITÀ")
    print(f"📦 Prodotti: {attivi}/{len(prodotti_monitorati)}")
    print(f"{'═' * 70}")

    disponibili = 0
    risultati_dashboard = {}

    for prod_id, info in prodotti_monitorati.items():
        is_avail, taglie_stato = controlla_prodotto(prod_id, info)
        if is_avail:
            disponibili += 1
            
        risultati_dashboard[prod_id] = {
            "info": info,
            "is_avail": is_avail,
            "taglie_stato": taglie_stato
        }

    print(f"\n{'─' * 70}")
    print(f"📊 RIEPILOGO: {disponibili}/{attivi} disponibili")
    print(f"{'─' * 70}")
    
    if da_actions:
        genera_dashboard_html(risultati_dashboard, timestamp)


def controlla_con_ritardo():
    """Controllo con ritardo."""
    ritardo = random.uniform(0, RITARDO_CASUALE_MAX * 60)
    print(f"\n⏱️ Attendo {ritardo / 60:.1f} min...")
    time.sleep(ritardo)
    controlla_tutti_prodotti()


# ============================================================
# ⏸️ MENU PAUSA (quando premi CTRL+C durante monitoraggio)
# ============================================================

def mostra_menu_pausa():
    """Menu quando si preme CTRL+C durante il monitoraggio."""
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    ⏸️  MONITORAGGIO IN PAUSA  ⏸️                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  1. ▶️  Riprendi monitoraggio                                        ║
║  2. 📋 Lista prodotti                                                ║
║  3. ➕ Aggiungi prodotto                                             ║
║  4. ✏️  Modifica prodotto                                            ║
║  5. ❌ Rimuovi prodotto                                              ║
║  6. 📱 Configura Telegram                                            ║
║  0. 🚪 Esci dal programma                                            ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def gestisci_menu_pausa():
    """Gestisce il menu pausa. Ritorna True=riprendi, False=esci."""
    while True:
        mostra_menu_pausa()
        scelta = input("    👉 ").strip()

        if scelta == '1':
            return True  # Riprendi
        elif scelta == '2':
            mostra_lista_prodotti()
            input("\n    INVIO...")
        elif scelta == '3':
            aggiungi_prodotto()
        elif scelta == '4':
            modifica_prodotto()
        elif scelta == '5':
            rimuovi_prodotto()
        elif scelta == '6':
            configura_telegram()
        elif scelta == '0':
            return False  # Esci


# ============================================================
# 📋 MENU
# ============================================================

def mostra_menu():
    """Menu principale."""

    tot = len(prodotti_monitorati)
    attivi = sum(1 for p in prodotti_monitorati.values() if p.get('attivo', True))
    taglie = sum(len(info.get('taglie', [])) for info in prodotti_monitorati.values() if info.get('attivo', True))
    tg = "🟢" if verifica_configurazione_telegram() else "🔴"

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    🛍️  ZARA MONITOR v5.0  🛍️                         ║
╠══════════════════════════════════════════════════════════════════════╣
║  📦 Prodotti: {attivi}/{tot}  │  👕 Taglie: {taglie:<4}  │  📱 Telegram: {tg}            ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║    1. ➕ Aggiungi prodotto                                           ║
║    2. 📋 Lista prodotti                                              ║
║    3. ✏️  Modifica prodotto                                          ║
║    4. ❌ Rimuovi prodotto                                            ║
║    5. 🔍 Test controllo                                              ║
║    6. 🚀 AVVIA MONITORAGGIO                                          ║
║                                                                      ║
║    7. 📱 Configura Telegram                                          ║
║    8. 📱 Test Telegram                                               ║
║                                                                      ║
║    0. 🚪 Esci                                                        ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def avvia_monitoraggio():
    """Avvia monitoraggio con supporto pausa."""

    attivi = sum(1 for p in prodotti_monitorati.values() if p.get('attivo', True))

    if attivi == 0:
        print("\n    ⚠️ Nessun prodotto attivo!")
        return

    taglie = sum(len(info.get('taglie', [])) for info in prodotti_monitorati.values() if info.get('attivo', True))

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║              🚀 MONITORAGGIO ATTIVO 🚀                               ║
╠══════════════════════════════════════════════════════════════════════╣
║  📦 {attivi} prodotti  │  👕 {taglie} taglie  │  ⏰ Ogni {INTERVALLO_MINUTI} min{' ' * 20}║
║  📱 Telegram: {'Attivo' if verifica_configurazione_telegram() else 'Non configurato':<52} ║
╠══════════════════════════════════════════════════════════════════════╣
║  ⌨️  CTRL+C → Menu impostazioni                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    if verifica_configurazione_telegram():
        invia_notifica_avvio_telegram()

    while True:  # Loop per pausa e ripresa
        print("📍 Controllo...")
        controlla_tutti_prodotti()

        schedule.clear()
        schedule.every(INTERVALLO_MINUTI).minutes.do(controlla_con_ritardo)

        print(f"\n📅 Prossimo tra ~{INTERVALLO_MINUTI} min (CTRL+C per menu)\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            schedule.clear()
            print("\n")

            if gestisci_menu_pausa():
                print("\n▶️  Ripresa...\n")
                continue  # Riprendi loop
            else:
                salva_configurazione()
                print("\n👋 Ciao!\n")
                sys.exit(0)


# ============================================================
# 🚀 MAIN
# ============================================================

def main():
    """Main."""

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║            🛍️  ZARA AVAILABILITY MONITOR  🛍️                         ║
║                     v5.0 - Taglie Accurate                           ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    print("📂 Caricamento configurazione...")
    carica_configurazione()

    while True:
        mostra_menu()

        scelta = input("    👉 Scelta: ").strip()

        if scelta == '1':
            aggiungi_prodotto()
        elif scelta == '2':
            mostra_lista_prodotti()
            input("\n    INVIO per continuare...")
        elif scelta == '3':
            modifica_prodotto()
        elif scelta == '4':
            rimuovi_prodotto()
        elif scelta == '5':
            controlla_tutti_prodotti()
            input("\n    INVIO...")
        elif scelta == '6':
            avvia_monitoraggio()
        elif scelta == '7':
            configura_telegram()
        elif scelta == '8':
            test_telegram()
            input("\n    INVIO...")
        elif scelta == '0':
            salva_configurazione()
            print("\n👋 Configurazione salvata. Ciao!\n")
            sys.exit(0)
        else:
            print("\n    ⚠️ Opzione non valida")


if __name__ == "__main__":
    # Avvio con --check → singolo controllo (per GitHub Actions)
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        print("🚀 Avvio controllo singolo (GitHub Actions)...\n")
        carica_configurazione()

        if not prodotti_monitorati:
            print("⚠️ Nessun prodotto da controllare!")
            sys.exit(0)

        controlla_tutti_prodotti(da_actions=True)
        sys.exit(0)

    # Avvio con --auto → monitoraggio diretto in loop
    elif len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print("🚀 Avvio rapido...\n")
        carica_configurazione()

        if not prodotti_monitorati:
            print("⚠️ Nessun prodotto! Avvia prima: python main.py")
            sys.exit(1)

        avvia_monitoraggio()
        
    # Avvio con --add → aggiunta da CLI
    elif len(sys.argv) > 1 and sys.argv[1] == "--add":
        print("🚀 Avvio aggiunta rapida (CLI)...\n")
        carica_configurazione()
        
        try:
            url_idx = sys.argv.index("--add") + 1
            url = sys.argv[url_idx]
            
            taglie = "TUTTE"
            if "--sizes" in sys.argv:
                size_idx = sys.argv.index("--sizes") + 1
                taglie = sys.argv[size_idx]
                
            if aggiungi_prodotto_cli(url, taglie):
                # Esegue un check per generare anche l'HTML
                controlla_tutti_prodotti(da_actions=True)
                sys.exit(0)
            else:
                sys.exit(1)
        except Exception as e:
            print(f"❌ Errore argomenti: {e}")
            sys.exit(1)
            
    # Avvio con --gui → Web GUI locale
    elif len(sys.argv) > 1 and sys.argv[1] == "--gui":
        try:
            import server
            server.run_gui()
        except ImportError as e:
            print(f"❌ Errore: {e}")
            print("💡 Assicurati di aver installato Flask: pip install flask")
            sys.exit(1)
            
    else:
        # Avvio normale con menu
        try:
            main()
        except KeyboardInterrupt:
            salva_configurazione()
            print("\n\n👋 Ciao!\n")
            sys.exit(0)