"""
SERVIDOR DE LICENÇAS — VERSÃO DESIGN PREMIUM (BRUNA/LUCS)
"""
from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
import os

app = Flask(__name__)

# 1. CONFIGURAÇÃO DO BANCO
_db_url = os.environ.get("DATABASE_URL", "")
DATABASE_URL = _db_url.replace("postgres://", "postgresql://", 1)

def get_db():
    # Usamos RealDictCursor para o Python entender os nomes das colunas do banco
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# 2. O SEU LAYOUT PERSONALIZADO (PAINEL ADMIN)
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Admin Lucs — Gerenciador de Licenças</title>
    <style>
        :root {
            --bg-a: #042017; --bg-b: #063426; --bg-c: #0b2f22;
            --accent-start: #29ff9a; --accent-end: #66ffb0;
            --text-color: #e8f7f1; --muted: #9aa6a6;
            --page-bg: linear-gradient(135deg, var(--bg-a) 0%, var(--bg-b) 45%, var(--bg-c) 100%);
        }
        body {
            margin: 0; font-family: 'Segoe UI', Roboto, sans-serif;
            background: var(--page-bg); color: var(--text-color);
            min-height: 100vh; padding: 20px;
        }
        .container { max-width: 900px; margin: auto; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        h1 { color: var(--accent-start); margin: 0; font-size: 24px; }
        
        .panel {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 15px; padding: 20px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }
        
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        input {
            background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1);
            padding: 12px; border-radius: 8px; color: white; flex: 1; min-width: 200px;
        }
        .btn {
            background: linear-gradient(90deg, var(--accent-start), var(--accent-end));
            color: #012216; border: none; padding: 12px 25px;
            border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.3s;
        }
        .btn:hover { transform: translateY(-2px); opacity: 0.9; }
        .btn-del { background: #ff5f6d; color: white; padding: 5px 10px; font-size: 12px; }

        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th { text-align: left; color: var(--muted); font-size: 13px; padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        td { padding: 15px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        code { background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; color: var(--accent-end); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Painel de Licenças</h1>
                <div style="color:var(--muted); font-size:13px;">Gerenciamento de Clientes e Chaves</div>
            </div>
            <button class="btn" onclick="location.href='/'">Ver Planejador</button>
        </header>

        <div class="panel">
            <div class="input-group">
                <input type="text" id="nome" placeholder="Nome do Cliente (Ex: Bruna)">
                <input type="text" id="chave" placeholder="Chave de Acesso">
                <button class="btn" onclick="criarAcesso()">➕ Gerar Acesso</button>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>CLIENTE</th>
                        <th>CHAVE DE ATIVAÇÃO</th>
                        <th>AÇÕES</th>
                    </tr>
                </thead>
                <tbody id="tabelaCorpo"></tbody>
            </table>
        </div>
    </div>

    <script>
        async function carregar() {
            const res = await fetch('/admin/dados');
            const dados = await res.json();
            const corpo = document.getElementById('tabelaCorpo');
            corpo.innerHTML = dados.map(u => `
                <tr>
                    <td>${u.nome}</td>
                    <td><code>${u.chave}</code></td>
                    <td><button class="btn btn-del" onclick="deletar('${u.chave}')">Excluir</button></td>
                </tr>
            `).join('');
        }

        async function criarAcesso() {
            const nome = document.getElementById('nome').value;
            const chave = document.getElementById('chave').value;
            if(!nome || !chave) return alert('Preencha nome e chave!');
            
            await fetch('/admin/criar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome, chave})
            });
            document.getElementById('nome').value = '';
            document.getElementById('chave').value = '';
            carregar();
        }

        async function deletar(chave) {
            if(confirm('Remover este acesso?')) {
                await fetch('/admin/deletar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({chave})
                });
                carregar();
            }
        }
        carregar();
    </script>
</body>
</html>
"""

# 3. ROTAS DO SERVIDOR

@app.route("/")
def index():
    # Entrega o seu planejador.html original
    if os.path.exists('planejador.html'):
        return send_file('planejador.html')
    return "<h1>Servidor Ativo</h1><p>Arquivo planejador.html não encontrado.</p>"

@app.route("/admin-sistema")
def admin():
    return render_template_string(PAINEL_HTML)

@app.route("/api/validar", methods=["POST"])
def validar():
    # ROTA QUE O SEU .EXE CONSULTA
    try:
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
        return jsonify({"ok": False, "msg": "Chave incorreta"}), 401
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/dados")
def admin_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome, chave FROM usuarios ORDER BY id DESC")
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

@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    chave = request.json.get('chave')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})

# Inicia a tabela se não existir
@app.before_request
def setup():
    if not hasattr(app, 'initialized'):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nome TEXT, chave TEXT UNIQUE)")
        conn.commit()
        cur.close()
        conn.close()
        app.initialized = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
