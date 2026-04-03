from flask import Flask, request, jsonify, render_template_string
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import os
import random
import string

app = Flask(__name__)

# 1. CONEXÃO AO BANCO (RENDER / POSTGRES)
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def gerar_chave_automatica():
    caracteres = string.ascii_uppercase + string.digits
    p1 = ''.join(random.choices(caracteres, k=4))
    p2 = ''.join(random.choices(caracteres, k=4))
    return f"LUCS-{p1}-{p2}"

# 2. SEU LAYOUT AZUL COM OS ACRÉSCIMOS DE LOGS
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>CyberAdmin | Lucs Tech</title>
    <style>
        :root { --bg: #050a14; --accent: #00d2ff; --card: rgba(10, 20, 40, 0.9); --text: #e0f2ff; --muted: #6a89a7; --red: #ff3c3c; --green: #00ffaa; }
        body { background: radial-gradient(circle at top, #0a1931 0%, #050a14 100%); color: var(--text); font-family: 'Segoe UI', sans-serif; padding: 20px; margin: 0; }
        .container { max-width: 1100px; margin: auto; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: var(--card); border: 1px solid rgba(0, 210, 255, 0.1); border-radius: 12px; padding: 15px; text-align: center; }
        .stat-num { font-size: 24px; font-weight: bold; color: var(--accent); display: block; }
        .panel { background: var(--card); border: 1px solid rgba(0, 210, 255, 0.2); border-radius: 15px; padding: 20px; margin-bottom: 25px; }
        .grid-inputs { display: grid; grid-template-columns: 2fr 2fr 100px auto; gap: 10px; }
        input { background: rgba(0, 0, 0, 0.5); border: 1px solid rgba(0, 210, 255, 0.3); padding: 10px; border-radius: 8px; color: #fff; outline: none; }
        .btn-main { background: linear-gradient(90deg, #00d2ff, #3a7bd5); color: #fff; border-radius: 8px; font-weight: bold; padding: 10px; border: none; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { text-align: left; color: var(--muted); padding: 10px; border-bottom: 1px solid rgba(0, 210, 255, 0.2); }
        td { padding: 12px 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); }
        .chave-box { color: #ffd166; background: rgba(255, 209, 102, 0.1); padding: 4px 8px; border-radius: 5px; cursor: pointer; font-family: monospace; border: 1px solid rgba(255, 209, 102, 0.2); }
        .badge { padding: 4px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; border: none; cursor: pointer; }
        .badge-on { background: var(--green); color: #000; }
        .badge-off { background: var(--red); color: #fff; }
        .logs-box { background: rgba(0,0,0,0.5); border-radius: 10px; padding: 15px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #88c0d0; }
    </style>
</head>
<body>
    <div class="container">
        <h1 style="color:var(--accent); text-transform:uppercase; font-size:20px; margin-bottom:20px;">⚡ Painel de Controle</h1>

        <div class="stats-grid">
            <div class="stat-card"><span class="stat-num" id="s-total">0</span><span style="font-size:10px; color:var(--muted)">TOTAL</span></div>
            <div class="stat-card"><span class="stat-num" id="s-ativos" style="color:var(--green)">0</span><span style="font-size:10px; color:var(--muted)">ATIVOS</span></div>
            <div class="stat-card"><span class="stat-num" id="s-bloq" style="color:var(--red)">0</span><span style="font-size:10px; color:var(--muted)">BLOQUEADOS</span></div>
            <div class="stat-card"><span class="stat-num" id="s-hoje">0</span><span style="font-size:10px; color:var(--muted)">LOGINS HOJE</span></div>
        </div>

        <div class="panel">
            <div class="grid-inputs">
                <input type="text" id="nome" placeholder="Nome do Cliente">
                <input type="email" id="email" placeholder="E-mail">
                <input type="number" id="dias" value="30">
                <button class="btn-main" onclick="criar()">GERAR ACESSO</button>
            </div>
        </div>

        <div class="panel">
            <table>
                <thead><tr><th>CLIENTE</th><th>CHAVE</th><th>VENCIMENTO</th><th>STATUS</th><th>AÇÃO</th></tr></thead>
                <tbody id="tabela"></tbody>
            </table>
        </div>

        <div class="panel">
            <h3 style="font-size:12px; color:var(--accent); margin-bottom:10px;">HISTÓRICO DE ACESSOS RECENTES</h3>
            <div class="logs-box" id="logs">Carregando logs...</div>
        </div>
    </div>

    <script>
        async function carregar() {
            const res = await fetch('/admin/dados');
            const d = await res.json();
            document.getElementById('s-total').innerText = d.usuarios.length;
            document.getElementById('s-ativos').innerText = d.usuarios.filter(u => u.ativo).length;
            document.getElementById('s-bloq').innerText = d.usuarios.filter(u => !u.ativo).length;
            document.getElementById('s-hoje').innerText = d.logs_hoje;

            document.getElementById('tabela').innerHTML = d.usuarios.map(u => `
                <tr>
                    <td><b>${u.nome}</b><br><small style="color:var(--muted)">${u.email||''}</small></td>
                    <td><span class="chave-box" onclick="navigator.clipboard.writeText('${u.chave}');alert('Copiado!')">${u.chave}</span></td>
                    <td>${u.expira ? new Date(u.expira).toLocaleDateString() : '--'}</td>
                    <td><button class="badge ${u.ativo?'badge-on':'badge-off'}" onclick="toggle('${u.chave}')">${u.ativo?'ATIVO':'BLOQUEADO'}</button></td>
                    <td><button onclick="deletar('${u.chave}')" style="background:none;border:none;color:var(--red);cursor:pointer">Remover</button></td>
                </tr>
            `).join('');

            document.getElementById('logs').innerHTML = d.logs.map(l => `<div>[${new Date(l.momento).toLocaleString()}] ${l.sucesso?'✅':'❌'} CHAVE: ${l.chave}</div>`).join('');
        }
        async function criar() {
            const nome=document.getElementById('nome').value; const email=document.getElementById('email').value; const dias=document.getElementById('dias').value;
            if(!nome) return alert('Nome obrigatório');
            const res = await fetch('/admin/criar-auto', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({nome, email, dias}) });
            if(res.ok) { const data = await res.json(); alert('Gerado: ' + data.chave); carregar(); }
        }
        async function toggle(chave) { await fetch('/admin/toggle', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({chave})}); carregar(); }
        async function deletar(chave) { if(confirm('Excluir?')) { await fetch('/admin/deletar', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({chave})}); carregar(); } }
        carregar(); setInterval(carregar, 15000);
    </script>
</body>
</html>
"""

# --- ROTAS (PRESERVANDO OS ENDEREÇOS) ---
@app.route("/")
@app.route("/admin-sistema") # Se você usava esse endereço, ele continua funcionando
def index():
    return render_template_string(PAINEL_HTML)

@app.route("/api/validar", methods=["POST"])
def validar():
    dados = request.json or {}
    chave = dados.get("chave", "").strip()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
    user = cur.fetchone()
    sucesso = 0
    if user:
        vencido = user['expira'] and user['expira'] < datetime.now().date()
        if user['ativo'] and not vencido: sucesso = 1
    cur.execute("INSERT INTO logs (chave, sucesso, momento) VALUES (%s, %s, %s)", (chave, sucesso, datetime.now()))
    conn.commit(); cur.close(); conn.close()
    if sucesso: return jsonify({"ok": True, "nome": user['nome']})
    return jsonify({"ok": False, "msg": "Negado"}), 403

@app.route("/admin/dados")
def admin_dados():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios ORDER BY id DESC")
    u = cur.fetchall()
    cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 30")
    l = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM logs WHERE momento::date = CURRENT_DATE AND sucesso = 1")
    h = cur.fetchone()['count']
    cur.close(); conn.close()
    return jsonify({"usuarios": u, "logs": l, "logs_hoje": h})

@app.route("/admin/criar-auto", methods=["POST"])
def criar_auto():
    d = request.json
    chave = gerar_chave_automatica()
    exp = datetime.now().date() + timedelta(days=int(d.get('dias', 30)))
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (nome, email, chave, expira, ativo) VALUES (%s, %s, %s, %s, True)", (d['nome'], d.get('email'), chave, exp))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True, "chave": chave})

@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    chave = request.json.get('chave')
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE usuarios SET ativo = NOT ativo WHERE chave = %s", (chave,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True})

@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    chave = request.json.get('chave')
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True})

@app.before_request
def setup():
    if not hasattr(app, 'init_done'):
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nome TEXT, email TEXT, chave TEXT UNIQUE, ativo BOOLEAN DEFAULT TRUE, expira DATE);
            CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, chave TEXT, sucesso INTEGER, momento TIMESTAMP);
        """)
        conn.commit(); cur.close(); conn.close()
        app.init_done = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
