# 🛍️ Zara Monitor Bot

Bot per monitorare la disponibilità di prodotti su Zara con notifiche Telegram in tempo reale.

## ✨ Funzionalità

- **Monitoraggio automatico** — Controlla periodicamente la disponibilità dei prodotti
- **Taglie accurate** — Usa l'API Detail di Zara per mappare correttamente ogni SKU alla sua taglia reale
- **Notifiche Telegram** — Ricevi un messaggio immediato quando un prodotto torna disponibile
- **Multi-prodotto** — Monitora più prodotti e taglie contemporaneamente
- **Rilevamento automatico** — Basta incollare l'URL del prodotto: nome, colore e taglie vengono scaricati automaticamente
- **Menu pausa** — Premi `CTRL+C` durante il monitoraggio per aggiungere/modificare prodotti senza fermare il bot

## 📦 Installazione

### 1. Clona il repository
```bash
git clone https://github.com/ThomasMazzeoo/Bot-Zara-Taglie.git
cd Bot-Zara-Taglie
```

### 2. Installa le dipendenze
```bash
pip install schedule curl_cffi requests
```

### 3. Configura Telegram (opzionale)
1. Cerca **@BotFather** su Telegram → `/newbot` → copia il **Token**
2. Cerca **@userinfobot** → `/start` → copia il tuo **Chat ID**
3. Avvia il bot e usa l'opzione `7. Configura Telegram` per inserire le credenziali

## 🚀 Utilizzo

```bash
python main.py
```

### Aggiungere un prodotto
1. Scegli `1. Aggiungi prodotto`
2. Incolla l'URL della pagina Zara (es. `https://www.zara.com/it/it/giacca-p03918415.html`)
3. Il bot scarica automaticamente nome, colore e taglie disponibili
4. Seleziona le taglie da monitorare

### Avviare il monitoraggio
Scegli `6. AVVIA MONITORAGGIO` — il bot controllerà ogni 10 minuti e ti avviserà su Telegram quando una taglia torna disponibile.

### Avvio rapido (senza menu)
```bash
python main.py --auto
```

## ⚙️ Configurazione

Al primo avvio viene creato il file `zara_monitor_config.json` con le tue impostazioni. Questo file contiene le credenziali Telegram ed è **escluso dal repository** tramite `.gitignore`.

Vedi [`zara_monitor_config.example.json`](zara_monitor_config.example.json) per il formato.

## 📁 Struttura

```
├── main.py                              # Script principale
├── zara_monitor_config.json             # ⚠️ Config privato (non nel repo)
├── zara_monitor_config.example.json     # Template di esempio
├── AVVIA_MONITORAGGIO.bat               # Avvio rapido Windows
├── Bot.bat                              # Avvio con menu Windows
└── .gitignore
```

## 🔧 Come funziona

Il bot usa due API interne di Zara:

| API | Scopo |
|-----|-------|
| **Detail** (`/itxrest/2/catalog/store/.../product/{id}`) | Ottiene nome, colori e mappa SKU→taglia |
| **Availability** (`/itxrest/1/.../availability`) | Stato disponibilità in tempo reale |

Quando aggiungi un prodotto, il bot scarica la mappa esatta `SKU → taglia` dal sito, garantendo che le taglie mostrate siano sempre corrette.
