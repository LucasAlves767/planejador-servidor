from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# 1. CONEXÃO BANCO
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# 2. PAINEL AZUL FUTURISTA
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>CyberAdmin | Gestão de Licenças</title>
    <style>
        :root { 
            --bg: #050a14; 
            --accent: #00d2ff; 
            --accent-glow: #0084ff;
            --card: rgba(10, 20, 40, 0.8); 
            --text: #e0f2ff; 
            --muted: #6a89a7;
        }
        body { 
            background: radial-gradient(circle at top, #0a1931 0%, #050a14 100%); 
            color: var(--text); 
            font-family: 'Segoe UI', system-ui, sans-serif; 
            padding: 30px; margin: 0; min-height: 100vh;
        }
        .container { max-width: 1100px; margin: auto; }
        .panel { 
            background: var(--card); 
            border: 1px solid rgba(0, 210, 255, 0.2); 
            border-radius: 20px; padding: 25px; 
            backdrop-filter: blur(15px);
            box-shadow: 0 0 30px rgba(0, 132, 255, 0.1);
        }
        h1 { 
            color: var(--accent); 
            text-transform: uppercase; letter-spacing: 2px;
            text-shadow: 0 0 15px var(--accent-glow);
            margin-bottom: 5px;
        }
        .grid-inputs { 
            display: grid; 
            grid-template-columns: 1.5fr 1.5fr 1.5fr 80px auto; 
            gap: 12px; margin-bottom: 25px; 
        }
        input { 
            background: rgba(0, 0, 0, 0.4); 
            border: 1px solid rgba(0, 210, 255, 0.3); 
            padding: 12px; border-radius: 10px; color: #fff;
            transition: 0.3s;
        }
        input:focus { border-color: var(--accent); outline: none; box-shadow: 0 0 10px var(--accent-glow); }
        
        .btn-main { 
            background: linear-gradient(90deg, #00d2ff, #3a7bd5); 
            color: #fff; border-radius: 10px; font-weight: bold; 
            padding: 10px 20px; border: none; cursor: pointer;
            box-shadow: 0 0 15px rgba(0, 210, 255, 0.4);
            transition: 0.3s;
        }
        .btn-main:hover { transform: scale(1.02); box-shadow: 0 0 25px var(--accent-glow); }

        .btn-status { 
            padding: 6px 12px; font-size: 11px; border-radius: 20px; border: none; font-weight: 800; cursor: pointer;
        }
        .on { background: rgba(0, 210, 255, 0.2); color: #00d2ff; border: 1px solid #00d2ff; }
        .off { background: rgba(255, 60, 60, 0.1); color: #ff3c3c; border: 1px solid #ff3c3c; }

        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th { text-align: left; color: var(--muted); font-size: 12px; padding: 12px; border-bottom: 2px solid rgba(0, 210, 255, 0.1); }
        td { padding: 15px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); font-size: 14px; }
        code { color: #fff; background: rgba(0, 210, 255, 0.2); padding: 4px 8px; border-radius: 5px; border: 1px solid rgba(0, 210, 255, 0.3); }
        .email-text { color: var(--muted); font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Protocolo de Licenças — Lucs</h1>
        <p style="color:var(--muted); margin-bottom:25px;">Interface de Gerenciamento Neon v3.0</p>
        
        <div class="panel">
            <div class="grid-inputs">
                <input type="text" id="nome" placeholder="Nome do Cliente">
                <input type="email" id="email" placeholder="E-mail">
                <input type="text" id="chave" placeholder="Chave de Acesso">
                <input type="number" id="dias" placeholder="Dias" value="30">
                <button class="btn-main" onclick="criar()">GERAR ACESSO</button>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>USUÁRIO / E-MAIL</th>
                        <th>CHAVE NEON</th>
                        <th>VENCIMENTO</th>
                        <th>ÚLTIMO LOGIN</th>
                        <th>STATUS</th>
                        <th>SISTEMA</th>
                    </tr>
                </thead>
                <tbody id="tabela"></tbody>
            </table>
        </div>
    </div>

    <script>
        async function carregar() {
            const r = await fetch('/admin/dados');
            const dados = await r.json();
            document.getElementById('tabela').innerHTML = dados.map(u => `
                <tr>
                    <td>
                        <b>${u.nome}</b><br>
                        <span class="email-text">${u.email || 'N/A'}</span>
                    </td>
                    <td><code>${u.chave}</code></td>
                    <td>${u.expira ? new Date(u.expira).toLocaleDateString() : 'VITALÍCIO'}</td>
                    <td style="color:var(--muted)">${u.ultimo_acesso ? new Date(u.ultimo_acesso).toLocaleString() : '--/--'}</td>
                    <td>
                        <button class="btn-status ${u.ativo ? 'on' : 'off'}" onclick="toggle('${u.chave}')">
                            ${u.ativo ? 'ATIVO' : 'BLOQUEADO'}
                        </button>
                    </td>
                    <td><button onclick="deletar('${u.chave}')" style="background:none; color:#ff3c3c; cursor:pointer; border:none; font-size:12px;">[REMOVER]</button></td>
                </tr>
            `).join('');
        }

        async function criar() {
            const nome = document.getElementById('nome').value;
            const email = document.getElementById('email').value;
            const chave = document.getElementById('chave').value;
            const dias = document.getElementById('dias').value;
            if(!nome || !chave) return alert('Campos obrigatórios!');
            
            await fetch('/admin/criar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome, email, chave, dias})
            });
            carregar();
        }

        async function toggle(chave) {
            await fetch('/admin/toggle', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({chave}) });
            carregar();
        }

        async function deletar(chave) {
            if(confirm('Terminar acesso permanentemente?')) {
                await fetch('/admin/deletar', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({chave}) });
                carregar();
            }
        }
        carregar();
    </script>
</body>
</html>
"""

# 3. ROTAS E LÓGICA (Mantidas para o seu EXE funcionar)

@app.route("/")
def home():
    return send_file('planejador.html') if os.path.exists('planejador.html') else "System Online"

@app.route("/admin-sistema")
def admin():
    return render_template_string(PAINEL_HTML)

@app.route("/api/validar", methods=["POST"])
def validar():
    dados = request.json or {}
    chave = dados.get("chave", "").strip()
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
    user = cur.fetchone()
    
    if user:
        vencido = False
        if user['expira'] and user['expira'] < datetime.now().date():
            vencido = True
        
        if user['ativo'] and not vencido:
            # LOG DE ACESSO
            cur.execute("UPDATE usuarios SET ultimo_acesso = %s WHERE chave = %s", (datetime.now(), chave))
            conn.commit()
            return jsonify({"ok": True, "nome": user['nome']})
        
        msg = "Licença Expirada" if vencido else "Acesso Revogado"
        return jsonify({"ok": False, "msg": msg}), 403
    
    return jsonify({"ok": False, "msg": "Chave Inválida"}), 401

@app.route("/admin/dados")
def admin_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome, email, chave, ativo, expira, ultimo_acesso FROM usuarios ORDER BY id DESC")
    return jsonify(cur.fetchall())

@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    d = request.json
    vencimento = datetime.now().date() + timedelta(days=int(d['dias']))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (nome, email, chave, expira, ativo) VALUES (%s, %s, %s, %s, True)", 
                (d['nome'], d.get('email'), d['chave'], vencimento))
    conn.commit()
    return jsonify({"ok": True})

@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    chave = request.json.get('chave')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE usuarios SET ativo = NOT ativo WHERE chave = %s", (chave,))
    conn.commit()
    return jsonify({"ok": True})

@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    chave = request.json.get('chave')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))
    conn.commit()
    return jsonify({"ok": True})

@app.before_request
def setup():
    if not hasattr(app, 'init'):
        conn = get_db()
        cur = conn.cursor()
        # Garante a coluna EMAIL caso não exista
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT,
                email TEXT,
                chave TEXT UNIQUE,
                ativo BOOLEAN DEFAULT TRUE,
                expira DATE,
                ultimo_acesso TIMESTAMP
            )
        """)
        conn.commit()
        app.init = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
