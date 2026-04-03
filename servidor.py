from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
import os

app = Flask(__name__)

# 1. CONFIGURAÇÃO DO BANCO
_db_url = os.environ.get("DATABASE_URL", "")
DATABASE_URL = _db_url.replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# 2. DEFINIÇÃO DO HTML DO PAINEL (Precisa estar aqui no topo!)
PAINEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Painel Admin Lucs</title>
    <style>
        body { font-family: sans-serif; background: #0d1117; color: white; padding: 20px; }
        .container { max-width: 800px; margin: auto; background: #161b22; padding: 20px; border-radius: 8px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #30363d; padding: 10px; text-align: left; }
        button { cursor: pointer; padding: 5px 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Gerenciador de Licenças</h1>
        <input type="text" id="n" placeholder="Nome">
        <input type="text" id="c" placeholder="Chave">
        <button onclick="add()">Criar Chave</button>
        <table id="t"></table>
    </div>
    <script>
        async function load() {
            const r = await fetch('/admin/dados');
            const d = await r.json();
            document.getElementById('t').innerHTML = d.map(u => 
                `<tr><td>${u.nome}</td><td>${u.chave}</td></tr>`
            ).join('');
        }
        async function add() {
            await fetch('/admin/criar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome: document.getElementById('n').value, chave: document.getElementById('c').value})
            });
            load();
        }
        load();
    </script>
</body>
</html>
"""

# 3. ROTAS DO SISTEMA
@app.route("/")
def home():
    # Tenta carregar o arquivo do planejador, se não existir, mostra aviso
    try:
        return send_file('planejador.html')
    except:
        return "<h1>Sistema Online</h1><p>Aguardando arquivo do planejador.</p>"

@app.route("/admin-sistema")
def painel_gerenciador():
    return render_template_string(PAINEL_HTML)

@app.route("/api/validar", methods=["POST"])
def validar():
    dados = request.json or {}
    chave = dados.get("chave", "").strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM usuarios WHERE chave = %s", (chave,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return jsonify({"ok": True, "nome": user['nome']})
    return jsonify({"ok": False}), 401

@app.route("/admin/dados")
def admin_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome, chave FROM usuarios")
    res = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(res)

@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    d = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (nome, chave) VALUES (%s, %s)", (d['nome'], d['chave']))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
