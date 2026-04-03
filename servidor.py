from flask import Flask, request, jsonify, render_template_string
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import os
import random
import string

app = Flask(__name__)

# CONFIGURAÇÃO BANCO DE DADOS RENDER
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def gerar_serial():
    chars = string.ascii_uppercase + string.digits
    return f"LUCS-{''.join(random.choices(chars, k=4))}-{''.join(random.choices(chars, k=4))}"

# O LAYOUT AZUL QUE VOCÊ GOSTOU
HTML_AZUL = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>CyberAdmin | Lucs Tech</title>
    <style>
        :root { 
            --bg: #050a14; --accent: #00d2ff; --card: rgba(10, 20, 40, 0.9); 
            --text: #e0f2ff; --muted: #6a89a7; --green: #00ffaa; --red: #ff3c3c;
        }
        body { 
            background: radial-gradient(circle at top, #0a1931 0%, #050a14 100%); 
            color: var(--text); font-family: 'Segoe UI', sans-serif; padding: 25px; margin: 0;
        }
        .container { max-width: 1000px; margin: auto; }
        .header { border-bottom: 1px solid rgba(0, 210, 255, 0.3); padding-bottom: 15px; margin-bottom: 25px; }
        .panel { 
            background: var(--card); border: 1px solid rgba(0, 210, 255, 0.2); 
            border-radius: 15px; padding: 20px; backdrop-filter: blur(10px); box-shadow: 0 0 20px rgba(0,0,0,0.5);
        }
        .grid-form { display: grid; grid-template-columns: 1fr 1fr 120px auto; gap: 10px; margin-bottom: 20px; }
        input { 
            background: rgba(0,0,0,0.4); border: 1px solid rgba(0, 210, 255, 0.3); 
            padding: 12px; border-radius: 8px; color: #fff; outline: none;
        }
        .btn-gen { 
            background: linear-gradient(90deg, #00d2ff, #3a7bd5); color: white; 
            border: none; border-radius: 8px; padding: 12px 20px; font-weight: bold; cursor: pointer;
        }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { text-align: left; color: var(--muted); font-size: 12px; padding: 10px; border-bottom: 1px solid rgba(0,210,255,0.1); }
        td { padding: 15px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .key { color: var(--accent); font-family: monospace; font-weight: bold; background: rgba(0,210,255,0.1); padding: 4px 8px; border-radius: 4px; }
        .status-on { color: var(--green); }
        .status-off { color: var(--red); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin:0; font-size:24px; color:var(--accent); text-shadow: 0 0 10px var(--accent);">⚡ CYBER-ADMIN v1.0</h1>
        </div>

        <div class="panel">
            <div class="grid-form">
                <input type="text" id="nome" placeholder="Nome do Cliente">
                <input type="text" id="email" placeholder="E-mail (Opcional)">
                <input type="number" id="dias" value="30">
                <button class="btn-gen" onclick="gerar()">GERAR CHAVE</button>
            </div>

            <table>
                <thead>
                    <tr><th>CLIENTE</th><th>CHAVE SERIAL</th><th>VENCIMENTO</th><th>STATUS</th></tr>
                </thead>
                <tbody id="lista"></tbody>
            </table>
        </div>
    </div>

    <script>
        async function carregar() {
            const r = await fetch('/admin/lista');
            const dados = await r.json();
            document.getElementById('lista').innerHTML = dados.map(u => `
                <tr>
                    <td>${u.nome}</td>
                    <td><span class="key">${u.chave}</span></td>
                    <td>${u.expira ? new Date(u.expira).toLocaleDateString() : 'VITALÍCIO'}</td>
                    <td class="${u.ativo ? 'status-on' : 'status-off'}">${u.ativo ? '● ATIVO' : '● BLOQUEADO'}</td>
                </tr>
            `).join('');
        }

        async function gerar() {
            const nome = document.getElementById('nome').value;
            const dias = document.getElementById('dias').value;
            if(!nome) return alert('Digite o nome!');
            await fetch('/admin/novo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome, dias})
            });
            carregar();
        }
        carregar();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_AZUL)

@app.route("/api/validar", methods=["POST"])
def validar():
    chave = request.json.get("chave")
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
    u = cur.fetchone()
    cur.close(); conn.close()
    
    if u and u['ativo']:
        if u['expira'] and u['expira'] < datetime.now().date():
            return jsonify({"ok": False, "msg": "Expirada"}), 403
        return jsonify({"ok": True, "nome": u['nome']})
    return jsonify({"ok": False, "msg": "Invalida"}), 403

@app.route("/admin/lista")
def lista():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios ORDER BY id DESC")
    users = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(users)

@app.route("/admin/novo", methods=["POST"])
def novo():
    d = request.json
    chave = gerar_serial()
    exp = datetime.now().date() + timedelta(days=int(d['dias']))
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (nome, chave, expira, ativo) VALUES (%s, %s, %s, True)", (d['nome'], chave, exp))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True})

@app.before_request
def setup():
    if not hasattr(app, 'init_done'):
        conn = get_db(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nome TEXT, chave TEXT UNIQUE, expira DATE, ativo BOOLEAN DEFAULT TRUE)")
        conn.commit(); cur.close(); conn.close()
        app.init_done = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
