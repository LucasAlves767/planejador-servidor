from flask import Flask, request, jsonify, render_template_string, send_file, redirect
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
import os
import random
import string

app = Flask(__name__)

# ══════════════════════════════════════════
#  BANCO
# ══════════════════════════════════════════
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def row_to_dict(row):
    d = dict(row)
    for k, v in d.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            pass
        elif hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
        else:
            d[k] = str(v)
    return d

def nova_chave():
    chars = string.ascii_uppercase + string.digits
    partes = [''.join(random.choices(chars, k=4)) for _ in range(3)]
    return "LUCS-" + "-".join(partes)

def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id          SERIAL PRIMARY KEY,
                nome        TEXT NOT NULL,
                email       TEXT,
                chave       TEXT UNIQUE NOT NULL,
                ativo       BOOLEAN DEFAULT TRUE,
                expira      DATE,
                criado_em   TIMESTAMP DEFAULT NOW(),
                ultimo_acesso TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS logs (
                id      SERIAL PRIMARY KEY,
                nome    TEXT,
                chave   TEXT,
                acao    TEXT,
                sucesso INTEGER DEFAULT 1,
                momento TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
        migracoes = [
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS expira DATE",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_acesso TIMESTAMP",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS nome TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS acao TEXT",
        ]
        for sql in migracoes:
            try:
                cur.execute(sql)
                conn.commit()
            except Exception:
                conn.rollback()

        # Corrige coluna ativo: banco antigo criava como INTEGER, novo precisa de BOOLEAN
        try:
            cur.execute("""
                SELECT data_type FROM information_schema.columns
                WHERE table_name = 'usuarios' AND column_name = 'ativo'
            """)
            row = cur.fetchone()
            if row is None:
                cur.execute("ALTER TABLE usuarios ADD COLUMN ativo BOOLEAN DEFAULT TRUE")
                conn.commit()
                print("[DB] Coluna ativo criada como BOOLEAN")
            elif row['data_type'] in ('integer', 'smallint', 'bigint'):
                cur.execute("ALTER TABLE usuarios ALTER COLUMN ativo TYPE BOOLEAN USING ativo::boolean")
                conn.commit()
                print("[DB] Coluna ativo convertida INTEGER -> BOOLEAN")
            else:
                print(f"[DB] Coluna ativo OK ({row['data_type']})")
        except Exception as e:
            conn.rollback()
            print(f"[DB] Aviso ativo: {e}")
        cur.close()
        conn.close()
        print("[DB] OK")
    except Exception as e:
        print(f"[DB] ERRO: {e}")

with app.app_context():
    init_db()

# ══════════════════════════════════════════
#  HTML
# ══════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lucs Tech</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:    #030b14;
  --surf:  #071525;
  --card:  #0a1e30;
  --bord:  rgba(0,200,255,.12);
  --c1:    #00cfff;
  --c2:    #005bcc;
  --text:  #cce8f4;
  --muted: #4a7a99;
  --green: #00e5a0;
  --red:   #ff3355;
  --gold:  #ffcc44;
  --shadow: 0 4px 24px rgba(0,0,0,.4);
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', sans-serif;
  min-height: 100vh;
  background-image:
    radial-gradient(ellipse 100% 50% at 50% 0%, rgba(0,90,200,.15) 0%, transparent 70%),
    linear-gradient(180deg, rgba(0,20,40,.6) 0%, transparent 100%);
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bord); border-radius: 4px; }

/* ── LAYOUT ── */
.wrap { max-width: 1200px; margin: 0 auto; padding: 24px 20px; }

/* ── HEADER ── */
.hdr {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px;
  background: var(--surf);
  border: 1px solid var(--bord);
  border-radius: 16px;
  margin-bottom: 20px;
  box-shadow: var(--shadow);
}
.logo {
  font-family: 'Orbitron', monospace;
  font-size: 18px; font-weight: 900; letter-spacing: 4px;
  background: linear-gradient(90deg, var(--c1), var(--c2));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.mode-tabs { display: flex; gap: 8px; }
.tab {
  padding: 6px 18px; border-radius: 20px;
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  cursor: pointer; text-decoration: none; transition: all .2s;
  border: 1px solid var(--bord); color: var(--muted); background: transparent;
}
.tab.active { background: rgba(0,207,255,.12); border-color: var(--c1); color: var(--c1); }
.tab:hover:not(.active) { border-color: rgba(0,207,255,.3); color: var(--c1); }

/* ── STATS ── */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.stat {
  background: var(--card); border: 1px solid var(--bord);
  border-radius: 14px; padding: 20px 16px; text-align: center;
  position: relative; overflow: hidden;
  transition: transform .2s, border-color .2s;
  box-shadow: var(--shadow);
}
.stat:hover { transform: translateY(-3px); border-color: rgba(0,207,255,.25); }
.stat::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--c2), var(--c1));
}
.stat-n {
  font-family: 'Orbitron', monospace; font-size: 32px; font-weight: 700;
  color: var(--c1); display: block; line-height: 1;
}
.stat-n.red  { color: var(--red); }
.stat-n.gold { color: var(--gold); }
.stat-l { font-size: 9px; color: var(--muted); letter-spacing: 2px; margin-top: 6px; display: block; }

/* ── CARD ── */
.card {
  background: var(--card); border: 1px solid var(--bord);
  border-radius: 16px; padding: 24px; margin-bottom: 18px;
  box-shadow: var(--shadow);
  animation: fadeup .35s ease both;
}
.card-title {
  font-family: 'Orbitron', monospace; font-size: 10px;
  letter-spacing: 3px; color: var(--c1); opacity: .7; margin-bottom: 18px;
}
.card-head {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;
}

/* ── FORM ── */
.form-row { display: grid; grid-template-columns: 1fr 1fr 90px auto; gap: 12px; align-items: end; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 9px; letter-spacing: 2px; color: var(--muted); font-weight: 600; }
input[type=text], input[type=email], input[type=number] {
  background: rgba(0,0,0,.5); border: 1px solid var(--bord);
  padding: 12px 14px; border-radius: 10px; color: #fff;
  font-family: 'Inter', sans-serif; font-size: 14px;
  outline: none; transition: border-color .2s, box-shadow .2s; width: 100%;
}
input:focus { border-color: var(--c1); box-shadow: 0 0 0 3px rgba(0,207,255,.1); }

/* ── BOTÕES ── */
.btn-primary {
  background: linear-gradient(135deg, var(--c2), var(--c1));
  color: #000; border: none; border-radius: 10px;
  font-family: 'Orbitron', monospace; font-size: 10px; font-weight: 700; letter-spacing: 1px;
  padding: 12px 20px; cursor: pointer; white-space: nowrap;
  transition: opacity .2s, transform .1s;
  box-shadow: 0 0 20px rgba(0,207,255,.3);
}
.btn-primary:hover { opacity: .85; }
.btn-primary:active { transform: scale(.97); }

.btn-danger {
  background: rgba(255,51,85,.1); color: var(--red);
  border: 1px solid rgba(255,51,85,.25); border-radius: 10px;
  font-family: 'Orbitron', monospace; font-size: 9px; font-weight: 700; letter-spacing: 1px;
  padding: 10px 16px; cursor: pointer; transition: all .2s;
}
.btn-danger:hover { background: rgba(255,51,85,.2); }

/* ── TABELA ── */
table { width: 100%; border-collapse: collapse; }
th {
  color: var(--muted); font-size: 9px; letter-spacing: 2px; font-weight: 600;
  padding: 10px 14px; border-bottom: 1px solid var(--bord); text-align: left;
}
td { padding: 14px; border-bottom: 1px solid rgba(255,255,255,.03); vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: rgba(0,207,255,.02); }

.nome-cell b { font-size: 14px; }
.nome-cell small { color: var(--muted); font-size: 11px; display: block; margin-top: 2px; }

.chave-badge {
  display: inline-block;
  background: rgba(255,204,68,.08); color: var(--gold);
  border: 1px solid rgba(255,204,68,.2); border-radius: 8px;
  padding: 5px 11px; cursor: pointer;
  font-family: 'Orbitron', monospace; font-size: 10px; letter-spacing: 1px;
  transition: background .2s; user-select: none;
}
.chave-badge:hover { background: rgba(255,204,68,.16); }
.chave-badge:active { transform: scale(.97); }

.status-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 14px; border-radius: 20px;
  font-size: 9px; font-weight: 700; letter-spacing: 1px;
  border: none; cursor: pointer; transition: all .2s;
}
.status-btn.on  { background: rgba(0,229,160,.12); color: var(--green); border: 1px solid rgba(0,229,160,.25); }
.status-btn.off { background: rgba(255,51,85,.1);  color: var(--red);   border: 1px solid rgba(255,51,85,.25); }
.status-btn.on:hover  { background: rgba(0,229,160,.22); }
.status-btn.off:hover { background: rgba(255,51,85,.2); }

.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot.on  { background: var(--green); box-shadow: 0 0 6px var(--green); }
.dot.off { background: var(--red);   box-shadow: 0 0 6px var(--red); }

.del-btn {
  background: none; border: none; color: var(--red);
  cursor: pointer; font-size: 18px; opacity: .35;
  transition: opacity .2s; line-height: 1; padding: 4px;
}
.del-btn:hover { opacity: 1; }

/* ── LOGS ── */
.log-box {
  background: rgba(0,0,0,.5); border-radius: 10px; padding: 16px;
  max-height: 200px; overflow-y: auto;
  font-family: 'Courier New', monospace; font-size: 11px; line-height: 1.9;
  color: var(--muted);
}
.log-box .ok   { color: var(--green); }
.log-box .fail { color: var(--red); }
.log-box .info { color: var(--c1); }

/* ── TOAST ── */
.toast {
  position: fixed; bottom: 24px; right: 24px;
  background: rgba(0,207,255,.1); border: 1px solid var(--c1); color: var(--c1);
  padding: 12px 22px; border-radius: 12px;
  font-family: 'Orbitron', monospace; font-size: 11px;
  opacity: 0; transform: translateY(10px);
  transition: all .3s; pointer-events: none; z-index: 9999;
}
.toast.show { opacity: 1; transform: translateY(0); }

/* ── EMPTY ── */
.empty { text-align: center; padding: 40px; color: var(--muted); font-size: 13px; }

/* ── ANIMAÇÃO ── */
@keyframes fadeup {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: none; }
}
.stats .stat:nth-child(1) { animation: fadeup .3s .05s both; }
.stats .stat:nth-child(2) { animation: fadeup .3s .10s both; }
.stats .stat:nth-child(3) { animation: fadeup .3s .15s both; }
.stats .stat:nth-child(4) { animation: fadeup .3s .20s both; }

/* ── DM THEME ── */
body.dm {
  --c1:   #b060ff;
  --c2:   #4800bb;
  --bord: rgba(160,80,255,.12);
  background-image:
    radial-gradient(ellipse 100% 50% at 50% 0%, rgba(80,0,180,.18) 0%, transparent 70%),
    linear-gradient(180deg, rgba(20,0,40,.6) 0%, transparent 100%);
}
body.dm .btn-primary { color: #fff; }
body.dm .stat::before { background: linear-gradient(90deg, var(--c2), var(--c1)); }
body.dm .log-box .ok { color: var(--c1); }
</style>
</head>
<body id="body">
<div class="wrap">

  <!-- HEADER -->
  <div class="hdr">
    <div class="logo" id="logo">⚡ LUCS TECH</div>
    <div class="mode-tabs">
      <a href="/app" class="tab" id="tab-app">APP</a>
      <a href="/dm"  class="tab" id="tab-dm">DM</a>
    </div>
  </div>

  <!-- STATS -->
  <div class="stats">
    <div class="stat"><span class="stat-n"      id="s-total">—</span><span class="stat-l">TOTAL</span></div>
    <div class="stat"><span class="stat-n"      id="s-ativos">—</span><span class="stat-l">ATIVOS</span></div>
    <div class="stat"><span class="stat-n red"  id="s-bloq">—</span><span class="stat-l">BLOQUEADOS</span></div>
    <div class="stat"><span class="stat-n gold" id="s-hoje">—</span><span class="stat-l">LOGINS HOJE</span></div>
  </div>

  <!-- GERAR -->
  <div class="card">
    <div class="card-title">GERAR NOVO ACESSO</div>
    <div class="form-row">
      <div class="field">
        <label>NOME DO CLIENTE</label>
        <input type="text" id="inp-nome" placeholder="Ex: João Silva"/>
      </div>
      <div class="field">
        <label>E-MAIL</label>
        <input type="email" id="inp-email" placeholder="cliente@email.com"/>
      </div>
      <div class="field">
        <label>DIAS</label>
        <input type="number" id="inp-dias" value="30" min="1"/>
      </div>
      <button class="btn-primary" id="btn-gerar">⚡ GERAR</button>
    </div>
  </div>

  <!-- TABELA -->
  <div class="card">
    <div class="card-head">
      <div class="card-title" style="margin:0">CLIENTES CADASTRADOS</div>
      <button class="btn-danger" id="btn-bloquear-todos">🔒 BLOQUEAR TODOS</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>CLIENTE</th>
          <th>CHAVE</th>
          <th>VENCIMENTO</th>
          <th>ÚLTIMO ACESSO</th>
          <th>STATUS</th>
          <th style="text-align:right">AÇÕES</th>
        </tr>
      </thead>
      <tbody id="tabela">
        <tr><td colspan="6" class="empty">Carregando...</td></tr>
      </tbody>
    </table>
  </div>

  <!-- LOGS -->
  <div class="card">
    <div class="card-title">LOG DE ALTERAÇÕES</div>
    <div class="log-box" id="logs">Carregando...</div>
  </div>

</div>
<div class="toast" id="toast"></div>

<script>
// ── TEMA ──────────────────────────────────────────────────
const MODO = document.body.dataset.modo || 'app';
if (MODO === 'dm') {
  document.getElementById('body').classList.add('dm');
  document.getElementById('logo').textContent = '✦ LUCS TECH';
}
document.getElementById('tab-' + MODO).classList.add('active');

// ── TOAST ─────────────────────────────────────────────────
function toast(msg, dur = 2800) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), dur);
}

// ── FORMATAÇÃO ────────────────────────────────────────────
function fData(s) {
  if (!s) return '<span style="color:var(--muted)">—</span>';
  return new Date(s).toLocaleDateString('pt-BR');
}
function fDT(s) {
  if (!s) return '<span style="color:var(--muted)">Nunca</span>';
  return new Date(s).toLocaleString('pt-BR');
}
function vencido(s) {
  return s && new Date(s) < new Date();
}

// ── CARREGAR DADOS ────────────────────────────────────────
async function carregar() {
  try {
    const res = await fetch('/admin/dados');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();
    if (!d.usuarios) return;

    // stats
    document.getElementById('s-total').textContent  = d.usuarios.length;
    document.getElementById('s-ativos').textContent = d.usuarios.filter(u => u.ativo).length;
    document.getElementById('s-bloq').textContent   = d.usuarios.filter(u => !u.ativo).length;
    document.getElementById('s-hoje').textContent   = d.logs_hoje;

    // tabela
    const tbody = document.getElementById('tabela');
    if (d.usuarios.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">Nenhum cliente cadastrado ainda.</td></tr>';
    } else {
      tbody.innerHTML = d.usuarios.map(u => `
        <tr>
          <td class="nome-cell">
            <b>${esc(u.nome)}</b>
            <small>${esc(u.email || '')}</small>
          </td>
          <td>
            <span class="chave-badge" data-chave="${esc(u.chave)}">${esc(u.chave)}</span>
          </td>
          <td style="color:${vencido(u.expira) ? 'var(--red)' : 'var(--muted)'}">
            ${u.expira ? fData(u.expira) : 'Sem limite'}
          </td>
          <td>${fDT(u.ultimo_acesso)}</td>
          <td>
            <button class="status-btn ${u.ativo ? 'on' : 'off'}" data-chave="${esc(u.chave)}">
              <span class="dot ${u.ativo ? 'on' : 'off'}"></span>
              ${u.ativo ? 'ATIVO' : 'BLOQUEADO'}
            </button>
          </td>
          <td style="text-align:right">
            <button class="del-btn" data-chave="${esc(u.chave)}" title="Remover">✕</button>
          </td>
        </tr>
      `).join('');
    }

    // eventos da tabela (usa data-chave — funciona com qualquer chave)
    tbody.querySelectorAll('.chave-badge').forEach(el =>
      el.onclick = () => { navigator.clipboard.writeText(el.dataset.chave); toast('✓ Chave copiada!'); }
    );
    tbody.querySelectorAll('.status-btn').forEach(el =>
      el.onclick = () => toggleStatus(el.dataset.chave)
    );
    tbody.querySelectorAll('.del-btn').forEach(el =>
      el.onclick = () => remover(el.dataset.chave)
    );

    // logs
    const logBox = document.getElementById('logs');
    if (d.logs.length === 0) {
      logBox.innerHTML = '<span style="color:var(--muted)">Nenhuma atividade registrada.</span>';
    } else {
      logBox.innerHTML = d.logs.map(l => {
        const cls   = l.acao === 'login' ? (l.sucesso ? 'ok' : 'fail') : 'info';
        const icon  = l.acao === 'login' ? (l.sucesso ? '✓' : '✗') : '◆';
        const label = l.acao === 'login'
          ? (l.sucesso ? 'LOGIN OK' : 'LOGIN NEGADO')
          : (l.acao || 'AÇÃO').toUpperCase();
        const nome  = l.nome ? ` [${esc(l.nome)}]` : '';
        return `<div>[${fDT(l.momento)}] <span class="${cls}">${icon} ${label}</span>${nome} — ${esc(l.chave || '')}</div>`;
      }).join('');
    }

  } catch (e) {
    console.error('[carregar]', e);
  }
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── GERAR CHAVE ───────────────────────────────────────────
document.getElementById('btn-gerar').onclick = async () => {
  const nome  = document.getElementById('inp-nome').value.trim();
  const email = document.getElementById('inp-email').value.trim();
  const dias  = document.getElementById('inp-dias').value;

  if (!nome) { toast('⚠ Nome obrigatório'); return; }

  const btn = document.getElementById('btn-gerar');
  btn.disabled = true; btn.textContent = '...';

  try {
    const res  = await fetch('/admin/criar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, email, dias })
    });
    const data = await res.json();
    if (data.ok) {
      toast('✓ Chave gerada: ' + data.chave);
      document.getElementById('inp-nome').value  = '';
      document.getElementById('inp-email').value = '';
      carregar();
    } else {
      toast('✗ ' + (data.msg || 'Erro ao criar'));
    }
  } catch (e) {
    toast('✗ Erro de conexão');
  } finally {
    btn.disabled = false; btn.textContent = '⚡ GERAR';
  }
};

// ── TOGGLE STATUS ─────────────────────────────────────────
async function toggleStatus(chave) {
  try {
    const res = await fetch('/admin/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chave })
    });
    const data = await res.json();
    if (data.ok) { carregar(); toast(data.ativo ? '✓ Cliente ativado' : '🔒 Cliente bloqueado'); }
    else toast('✗ ' + (data.msg || 'Erro'));
  } catch (e) { toast('✗ Erro de conexão'); }
}

// ── REMOVER ───────────────────────────────────────────────
async function remover(chave) {
  if (!confirm('Remover este cliente permanentemente?')) return;
  try {
    const res = await fetch('/admin/deletar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chave })
    });
    const data = await res.json();
    if (data.ok) { carregar(); toast('✓ Cliente removido'); }
    else toast('✗ ' + (data.msg || 'Erro'));
  } catch (e) { toast('✗ Erro de conexão'); }
}

// ── BLOQUEAR TODOS ────────────────────────────────────────
document.getElementById('btn-bloquear-todos').onclick = async () => {
  if (!confirm('Bloquear TODOS os clientes ativos?')) return;
  try {
    await fetch('/admin/bloquear-todos', { method: 'POST' });
    toast('🔒 Todos bloqueados'); carregar();
  } catch (e) { toast('✗ Erro'); }
};

// ── INIT ──────────────────────────────────────────────────
carregar();
setInterval(carregar, 15000);
</script>
</body>
</html>"""

# ══════════════════════════════════════════
#  ROTAS DE NAVEGAÇÃO
# ══════════════════════════════════════════
@app.route("/")
def root():
    if os.path.exists('planejador.html'):
        return send_file('planejador.html')
    return redirect("/app")

@app.route("/app")
def pagina_app():
    html = HTML.replace('<body id="body">', '<body id="body" data-modo="app">')
    return render_template_string(html)

@app.route("/dm")
def pagina_dm():
    html = HTML.replace('<body id="body">', '<body id="body" data-modo="dm">')
    return render_template_string(html)

@app.route("/admin-sistema")
def legado():
    return redirect("/app")

# ══════════════════════════════════════════
#  API — VALIDAR CHAVE (usado pelo app)
# ══════════════════════════════════════════
@app.route("/api/validar", methods=["POST"])
def validar():
    try:
        dados = request.json or {}
        chave = dados.get("chave", "").strip()
        conn = get_db(); cur = conn.cursor()

        cur.execute("SELECT id, nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
        user = cur.fetchone()

        sucesso = 0
        nome_user = ""

        if user:
            nome_user = user['nome']
            exp = user['expira']
            if isinstance(exp, str):
                try: exp = date.fromisoformat(exp)
                except: exp = None
            vencido = exp and exp < datetime.now().date()
            if user['ativo'] and not vencido:
                sucesso = 1
                cur.execute(
                    "UPDATE usuarios SET ultimo_acesso = %s WHERE chave = %s",
                    (datetime.now(), chave)
                )

        cur.execute(
            "INSERT INTO logs (nome, chave, acao, sucesso, momento) VALUES (%s, %s, %s, %s, %s)",
            (nome_user or None, chave, 'login', sucesso, datetime.now())
        )
        conn.commit(); cur.close(); conn.close()

        if sucesso:
            return jsonify({"ok": True, "nome": nome_user})
        return jsonify({"ok": False, "msg": "Acesso negado"}), 403

    except Exception as e:
        print(f"[validar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — ADMIN: DADOS
# ══════════════════════════════════════════
@app.route("/admin/dados")
def admin_dados():
    try:
        conn = get_db(); cur = conn.cursor()

        cur.execute("""
            SELECT nome, email, chave, ativo, expira, ultimo_acesso
            FROM usuarios ORDER BY id DESC
        """)
        usuarios = [row_to_dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT nome, chave, acao, sucesso, momento
            FROM logs ORDER BY id DESC LIMIT 80
        """)
        logs = [row_to_dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT COUNT(*) AS total FROM logs
            WHERE momento::date = CURRENT_DATE AND acao = 'login' AND sucesso = 1
        """)
        hoje = cur.fetchone()['total']

        cur.close(); conn.close()
        return jsonify({"usuarios": usuarios, "logs": logs, "logs_hoje": hoje})

    except Exception as e:
        print(f"[admin_dados] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — ADMIN: CRIAR
# ══════════════════════════════════════════
@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    try:
        d     = request.json or {}
        nome  = d.get('nome', '').strip()
        email = (d.get('email') or '').strip() or None
        dias  = int(d.get('dias') or 30)

        if not nome:
            return jsonify({"ok": False, "msg": "Nome obrigatório"}), 400

        exp   = datetime.now().date() + timedelta(days=dias)
        chave = nova_chave()

        conn = get_db(); cur = conn.cursor()

        for _ in range(10):
            try:
                cur.execute(
                    "INSERT INTO usuarios (nome, email, chave, expira, ativo) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING chave",
                    (nome, email, chave, exp, True)
                )
                chave = cur.fetchone()['chave']
                conn.commit()
                break
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                chave = nova_chave()

        # log da criação
        cur.execute(
            "INSERT INTO logs (nome, chave, acao, sucesso, momento) VALUES (%s, %s, %s, %s, %s)",
            (nome, chave, 'criacao', 1, datetime.now())
        )
        conn.commit()
        cur.close(); conn.close()

        return jsonify({"ok": True, "chave": chave})

    except Exception as e:
        print(f"[admin_criar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — ADMIN: TOGGLE
# ══════════════════════════════════════════
@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    try:
        chave = (request.json or {}).get('chave', '')
        conn = get_db(); cur = conn.cursor()

        cur.execute(
            "UPDATE usuarios SET ativo = NOT ativo WHERE chave = %s RETURNING nome, ativo",
            (chave,)
        )
        row = cur.fetchone()
        conn.commit()

        if row:
            acao = 'ativacao' if row['ativo'] else 'bloqueio'
            cur.execute(
                "INSERT INTO logs (nome, chave, acao, sucesso, momento) VALUES (%s, %s, %s, %s, %s)",
                (row['nome'], chave, acao, 1, datetime.now())
            )
            conn.commit()

        cur.close(); conn.close()
        return jsonify({"ok": True, "ativo": row['ativo'] if row else None})

    except Exception as e:
        print(f"[admin_toggle] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — ADMIN: DELETAR
# ══════════════════════════════════════════
@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    try:
        chave = (request.json or {}).get('chave', '')
        conn = get_db(); cur = conn.cursor()

        cur.execute("SELECT nome FROM usuarios WHERE chave = %s", (chave,))
        row = cur.fetchone()
        nome = row['nome'] if row else None

        cur.execute("DELETE FROM logs WHERE chave = %s AND acao = 'login'", (chave,))
        cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))

        if nome:
            cur.execute(
                "INSERT INTO logs (nome, chave, acao, sucesso, momento) VALUES (%s, %s, %s, %s, %s)",
                (nome, chave, 'remocao', 1, datetime.now())
            )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})

    except Exception as e:
        print(f"[admin_deletar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — ADMIN: BLOQUEAR TODOS
# ══════════════════════════════════════════
@app.route("/admin/bloquear-todos", methods=["POST"])
def bloquear_todos():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET ativo = FALSE WHERE ativo = TRUE")
        cur.execute(
            "INSERT INTO logs (nome, chave, acao, sucesso, momento) VALUES (%s, %s, %s, %s, %s)",
            ('SISTEMA', 'TODOS', 'bloqueio_geral', 1, datetime.now())
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})

    except Exception as e:
        print(f"[bloquear_todos] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
