"""
SERVIDOR DE LICENÇAS — Render.com + PostgreSQL
"""

from flask import Flask, request, jsonify, render_template_string
import psycopg2, psycopg2.extras
import secrets, datetime, os

app = Flask(__name__)

# Render injeta DATABASE_URL automaticamente
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
                    id          SERIAL PRIMARY KEY,
                    nome        TEXT NOT NULL,
                    email       TEXT UNIQUE NOT NULL,
                    chave       TEXT UNIQUE NOT NULL,
                    ativo       INTEGER DEFAULT 1,
                    criado_em   TEXT NOT NULL,
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

# ───────────────────────────────────────────────
# API — validação de chave
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
                    return jsonify({"ok": False, "msg": "Acesso bloqueado pelo administrador"})
            else:
                cur.execute(
                    "INSERT INTO logs(email,chave,ip,sucesso,momento) VALUES(%s,%s,%s,%s,%s)",
                    ("desconhecido", chave, ip, 0, momento)
                )
                conn.commit()
                return jsonify({"ok": False, "msg": "Chave não encontrada"})

# ───────────────────────────────────────────────
# PAINEL ADMIN
# ───────────────────────────────────────────────
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Painel Admin — Licenças</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@700;800&display=swap');
  :root{
    --bg:#040d0a; --card:#0a1a14; --border:rgba(41,255,154,0.12);
    --green:#29ff9a; --green-dim:rgba(41,255,154,0.15);
    --red:#ff5f6d; --red-dim:rgba(255,95,109,0.15);
    --yellow:#ffd166; --text:#d4efe5; --muted:#5a8070;
  }
  *{ box-sizing:border-box; margin:0; padding:0; }
  body{ background:var(--bg); color:var(--text); font-family:'JetBrains Mono',monospace; min-height:100vh; }
  header{ padding:28px 36px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; background:linear-gradient(90deg,rgba(41,255,154,0.04),transparent); }
  header h1{ font-family:'Syne',sans-serif; font-size:22px; color:var(--green); }
  header small{ color:var(--muted); font-size:11px; }
  .main{ padding:32px 36px; max-width:1100px; }
  .stats{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:32px; }
  .stat-card{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px 20px; }
  .stat-card .num{ font-size:32px; font-weight:700; color:var(--green); }
  .stat-card .lbl{ font-size:11px; color:var(--muted); margin-top:4px; text-transform:uppercase; letter-spacing:1px; }
  .section{ margin-bottom:32px; }
  .section h2{ font-family:'Syne',sans-serif; font-size:15px; color:var(--green); margin-bottom:14px; }
  .form-row{ display:flex; gap:10px; flex-wrap:wrap; background:var(--card); border:1px solid var(--border); border-radius:12px; padding:16px; }
  .form-row input{ flex:1; min-width:160px; background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:8px; padding:10px 14px; color:var(--text); font-family:inherit; font-size:13px; }
  .form-row input:focus{ outline:none; border-color:var(--green); }
  .form-row input::placeholder{ color:var(--muted); }
  .btn{ padding:10px 20px; border-radius:8px; border:none; cursor:pointer; font-family:inherit; font-weight:700; font-size:13px; transition:all .15s; }
  .btn-green{ background:var(--green); color:#02120a; }
  .btn-green:hover{ filter:brightness(1.1); transform:translateY(-1px); }
  .btn-red{ background:var(--red-dim); color:var(--red); border:1px solid rgba(255,95,109,0.3); }
  .btn-red:hover{ background:var(--red); color:#fff; }
  .btn-yellow{ background:rgba(255,209,102,0.15); color:var(--yellow); border:1px solid rgba(255,209,102,0.3); }
  .btn-yellow:hover{ background:var(--yellow); color:#02120a; }
  .btn-sm{ padding:6px 12px; font-size:12px; }
  table{ width:100%; border-collapse:collapse; font-size:13px; }
  th{ text-align:left; padding:10px 14px; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; border-bottom:1px solid var(--border); }
  td{ padding:12px 14px; border-bottom:1px solid rgba(255,255,255,0.03); vertical-align:middle; }
  tr:hover td{ background:rgba(41,255,154,0.02); }
  .badge{ display:inline-block; padding:4px 10px; border-radius:999px; font-size:11px; font-weight:700; letter-spacing:.5px; }
  .badge-on{ background:var(--green-dim); color:var(--green); }
  .badge-off{ background:var(--red-dim); color:var(--red); }
  .chave-box{ font-family:'JetBrains Mono',monospace; font-size:12px; background:rgba(0,0,0,0.3); padding:4px 8px; border-radius:6px; color:var(--yellow); cursor:pointer; border:1px solid rgba(255,209,102,0.15); user-select:all; }
  .chave-box:hover{ border-color:var(--yellow); }
  .actions{ display:flex; gap:6px; }
  .toast{ position:fixed; bottom:24px; right:24px; background:var(--green); color:#02120a; padding:12px 20px; border-radius:10px; font-weight:700; font-size:13px; opacity:0; transition:opacity .3s; pointer-events:none; z-index:9999; }
  .toast.show{ opacity:1; }
  .logs-box{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px; max-height:280px; overflow-y:auto; font-size:12px; }
  .log-row{ padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.03); display:flex; gap:12px; }
  .log-ok{ color:var(--green); }
  .log-fail{ color:var(--red); }
  .log-time{ color:var(--muted); min-width:160px; }
  #adminGuard{ position:fixed; inset:0; background:var(--bg); display:flex; align-items:center; justify-content:center; z-index:99999; flex-direction:column; gap:16px; }
  #adminGuard input{ background:rgba(255,255,255,0.05); border:1px solid var(--border); border-radius:10px; padding:12px 18px; color:var(--text); font-family:inherit; font-size:14px; width:280px; outline:none; }
  #adminGuard input:focus{ border-color:var(--green); }
  #adminGuard .err{ color:var(--red); font-size:13px; display:none; }
</style>
</head>
<body>

<div id="adminGuard">
  <div style="font-family:'Syne',sans-serif;font-size:22px;color:var(--green)">🔐 Painel Admin</div>
  <input type="password" id="adminPass" placeholder="Senha do painel..." onkeydown="if(event.key==='Enter')checkPass()" />
  <button class="btn btn-green" onclick="checkPass()">Entrar</button>
  <div class="err" id="passErr">Senha incorreta</div>
</div>

<header>
  <div><h1>🔐 Painel de Licenças</h1><small>Planejador Lucs — controle de acesso</small></div>
  <small style="color:var(--muted)" id="urlInfo"></small>
</header>

<div class="main">
  <div class="stats">
    <div class="stat-card"><div class="num" id="s-total">—</div><div class="lbl">Total usuários</div></div>
    <div class="stat-card"><div class="num" id="s-ativos" style="color:#29ff9a">—</div><div class="lbl">Ativos</div></div>
    <div class="stat-card"><div class="num" id="s-bloq" style="color:#ff5f6d">—</div><div class="lbl">Bloqueados</div></div>
    <div class="stat-card"><div class="num" id="s-logs">—</div><div class="lbl">Acessos hoje</div></div>
  </div>

  <div class="section">
    <h2>➕ Novo usuário</h2>
    <div class="form-row">
      <input id="novo-nome" placeholder="Nome completo" />
      <input id="novo-email" placeholder="E-mail" type="email" />
      <button class="btn btn-green" onclick="criarUsuario()">Gerar chave e criar</button>
    </div>
  </div>

  <div class="section">
    <h2>👥 Usuários</h2>
    <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden">
      <table>
        <thead><tr><th>Nome</th><th>E-mail</th><th>Chave de acesso</th><th>Status</th><th>Último acesso</th><th>Ações</th></tr></thead>
        <tbody id="tabela-usuarios"><tr><td colspan="6" style="color:var(--muted);text-align:center;padding:24px">Carregando...</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>📋 Log de acessos (últimos 50)</h2>
    <div class="logs-box" id="logs-box">Carregando...</div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const ADMIN_PASSWORD = "admin123";  // ← TROQUE ANTES DE SUBIR!

function checkPass(){
  if(document.getElementById('adminPass').value === ADMIN_PASSWORD){
    document.getElementById('adminGuard').style.display = 'none';
    document.getElementById('urlInfo').textContent = window.location.host;
    carregar();
  } else {
    document.getElementById('passErr').style.display = 'block';
  }
}

async function api(path, method='GET', body=null){
  const opts = { method, headers:{'Content-Type':'application/json'} };
  if(body) opts.body = JSON.stringify(body);
  return (await fetch(path, opts)).json();
}

function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(()=> t.classList.remove('show'), 2500);
}

function copiar(txt){
  navigator.clipboard.writeText(txt).then(()=> toast('✅ Chave copiada!'));
}

async function carregar(){
  const data = await api('/admin/dados');
  document.getElementById('s-total').textContent = data.total;
  document.getElementById('s-ativos').textContent = data.ativos;
  document.getElementById('s-bloq').textContent = data.total - data.ativos;
  document.getElementById('s-logs').textContent = data.logs_hoje;

  const tbody = document.getElementById('tabela-usuarios');
  tbody.innerHTML = !data.usuarios.length
    ? '<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:24px">Nenhum usuário ainda</td></tr>'
    : data.usuarios.map(u => `
      <tr>
        <td>${u.nome}</td>
        <td style="color:var(--muted)">${u.email}</td>
        <td><span class="chave-box" onclick="copiar('${u.chave}')">${u.chave}</span></td>
        <td><span class="badge ${u.ativo ? 'badge-on':'badge-off'}">${u.ativo ? 'Ativo':'Bloqueado'}</span></td>
        <td style="color:var(--muted);font-size:12px">${u.ultimo_login ? u.ultimo_login.slice(0,16).replace('T',' ') : '—'}</td>
        <td><div class="actions">
          ${u.ativo
            ? `<button class="btn btn-red btn-sm" onclick="toggleAcesso(${u.id},0)">Bloquear</button>`
            : `<button class="btn btn-green btn-sm" onclick="toggleAcesso(${u.id},1)">Liberar</button>`}
          <button class="btn btn-yellow btn-sm" onclick="copiar('${u.chave}')">📋 Copiar</button>
          <button class="btn btn-red btn-sm" onclick="deletarUsuario(${u.id})">🗑️</button>
        </div></td>
      </tr>`).join('');

  const logsBox = document.getElementById('logs-box');
  logsBox.innerHTML = !data.logs.length
    ? '<div style="color:var(--muted)">Nenhum acesso registrado.</div>'
    : data.logs.map(l => `
      <div class="log-row">
        <span class="log-time">${l.momento ? l.momento.slice(0,16).replace('T',' ') : '—'}</span>
        <span class="${l.sucesso ? 'log-ok':'log-fail'}">${l.sucesso ? '✅':'❌'}</span>
        <span>${l.email}</span>
        <span style="color:var(--muted)">${l.ip}</span>
      </div>`).join('');
}

async function criarUsuario(){
  const nome = document.getElementById('novo-nome').value.trim();
  const email = document.getElementById('novo-email').value.trim();
  if(!nome || !email){ alert('Preencha nome e e-mail'); return; }
  const r = await api('/admin/criar','POST',{nome,email});
  if(r.ok){
    navigator.clipboard.writeText(r.chave).then(()=> toast('✅ Chave copiada automaticamente!'));
    document.getElementById('novo-nome').value='';
    document.getElementById('novo-email').value='';
    carregar();
  } else { alert(r.msg || 'Erro'); }
}

async function toggleAcesso(id, ativo){
  await api('/admin/toggle','POST',{id,ativo});
  toast(ativo ? '✅ Acesso liberado' : '🔒 Acesso bloqueado');
  carregar();
}

async function deletarUsuario(id){
  if(!confirm('Excluir usuário?')) return;
  await api('/admin/deletar','POST',{id});
  toast('🗑️ Removido');
  carregar();
}

setInterval(carregar, 15000);
</script>
</body>
</html>
"""

@app.route("/")
def painel():
    return render_template_string(PAINEL_HTML)

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
    total  = len(usuarios)
    ativos = sum(1 for u in usuarios if u["ativo"])
    return jsonify({"usuarios": usuarios, "total": total, "ativos": ativos,
                    "logs_hoje": logs_hoje, "logs": logs})

@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    dados = request.json or {}
    nome  = dados.get("nome","").strip()
    email = dados.get("email","").strip()
    if not nome or not email:
        return jsonify({"ok": False, "msg": "Nome e e-mail obrigatórios"})
    chave = secrets.token_urlsafe(24)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO usuarios(nome,email,chave,ativo,criado_em) VALUES(%s,%s,%s,1,%s)",
                    (nome, email, chave, datetime.datetime.now().isoformat())
                )
            conn.commit()
        return jsonify({"ok": True, "chave": chave})
    except Exception as e:
        return jsonify({"ok": False, "msg": "E-mail já cadastrado"})

@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    dados = request.json or {}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ativo=%s WHERE id=%s",
                       (dados.get("ativo",0), dados.get("id")))
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

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ───────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)