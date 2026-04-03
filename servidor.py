"""
SERVIDOR DE LICENÇAS — VERSÃO PREMIUM 2026
"""
from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
import os

app = Flask(__name__)

# Configuração do Banco (Render)
_db_url = os.environ.get("DATABASE_URL", "")
DATABASE_URL = _db_url.replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# ─── 1. O PAINEL DE CONTROLE (HTML) ───
# Colocamos a variável aqui no topo para o Python não dar "NameError"
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Admin Lucs | Gerenciador</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0b0f19; color: white; padding: 20px; }
        .card { background: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; max-width: 800px; margin: auto; }
        h1 { color: #58a6ff; text-align: center; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; border-bottom: 1px solid #30363d; text-align: left; }
        input, button { padding: 10px; border-radius: 5px; border: none; margin: 5px; }
        button { background: #238636; color: white; cursor: pointer; font-weight: bold; }
        button:hover { background: #2ea043; }
        .btn-del { background: #da3633; }
    </style>
</head>
<body>
    <div class="card">
        <h1>GERENCIADOR DE ACESSOS</h1>
        <div style="text-align: center; margin-bottom: 20px;">
            <input type="text" id="nome" placeholder="Nome do Cliente">
            <input type="text" id="chave" placeholder="Chave Personalizada">
            <button onclick="criar()">GERAR ACESSO</button>
        </div>
        <table>
            <thead>
                <tr><th>Cliente</th><th>Chave</th><th>Ação</th></tr>
            </thead>
            <tbody id="lista"></tbody>
        </table>
    </div>

    <script>
        async function carregar() {
            const res = await fetch('/admin/dados');
            const dados = await res.json();
            const lista = document.getElementById('lista');
            lista.innerHTML = dados.map(u => `
                <tr>
                    <td>${u.nome}</td>
                    <td><code>${u.chave}</code></td>
                    <td><button class="btn-del" onclick="deletar('${u.chave}')">EXCLUIR</button></td>
                </tr>
            `).join('');
        }

        async function criar() {
            const nome = document.getElementById('nome').value;
            const chave = document.getElementById('chave').value;
            await fetch('/admin/criar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome, chave})
            });
            carregar();
        }

        async function deletar(chave) {
            if(confirm('Deseja excluir este acesso?')) {
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

# ─── 2. ROTAS DO SISTEMA (CLIENTE E EXE) ───

@app.route("/")
def abrir_app_online():
    # Tenta abrir o arquivo, se não existir mostra um aviso amigável
    if os.path.exists('planejador.html'):
        return send_file('planejador.html')
    return "<h1>Sistema Lucs Online</h1><p>O Planejador está sendo carregado...</p>"

@app.route("/api/validar", methods=["POST"])
def validar():
    # ESSA ROTA É O QUE O SEU EXE CHAMA. NÃO MUDE O NOME!
    try:
        dados = request.json or {}
        chave_cliente = dados.get("chave", "").strip()
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT nome FROM usuarios WHERE chave = %s", (chave_cliente,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            return jsonify({"ok": True, "nome": user['nome']})
        return jsonify({"ok": False, "msg": "Chave Inválida"}), 401
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

# ─── 3. ROTAS DE ADMINISTRAÇÃO (VOCÊ) ───

@app.route("/admin-sistema")
def painel_gerenciador():
    return render_template_string(PAINEL_HTML)

@app.route("/admin/dados")
def admin_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome, chave FROM usuarios ORDER BY id DESC")
    usuarios = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(usuarios)

@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    dados = request.json
    nome = dados.get('nome')
    chave = dados.get('chave')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (nome, chave) VALUES (%s, %s)", (nome, chave))
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

# Inicialização do Banco (Caso não exista a tabela)
@app.before_request
def init_db():
    if not hasattr(app, 'db_initialized'):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                chave TEXT UNIQUE NOT NULL
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        app.db_initialized = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
