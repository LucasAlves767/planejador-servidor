"""
SERVIDOR DE LICENÇAS — Versão Final com App Integrado
"""

from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
import secrets, datetime, os

app = Flask(__name__)

# Render usa postgres:// mas psycopg2 precisa de postgresql://
_db_url = os.environ.get("DATABASE_URL", "")
DATABASE_URL = _db_url.replace("postgres://", "postgresql://", 1)

# ───────────────────────────────────────────────
# BANCO DE DADOS
# ───────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id           SERIAL PRIMARY KEY,
                    nome         TEXT NOT NULL,
                    email        TEXT UNIQUE NOT NULL,
                    chave        TEXT UNIQUE NOT NULL,
                    ativo        INTEGER DEFAULT 1,
                    criado_em    TEXT NOT NULL,
                    ultimo_login TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id        SERIAL PRIMARY KEY,
                    email     TEXT,
                    chave     TEXT,
                    ip        TEXT,
                    sucesso   INTEGER,
                    momento   TEXT
                )
            """)
        conn.commit()

try:
    init_db()
    print("✅ Banco inicializado!")
except Exception as e:
    print(f"⚠ Erro no banco: {e}")

# ───────────────────────────────────────────────
# 🚀 ROTA DO APLICATIVO (O QUE O USUÁRIO VÊ)
# ───────────────────────────────────────────────
@app.route("/")
def index():
    # Isso vai abrir o seu arquivo planejador.html que está no GitHub
    try:
        return send_file('planejador.html')
    except:
        return "<h1>Arquivo planejador.html não encontrado no servidor.</h1>", 404

# ───────────────────────────────────────────────
# 🔑 API DE VALIDAÇÃO (O QUE O .EXE CHAMA)
# ───────────────────────────────────────────────
@app.route("/api/validar", methods=["POST"])
def validar():
    dados   = request.json or {}
    chave   = dados.get("chave", "").strip()
    ip      = request.remote_addr
    momento = datetime.datetime.now().isoformat()

    if not chave:
        return jsonify({"ok": False, "msg": "Chave inválida"}), 400

    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM usuarios WHERE chave = %s", (chave,))
            row = cur.fetchone()

            if row:
                sucesso = 1 if row["ativo"] else 0
                cur.execute(
                    "INSERT INTO logs(email,chave,ip,sucesso,momento) VALUES(%s,%s,%s,%s,%s)",
                    (row["email"], chave, ip, sucesso, momento)
                )
                if row["ativo"]:
                    cur.execute(
                        "UPDATE usuarios SET ultimo_login=%s WHERE chave=%s",
                        (momento, chave)
                    )
                conn.commit()

                if row["ativo"]:
                    return jsonify({"ok": True, "nome": row["nome"], "email": row["email"]})
                else:
                    return jsonify({"ok": False, "msg": "Acesso bloqueado"})
            else:
                cur.execute(
                    "INSERT INTO logs(email,chave,ip,sucesso,momento) VALUES(%s,%s,%s,%s,%s)",
                    ("desconhecido", chave, ip, 0, momento)
                )
                conn.commit()
                return jsonify({"ok": False, "msg": "Chave não encontrada"})

# ───────────────────────────────────────────────
# 🛠️ PAINEL ADMIN (ROTA SECRETA PARA VOCÊ)
# ───────────────────────────────────────────────
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>Gerenciador de Chaves</title>
<style>
  body { background: #040d0a; color: #29ff9a; font-family: monospace; padding: 20px; }
  /* (Mantenha o CSS do seu painel aqui) */
</style>
</head>
<body>
    <div id="adminGuard">
       <h2>🔐 Acesso Admin</h2>
       <input type="password" id="adminPass" placeholder="Senha..."/>
       <button onclick="checkPass()">Entrar</button>
    </div>
    <div id="conteudo" style="display:none">
       <h1>Painel de Licenças</h1>
       </div>
    <script>
      const ADMIN_PASSWORD = "admin123"; // TROQUE ESSA SENHA!
      function checkPass(){
          if(document.getElementById('adminPass').value === ADMIN_PASSWORD){
              document.getElementById('adminGuard').style.display = 'none';
              document.getElementById('conteudo').style.display = 'block';
              carregar();
          }
      }
      // ... suas funções de carregar(), criarUsuario(), etc ...
    </script>
</body>
</html>
"""

# Mudei a rota para não conflitar com o App
@app.route("/admin-sistema")
def painel():
    return render_template_string(PAINEL_HTML)

# --- ROTAS DE DADOS DO ADMIN (MANTIDAS) ---
@app.route("/admin/dados")
def admin_dados():
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM usuarios ORDER BY criado_em DESC")
            usuarios = [dict(r) for r in cur.fetchall()]
            hoje = datetime.date.today().isoformat()
            cur.execute("SELECT COUNT(*) as c FROM logs WHERE momento LIKE %s", (hoje+"%",))
            logs_hoje = cur.fetchone()["c"]
            cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50")
            logs = [dict(r) for r in cur.fetchall()]
    return jsonify({"usuarios": usuarios, "total": len(usuarios), "ativos": sum(1 for u in usuarios if u["ativo"]), "logs_hoje": logs_hoje, "logs": logs})

@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    dados = request.json or {}
    nome, email = dados.get("nome",""), dados.get("email","")
    chave = secrets.token_urlsafe(24)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO usuarios(nome,email,chave,ativo,criado_em) VALUES(%s,%s,%s,1,%s)", (nome, email, chave, datetime.datetime.now().isoformat()))
            conn.commit()
        return jsonify({"ok": True, "chave": chave})
    except: return jsonify({"ok": False, "msg": "E-mail duplicado"})

@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    dados = request.json or {}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ativo=%s WHERE id=%s", (dados.get("ativo"), dados.get("id")))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    dados = request.json or {}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE id=%s", (dados.get("id"),))
        conn.commit()
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
