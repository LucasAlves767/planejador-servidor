from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import os
import random
import string

app = Flask(__name__)

# 1. CONEXÃO AO BANCO DE DADOS (RENDER / POSTGRES)
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def gerar_chave_automatica():
    caracteres = string.ascii_uppercase + string.digits
    p1 = ''.join(random.choices(caracteres, k=4))
    p2 = ''.join(random.choices(caracteres, k=4))
    return f"LUCS-{p1}-{p2}"

# 2. PAINEL AZUL FUTURISTA COMPLETO
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>CyberAdmin v7.0 | Planejador Lucs</title>
    <style>
        :root { 
            --bg: #050a14; --accent: #00d2ff; --accent-glow: #0084ff;
            --card: rgba(10, 20, 40, 0.8); --text: #e0f2ff; --muted: #6a89a7;
            --red: #ff3c3c; --green: #00ffaa;
        }
        body { 
            background: radial-gradient(circle at top, #0a1931 0%, #050a14 100%); 
            color: var(--text); font-family: 'Segoe UI', sans-serif; 
            padding: 20px; margin: 0; min-height: 100vh;
        }
        .container { max-width: 1200px; margin: auto; }
        
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid rgba(0, 210, 255, 0.2); padding-bottom: 15px; }
        h1 { color: var(--accent); text-transform: uppercase; text-shadow: 0 0 15px var(--accent-glow); margin: 0; font-size: 24px; }

        /* Estastísticas */
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: var(--card); border: 1px solid rgba(0, 210, 255, 0.1); border-radius: 12px; padding: 20px; text-align: center; backdrop-filter: blur(10px); }
        .stat-num { font-size: 28px; font-weight: bold; color: var(--accent); display: block; }
        .stat-lbl { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }

        /* Form */
        .panel { background: var(--card); border: 1px solid rgba(0, 210, 255, 0.2); border-radius: 15px; padding: 25px; margin-bottom: 30px; }
        .grid-inputs { display: grid; grid-template-columns: 2fr 2fr 100px auto; gap: 12px; }
        input { background: rgba(0, 0, 0, 0.5); border: 1px solid rgba(0, 210, 255, 0.3); padding: 12px; border-radius: 8px; color: #fff; outline: none; }
        input:focus { border-color: var(--accent); }
        .btn-main { background: linear-gradient(90deg, #00d2ff, #3a7bd5); color: #fff; border-radius: 8px; font-weight: bold; padding: 12px 20px; border: none; cursor: pointer; transition: 0.3s; }
        .btn-main:hover { transform: translateY(-2px); box-shadow: 0 0 20px var(--accent-glow); }

        /* Tabela */
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th { text-align: left; color: var(--muted); font-size: 12px; padding: 12px; border-bottom: 2px solid rgba(0, 210, 255, 0.1); }
        td { padding: 15px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); font-size: 14px; }
        .chave-box { color: var(--accent); background: rgba(0, 210, 255, 0.1); padding: 5px 10px; border-radius: 5px; font-weight: bold; cursor: pointer; border: 1px solid rgba(0, 210, 255, 0.2); }
        
        .badge { padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; border: none; cursor: pointer; }
        .badge-on { background: rgba(0, 255, 170, 0.1); color: var(--green); border: 1px solid var(--green); }
        .badge-off { background: rgba(255, 60, 60, 0.1); color: var(--red); border: 1px solid var(--red); }

        /* Logs */
        .logs-container { background: rgba(0, 0, 0, 0.3); border-radius: 10px; padding: 15px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 12px; }
        .log-line { border-bottom: 1px solid rgba(255,255,255,0.05); padding: 5px 0; display: flex; gap: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔐 CyberAdmin Protocol</h1>
            <div id="relogio" style="color: var(--accent)">--:--:--</div>
        </header>

        <div class="stats-grid">
            <div class="stat-card"><span class="stat-num" id="s-total">0</span><span class="stat-lbl">Usuários</span></div>
            <div class="stat-card"><span class="stat-num" id="s-ativos" style="color: var(--green)">0</span><span class="stat-lbl">Ativos</span></div>
            <div class="stat-card"><span class="stat-num" id="s-bloq" style="color: var(--red)">0</span><span class="stat-lbl">Bloqueados</span></div>
            <div class="stat-card"><span class="stat-num" id="s-hoje">0</span><span class="stat-lbl">Logins Hoje</span></div>
        </div>

        <div class="panel">
            <h3 style="margin-top:0; color:var(--accent); font-size:14px; margin-bottom:15px">⚡ GERAR NOVO ACESSO</h3>
            <div class="grid-inputs">
                <input type="text" id="nome" placeholder="Nome do Cliente">
                <input type="email" id="email" placeholder="E-mail">
                <input type="number" id="dias" value="30">
                <button class="btn-main" onclick="criar()">GERAR AGORA</button>
            </div>
        </div>

        <div class="panel">
            <h3 style="margin-top:0; color:var(--accent); font-size:14px">👥 GESTÃO DE LICENÇAS</h3>
            <table>
                <thead>
                    <tr>
                        <th>CLIENTE</th>
                        <th>CHAVE</th>
                        <th>EXPIRA EM</th>
                        <th>STATUS</th>
                        <th>AÇÕES</th>
                    </tr>
                </thead>
                <tbody id="tabela"></tbody>
            </table>
        </div>

        <div class="panel">
            <h3 style="margin-top:0; color:var(--accent); font-size:14px">📋 LOGS DE SISTEMA (ÚLTIMOS 30)</h3>
            <div class="logs-container" id="logs"></div>
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
                    <td style="color: ${u.expira && new Date(u.expira) < new Date() ? 'var(--red)' : 'inherit'}">
                        ${u.expira ? new Date(u.expira).toLocaleDateString() : 'Vitalício'}
                    </td>
                    <td>
                        <button class="badge ${u.ativo ? 'badge-on' : 'badge-off'}" onclick="toggle('${u.chave}')">
                            ${u.ativo ? 'ATIVO' : 'BLOQUEADO'}
                        </button>
                    </td>
                    <td><button onclick="deletar('${u.chave}')" style="background:none; border:none; color:var(--red); cursor:pointer;">Excluir</button></td>
                </tr>
            `).join('');

            document.getElementById('logs').innerHTML = d.logs.map(l => `
                <div class="log-line">
                    <span style="color:var(--muted)">[${new Date(l.momento).toLocaleString()}]</span>
                    <span style="color:${l.sucesso ? 'var(--green)' : 'var(--red)'}">${l.sucesso ? 'SUCCESS' : 'DENIED'}</span>
                    <span>KEY: ${l.chave}</span>
                </div>
            `).join('');
        }

        async function criar() {
            const nome = document.getElementById('nome').value;
            const email = document.getElementById('email').value;
            const dias = document.getElementById('dias').value;
            if(!nome) return alert('Nome é obrigatório!');
            const res = await fetch('/admin/criar-auto', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome, email, dias})
            });
            const data = await res.json();
            if(data.ok) {
                prompt('COPIE A CHAVE GERADA:', data.chave);
                carregar();
            }
        }

        async function toggle(chave) { await fetch('/admin/toggle', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({chave})}); carregar(); }
        async function deletar(chave) { if(confirm('Apagar permanentemente?')) { await fetch('/admin/deletar', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({chave})}); carregar(); } }
        
        setInterval(() => { document.getElementById('relogio').innerText = new Date().toLocaleTimeString(); }, 1000);
        carregar();
        setInterval(carregar, 20000);
    </script>
</body>
</html>
"""

# 3. ROTAS E LÓGICA (BACK-END)
@app.route("/")
def admin_page():
    return render_template_string(PAINEL_HTML)

@app.route("/admin/dados")
def admin_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios ORDER BY id DESC")
    users = cur.fetchall()
    cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 30")
    logs = cur.fetchall()
    hoje = datetime.now().strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(*) FROM logs WHERE momento::text LIKE %s AND sucesso = 1", (hoje+"%",))
    logs_hoje = cur.fetchone()['count']
    cur.close(); conn.close()
    return jsonify({"usuarios": users, "logs": logs, "logs_hoje": logs_hoje})

@app.route("/admin/criar-auto", methods=["POST"])
def criar_auto():
    d = request.json
    chave = gerar_chave_automatica()
    expira = datetime.now().date() + timedelta(days=int(d.get('dias', 30)))
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (nome, email, chave, expira, ativo) VALUES (%s, %s, %s, %s, True)", (d['nome'], d['email'], chave, expira))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True, "chave": chave})

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
    conn.commit()
    
    if sucesso:
        return jsonify({"ok": True, "nome": user['nome']})
    return jsonify({"ok": False, "msg": "Acesso Negado"}), 403

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
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY, nome TEXT, email TEXT, chave TEXT UNIQUE, ativo BOOLEAN DEFAULT TRUE, expira DATE
            );
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY, chave TEXT, sucesso INTEGER, momento TIMESTAMP
            );
        """)
        conn.commit(); cur.close(); conn.close()
        app.init_done = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
