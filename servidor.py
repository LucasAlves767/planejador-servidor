from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# 1. BANCO DE DADOS
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# 2. LAYOUT DO PAINEL (DESIGN BRUNA/LUCS)
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>Admin Lucs | Gestão de Licenças</title>
    <style>
        :root { --bg: #042017; --accent: #29ff9a; --card: rgba(255,255,255,0.03); --text: #e8f7f1; }
        body { background: #042017; color: var(--text); font-family: 'Segoe UI', sans-serif; padding: 20px; margin: 0; }
        .container { max-width: 1000px; margin: auto; }
        .panel { background: var(--card); border: 1px solid rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; backdrop-filter: blur(10px); }
        h1 { color: var(--accent); margin-bottom: 5px; }
        .grid-inputs { display: grid; grid-template-columns: 1fr 1fr 100px auto; gap: 10px; margin-bottom: 20px; }
        input { background: #000; border: 1px solid #333; padding: 12px; border-radius: 8px; color: #fff; }
        button { cursor: pointer; border-radius: 8px; font-weight: bold; padding: 10px 20px; border: none; }
        .btn-main { background: var(--accent); color: #012216; }
        .btn-status { padding: 5px 10px; font-size: 11px; }
        .on { background: #2ecc71; color: #fff; }
        .off { background: #e74c3c; color: #fff; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th { text-align: left; color: #9aa6a6; font-size: 12px; padding: 10px; border-bottom: 1px solid #222; }
        td { padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 14px; }
        code { color: var(--accent); background: rgba(0,0,0,0.3); padding: 3px 6px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Gerenciador Lucs</h1>
        <p style="color:#9aa6a6; margin-bottom:20px;">Controle de acessos, logs e expiração de licenças.</p>
        
        <div class="panel">
            <div class="grid-inputs">
                <input type="text" id="nome" placeholder="Cliente">
                <input type="text" id="chave" placeholder="Chave">
                <input type="number" id="dias" placeholder="Dias" value="30">
                <button class="btn-main" onclick="criar()">GERAR ACESSO</button>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>CLIENTE</th>
                        <th>CHAVE</th>
                        <th>VENCIMENTO</th>
                        <th>ÚLTIMO ACESSO</th>
                        <th>STATUS</th>
                        <th>AÇÃO</th>
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
                    <td><b>${u.nome}</b></td>
                    <td><code>${u.chave}</code></td>
                    <td>${u.expira ? new Date(u.expira).toLocaleDateString() : 'Vitalício'}</td>
                    <td style="color:#9aa6a6">${u.ultimo_acesso ? new Date(u.ultimo_acesso).toLocaleString() : 'Nunca'}</td>
                    <td>
                        <button class="btn-status ${u.ativo ? 'on' : 'off'}" onclick="toggle('${u.chave}')">
                            ${u.ativo ? 'ATIVO' : 'BLOQUEADO'}
                        </button>
                    </td>
                    <td><button onclick="deletar('${u.chave}')" style="background:none; color:#ff5f6d; cursor:pointer; border:none;">Excluir</button></td>
                </tr>
            `).join('');
        }

        async function criar() {
            const nome = document.getElementById('nome').value;
            const chave = document.getElementById('chave').value;
            const dias = document.getElementById('dias').value;
            await fetch('/admin/criar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome, chave, dias})
            });
            carregar();
        }

        async function toggle(chave) {
            await fetch('/admin/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({chave})
            });
            carregar();
        }

        async function deletar(chave) {
            if(confirm('Apagar chave?')) {
                await fetch('/admin/deletar', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({chave}) });
                carregar();
            }
        }
        carregar();
    </script>
</body>
</html>
"""

# 3. ROTAS LOGIC
@app.route("/")
def home():
    return send_file('planejador.html') if os.path.exists('planejador.html') else "Servidor ON"

@app.route("/admin-sistema")
def admin():
    return render_template_string(PAINEL_HTML)

@app.route("/api/validar", methods=["POST"])
def validar():
    dados = request.json or {}
    chave = dados.get("chave", "").strip()
    conn = get_db()
    cur = conn.cursor()
    
    # Busca chave e verifica se está ativa e se não venceu
    cur.execute("SELECT nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
    user = cur.fetchone()
    
    if user:
        # Verifica expiração
        vencido = False
        if user['expira'] and user['expira'] < datetime.now().date():
            vencido = True
        
        if user['ativo'] and not vencido:
            # REGISTRA O LOG DE ACESSO (HORA QUE ABRIU O EXE)
            cur.execute("UPDATE usuarios SET ultimo_acesso = %s WHERE chave = %s", (datetime.now(), chave))
            conn.commit()
            return jsonify({"ok": True, "nome": user['nome']})
        
        msg = "Licença Vencida" if vencido else "Acesso Bloqueado pelo Administrador"
        return jsonify({"ok": False, "msg": msg}), 403
    
    return jsonify({"ok": False, "msg": "Chave Inexistente"}), 401

@app.route("/admin/dados")
def admin_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome, chave, ativo, expira, ultimo_acesso FROM usuarios ORDER BY id DESC")
    res = cur.fetchall()
    return jsonify(res)

@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    d = request.json
    vencimento = datetime.now().date() + timedelta(days=int(d['dias']))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (nome, chave, expira, ativo) VALUES (%s, %s, %s, True)", (d['nome'], d['chave'], vencimento))
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
        # CRIA A TABELA COM TODAS AS COLUNAS NOVAS
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT,
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
