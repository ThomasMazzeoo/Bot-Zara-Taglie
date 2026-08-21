import os
import threading
import webbrowser
from flask import Flask, jsonify, request, render_template_string
import main

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zara Monitor - Gestione Locale</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        :root {
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --danger: #ef4444;
            --danger-hover: #dc2626;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
            --radius: 12px;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
            background-image: 
                radial-gradient(at 0% 0%, hsla(253,16%,7%,1) 0, transparent 50%), 
                radial-gradient(at 50% 0%, hsla(225,39%,30%,0.2) 0, transparent 50%), 
                radial-gradient(at 100% 0%, hsla(339,49%,30%,0.1) 0, transparent 50%);
            min-height: 100vh;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }

        .header h1 {
            margin: 0;
            font-size: 28px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 12px;
            background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* Form Aggiunta */
        .add-card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 40px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }

        .add-card h2 {
            margin-top: 0;
            font-size: 18px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .form-row {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }

        .input-group {
            flex: 1;
            min-width: 200px;
        }

        .input-group.url {
            flex: 3;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-size: 14px;
            color: var(--text-muted);
            font-weight: 500;
        }

        input {
            width: 100%;
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
            box-sizing: border-box;
        }

        input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }

        button {
            background: var(--primary);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }

        button:hover {
            background: var(--primary-hover);
            transform: translateY(-1px);
        }

        button.btn-danger {
            background: rgba(239, 68, 68, 0.1);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }

        button.btn-danger:hover {
            background: var(--danger);
            color: white;
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        /* Prodotti Grid */
        .products-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }

        .product-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
            transition: all 0.2s;
            display: flex;
            flex-direction: column;
        }

        .product-card:hover {
            border-color: var(--text-muted);
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2);
        }

        .product-title {
            font-size: 16px;
            font-weight: 600;
            margin: 0 0 8px 0;
            line-height: 1.4;
        }

        .product-title a {
            color: var(--text);
            text-decoration: none;
        }

        .product-title a:hover {
            color: var(--primary);
        }

        .product-meta {
            color: var(--text-muted);
            font-size: 13px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .tags-container {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 20px;
            flex-grow: 1;
        }

        .tag {
            background: rgba(59, 130, 246, 0.1);
            color: var(--primary);
            border: 1px solid rgba(59, 130, 246, 0.2);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }

        .card-actions {
            display: flex;
            justify-content: flex-end;
            border-top: 1px solid var(--border);
            padding-top: 16px;
        }

        /* Toast */
        #toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: var(--surface);
            color: white;
            padding: 16px 24px;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            gap: 12px;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
            z-index: 1000;
            border-left: 4px solid var(--primary);
        }

        #toast.show {
            transform: translateY(0);
            opacity: 1;
        }
        
        #toast.error {
            border-left-color: var(--danger);
        }
        
        .loading-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(4px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 2000;
            flex-direction: column;
            gap: 16px;
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid rgba(255,255,255,0.1);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin { 100% { transform: rotate(360deg); } }

    </style>
</head>
<body>

    <div class="loading-overlay" id="loading">
        <div class="spinner"></div>
        <div style="font-weight: 500;">Operazione in corso...<br>Potrebbe richiedere qualche secondo (API Zara)</div>
    </div>

    <div class="container">
        <div class="header">
            <h1>🛍️ Zara Monitor - GUI Locale</h1>
            <div style="color: var(--text-muted); font-size: 14px;">
                I dati vengono salvati direttamente in <b>prodotti.json</b>
            </div>
        </div>

        <div class="add-card">
            <h2>➕ Aggiungi Nuovo Prodotto</h2>
            <form id="addForm" onsubmit="addProduct(event)">
                <div class="form-row">
                    <div class="input-group url">
                        <label>URL Prodotto Zara</label>
                        <input type="url" id="urlInput" placeholder="https://www.zara.com/it/it/..." required>
                    </div>
                    <div class="input-group">
                        <label>Taglie (es. S, M, L oppure TUTTE)</label>
                        <input type="text" id="sizesInput" placeholder="TUTTE" value="TUTTE" required>
                    </div>
                    <div class="input-group" style="display: flex; align-items: flex-end;">
                        <button type="submit" id="addBtn">
                            Aggiungi al Monitor
                        </button>
                    </div>
                </div>
            </form>
        </div>

        <h2 style="font-size: 20px; margin-bottom: 24px;">📦 Prodotti Monitorati (<span id="count">0</span>)</h2>
        <div class="products-grid" id="productsGrid">
            <!-- Products injected here -->
        </div>
    </div>

    <div id="toast">✅ Operazione completata!</div>

    <script>
        function showToast(message, isError = false) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            if (isError) toast.classList.add('error');
            else toast.classList.remove('error');
            
            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }
        
        function showLoading(show) {
            document.getElementById('loading').style.display = show ? 'flex' : 'none';
        }

        async function loadProducts() {
            try {
                const res = await fetch('/api/products');
                const products = await res.json();
                
                const grid = document.getElementById('productsGrid');
                grid.innerHTML = '';
                
                let count = 0;
                
                for (const [id, info] of Object.entries(products)) {
                    count++;
                    const card = document.createElement('div');
                    card.className = 'product-card';
                    
                    const taglie = Array.isArray(info.taglie) ? info.taglie.join(', ') : info.taglie;
                    const dataAggiunta = info.data_aggiunta || 'Sconosciuta';
                    
                    card.innerHTML = `
                        <h3 class="product-title">
                            <a href="${info.url_pagina}" target="_blank">🔗 ${info.nome}</a>
                        </h3>
                        <div class="product-meta">
                            🎨 ${info.color_name}
                        </div>
                        <div class="tags-container">
                            <span class="tag">👕 ${taglie}</span>
                            <span class="tag" style="background: rgba(255,255,255,0.05); color: #94a3b8; border-color: rgba(255,255,255,0.1);">🕒 ${dataAggiunta.split(' ')[0]}</span>
                        </div>
                        <div class="card-actions">
                            <button onclick="editSizes('${id}', '${taglie}')" style="background: rgba(59, 130, 246, 0.1); color: var(--primary); border: 1px solid rgba(59, 130, 246, 0.2); padding: 8px 16px; font-size: 13px; border-radius: 8px; font-weight: 600; cursor: pointer; margin-right: 8px; transition: all 0.2s;">
                                ✏️ Taglie
                            </button>
                            <button class="btn-danger" onclick="removeProduct('${id}')" style="padding: 8px 16px; font-size: 13px;">
                                ❌ Rimuovi
                            </button>
                        </div>
                    `;
                    grid.appendChild(card);
                }
                
                document.getElementById('count').textContent = count;
                
                if (count === 0) {
                    grid.innerHTML = '<div style="color: #94a3b8;">Nessun prodotto monitorato. Incolla un URL qui sopra per iniziare!</div>';
                }
                
            } catch (err) {
                console.error(err);
                showToast("Errore di connessione", true);
            }
        }

        async function addProduct(e) {
            e.preventDefault();
            const url = document.getElementById('urlInput').value;
            const sizes = document.getElementById('sizesInput').value;
            
            showLoading(true);
            try {
                const res = await fetch('/api/add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url, sizes })
                });
                
                if (res.ok) {
                    showToast("Prodotto aggiunto con successo!");
                    document.getElementById('urlInput').value = '';
                    await loadProducts();
                } else {
                    const data = await res.json();
                    showToast("Errore: " + (data.error || "Impossibile aggiungere"), true);
                }
            } catch (err) {
                showToast("Errore di rete", true);
            } finally {
                showLoading(false);
            }
        }
        
        async function editSizes(id, currentSizes) {
            const newSizes = prompt("Modifica le taglie da monitorare (es. S, M, L oppure TUTTE):", currentSizes);
            if (newSizes === null || newSizes.trim() === '') return;
            
            try {
                const res = await fetch('/api/update_sizes', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id, sizes: newSizes })
                });
                
                if (res.ok) {
                    showToast("Taglie aggiornate!");
                    await loadProducts();
                } else {
                    const data = await res.json();
                    showToast("Errore: " + (data.error || "Impossibile aggiornare"), true);
                }
            } catch (err) {
                showToast("Errore di rete", true);
            }
        }

        async function removeProduct(id) {
            if (!confirm("Sei sicuro di voler rimuovere questo prodotto?")) return;
            
            try {
                const res = await fetch('/api/remove', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                
                if (res.ok) {
                    showToast("Prodotto rimosso!");
                    await loadProducts();
                } else {
                    showToast("Errore durante la rimozione", true);
                }
            } catch (err) {
                showToast("Errore di rete", true);
            }
        }

        // Init
        loadProducts();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/products')
def get_products():
    return jsonify(main.prodotti_monitorati)

@app.route('/api/add', methods=['POST'])
def add_product():
    data = request.json
    url = data.get('url')
    sizes = data.get('sizes', 'TUTTE')
    
    if main.aggiungi_prodotto_cli(url, sizes):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "error": "Verifica l'URL o la connessione API"}), 400

@app.route('/api/remove', methods=['POST'])
def remove_product():
    data = request.json
    prod_id = data.get('id')
    
    if prod_id in main.prodotti_monitorati:
        del main.prodotti_monitorati[prod_id]
        main.salva_configurazione()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404
    
@app.route('/api/update_sizes', methods=['POST'])
def update_sizes():
    data = request.json
    prod_id = data.get('id')
    sizes_input = data.get('sizes')
    
    if prod_id in main.prodotti_monitorati:
        info = main.prodotti_monitorati[prod_id]
        
        # Le taglie disponibili reali (tutte le taglie di questo colore)
        taglie_disponibili_nomi = list(info.get('sku_taglia_map', {}).values())
        if not taglie_disponibili_nomi:
            return jsonify({"status": "error", "error": "Mappa taglie non disponibile per questo prodotto"}), 400
            
        taglie_upper = [t.upper() for t in taglie_disponibili_nomi]
        taglie_selezionate = []
        sizes_input_upper = sizes_input.strip().upper()
        
        if sizes_input_upper in ['TUTTE', 'ALL', '*']:
            taglie_selezionate = taglie_disponibili_nomi.copy()
        else:
            for t in sizes_input_upper.replace(' ', ',').split(','):
                t = t.strip()
                if t in taglie_upper:
                    idx = taglie_upper.index(t)
                    nome_reale = taglie_disponibili_nomi[idx]
                    if nome_reale not in taglie_selezionate:
                        taglie_selezionate.append(nome_reale)
                        
        if not taglie_selezionate:
            return jsonify({"status": "error", "error": f"Nessuna taglia valida. Disponibili: {', '.join(taglie_disponibili_nomi)}"}), 400
            
        main.prodotti_monitorati[prod_id]['taglie'] = taglie_selezionate
        main.salva_configurazione()
        return jsonify({"status": "success", "taglie": taglie_selezionate})
        
    return jsonify({"status": "error", "error": "Prodotto non trovato"}), 404

def run_gui():
    print("🚀 Avvio Web GUI locale...")
    main.carica_configurazione()
    
    def open_browser():
        webbrowser.open_new("http://127.0.0.1:5000")
        
    threading.Timer(1.0, open_browser).start()
    
    print("🌐 Interfaccia disponibile su: http://127.0.0.1:5000")
    print("Premi CTRL+C nel terminale per spegnere.")
    # Usiamo werkzeug per un avvio pulito senza troppi log
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='127.0.0.1', port=5000, debug=False)

if __name__ == '__main__':
    run_gui()
