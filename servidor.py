from flask import Flask, request, jsonify, render_template_string, send_file, redirect
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta, date
import os, random, string

app = Flask(__name__)

# ════════════════════════════════════════════════════════════
#  BANCO DE DADOS
# ════════════════════════════════════════════════════════════
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def gerar_chave():
    c = string.ascii_uppercase + string.digits
    return "LUCS-" + "-".join(''.join(random.choices(c, k=4)) for _ in range(3))

def serializar(row):
    """Converte RealDictRow em dict JSON-safe. Funciona no Python 3.14 (datas já como string)."""
    r = dict(row)
    for k, v in r.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            pass
        elif hasattr(v, 'isoformat'):
            r[k] = v.isoformat()
        else:
            r[k] = str(v)
    return r

def init_db():
    try:
        conn = get_db(); cur = conn.cursor()
        # cria tabelas se não existirem
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                email TEXT,
                chave TEXT UNIQUE NOT NULL,
                ativo BOOLEAN DEFAULT TRUE,
                expira DATE,
                ultimo_acesso TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                chave TEXT,
                sucesso INTEGER,
                momento TIMESTAMP
            );
        """)
        conn.commit()
        # migração segura — adiciona colunas se banco for antigo
        for sql in [
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS expira DATE",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_acesso TIMESTAMP",
        ]:
            try: cur.execute(sql); conn.commit()
            except Exception: conn.rollback()
        cur.close(); conn.close()
        print("[DB] Tabelas OK")
    except Exception as e:
        print(f"[DB] ERRO: {e}")

with app.app_context():
    init_db()

# ════════════════════════════════════════════════════════════
#  PÁGINA /app  — tema azul ciano
# ════════════════════════════════════════════════════════════
APP_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lucs Tech — APP</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#020c18;--c1:#00e5ff;--c2:#0057d9;--card:rgba(4,16,36,0.92);--text:#d8f4ff;--muted:#3a6a88;--red:#ff2d55;--green:#00e5c8;--gold:#ffc940;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;
  background-image:radial-gradient(ellipse 90% 55% at 50% -5%,rgba(0,87,217,0.18),transparent),
  repeating-linear-gradient(0deg,transparent,transparent 48px,rgba(0,229,255,0.025) 48px,rgba(0,229,255,0.025) 49px),
  repeating-linear-gradient(90deg,transparent,transparent 48px,rgba(0,229,255,0.025) 48px,rgba(0,229,255,0.025) 49px);}
::-webkit-scrollbar{width:5px;} ::-webkit-scrollbar-thumb{background:rgba(0,229,255,0.2);border-radius:4px;}
.wrap{max-width:1160px;margin:auto;padding:28px 20px;}
.hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:32px;padding-bottom:18px;border-bottom:1px solid rgba(0,229,255,0.08);}
.logo{font-family:'Orbitron',monospace;font-size:20px;font-weight:900;letter-spacing:4px;
  background:linear-gradient(90deg,var(--c1),var(--c2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hdr-r{display:flex;gap:10px;align-items:center;}
.badge{padding:5px 16px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:2px;}
.b-app{background:rgba(0,229,255,0.12);border:1px solid var(--c1);color:var(--c1);}
.b-lnk{background:transparent;border:1px solid rgba(255,255,255,0.1);color:var(--muted);text-decoration:none;transition:all .2s;}
.b-lnk:hover{border-color:rgba(0,229,255,0.3);color:var(--c1);}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}
.sc{background:var(--card);border:1px solid rgba(0,229,255,0.07);border-radius:14px;padding:18px 14px;
  text-align:center;position:relative;overflow:hidden;transition:border-color .3s,transform .2s;}
.sc:hover{border-color:rgba(0,229,255,0.25);transform:translateY(-2px);}
.sc::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--c2),var(--c1));}
.sc-n{font-family:'Orbitron',monospace;font-size:28px;font-weight:700;color:var(--c1);display:block;line-height:1.1;}
.sc-n.r{color:var(--red);} .sc-n.g{color:var(--gold);}
.sc-l{font-size:9px;color:var(--muted);letter-spacing:2px;margin-top:5px;display:block;}
.panel{background:var(--card);border:1px solid rgba(0,229,255,0.09);border-radius:16px;padding:22px;margin-bottom:20px;animation:fi .4s ease both;}
.ptitle{font-family:'Orbitron',monospace;font-size:10px;letter-spacing:3px;color:var(--c1);margin-bottom:16px;opacity:.75;}
.frow{display:grid;grid-template-columns:1fr 1fr 80px auto;gap:10px;align-items:end;}
.field{display:flex;flex-direction:column;gap:5px;}
.field label{font-size:9px;letter-spacing:2px;color:var(--muted);}
input{background:rgba(0,0,0,0.55);border:1px solid rgba(0,229,255,0.14);padding:11px 13px;
  border-radius:9px;color:#fff;font-family:'Rajdhani',sans-serif;font-size:14px;outline:none;transition:border-color .25s;width:100%;}
input:focus{border-color:var(--c1);}
.btn{background:linear-gradient(135deg,#0057d9,#00e5ff);color:#000;border:none;border-radius:9px;
  font-family:'Orbitron',monospace;font-size:10px;font-weight:700;letter-spacing:1px;padding:11px 18px;
  cursor:pointer;white-space:nowrap;transition:opacity .2s,transform .15s;box-shadow:0 0 18px rgba(0,229,255,0.25);}
.btn:hover{opacity:.88;} .btn:active{transform:scale(.97);}
.btn-d{background:rgba(255,45,85,0.1);color:var(--red);border:1px solid rgba(255,45,85,0.25);
  border-radius:8px;font-family:'Orbitron',monospace;font-size:9px;font-weight:700;
  letter-spacing:1px;padding:8px 14px;cursor:pointer;transition:all .2s;}
.btn-d:hover{background:rgba(255,45,85,0.22);}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{color:var(--muted);font-size:9px;letter-spacing:2px;padding:10px 12px;border-bottom:1px solid rgba(0,229,255,0.07);text-align:left;}
td{padding:12px;border-bottom:1px solid rgba(255,255,255,0.025);vertical-align:middle;}
tr:hover td{background:rgba(0,229,255,0.018);}
.chave{color:var(--gold);background:rgba(255,201,64,0.07);padding:5px 10px;border-radius:6px;
  cursor:pointer;font-family:'Orbitron',monospace;font-size:10px;letter-spacing:1px;
  border:1px solid rgba(255,201,64,0.18);transition:background .2s;display:inline-block;}
.chave:hover{background:rgba(255,201,64,0.15);}
.pill{padding:4px 13px;border-radius:20px;font-size:9px;font-weight:700;letter-spacing:1px;border:none;cursor:pointer;transition:all .2s;}
.on{background:rgba(0,229,200,0.12);color:var(--green);border:1px solid rgba(0,229,200,0.28);}
.on:hover{background:rgba(0,229,200,0.22);}
.off{background:rgba(255,45,85,0.1);color:var(--red);border:1px solid rgba(255,45,85,0.25);}
.off:hover{background:rgba(255,45,85,0.2);}
.del{background:none;border:none;color:var(--red);cursor:pointer;font-size:16px;opacity:.35;transition:opacity .2s;}
.del:hover{opacity:1;}
.acts{display:flex;gap:8px;align-items:center;justify-content:flex-end;}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;}
.don{background:var(--green);box-shadow:0 0 6px var(--green);}
.doff{background:var(--red);box-shadow:0 0 6px var(--red);}
.logs-box{background:rgba(0,0,0,0.55);border-radius:10px;padding:14px;max-height:190px;
  overflow-y:auto;font-family:'Courier New',monospace;font-size:11px;color:#3a7a90;line-height:1.85;}
.lok{color:var(--green);} .lfail{color:var(--red);}
.toast{position:fixed;bottom:22px;right:22px;background:rgba(0,229,255,0.1);border:1px solid var(--c1);
  color:var(--c1);padding:11px 20px;border-radius:10px;font-family:'Orbitron',monospace;font-size:11px;
  opacity:0;transform:translateY(8px);transition:all .3s;pointer-events:none;z-index:999;}
.toast.show{opacity:1;transform:translateY(0);}
@keyframes fi{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">⚡ LUCS TECH</div>
    <div class="hdr-r">
      <span class="badge b-app">APP MODE</span>
      <a href="/dm" class="badge b-lnk">DM MODE →</a>
    </div>
  </div>
  <div class="stats">
    <div class="sc"><span class="sc-n" id="s-total">—</span><span class="sc-l">TOTAL</span></div>
    <div class="sc"><span class="sc-n" id="s-ativos">—</span><span class="sc-l">ATIVOS</span></div>
    <div class="sc"><span class="sc-n r" id="s-bloq">—</span><span class="sc-l">BLOQUEADOS</span></div>
    <div class="sc"><span class="sc-n g" id="s-hoje">—</span><span class="sc-l">LOGINS HOJE</span></div>
  </div>
  <div class="panel">
    <div class="ptitle">GERAR NOVO ACESSO</div>
    <div class="frow">
      <div class="field"><label>NOME DO CLIENTE</label><input type="text" id="nome" placeholder="Ex: João Silva"/></div>
      <div class="field"><label>E-MAIL</label><input type="email" id="email" placeholder="cliente@email.com"/></div>
      <div class="field"><label>DIAS</label><input type="number" id="dias" value="30" min="1"/></div>
      <button class="btn" onclick="criar()">⚡ GERAR</button>
    </div>
  </div>
  <div class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <div class="ptitle" style="margin:0">CLIENTES CADASTRADOS</div>
      <button class="btn-d" onclick="bloquearTodos()">🔒 BLOQUEAR TODOS</button>
    </div>
    <table>
      <thead><tr><th>CLIENTE</th><th>CHAVE</th><th>VENCIMENTO</th><th>ÚLTIMO ACESSO</th><th>STATUS</th><th style="text-align:right">AÇÕES</th></tr></thead>
      <tbody id="tabela"></tbody>
    </table>
  </div>
  <div class="panel">
    <div class="ptitle">HISTÓRICO DE ACESSOS</div>
    <div class="logs-box" id="logs">Carregando...</div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
function toast(m){const t=document.getElementById('toast');t.innerText=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600);}
function fD(s){if(!s)return'<span style="color:var(--muted)">—</span>';return new Date(s).toLocaleDateString('pt-BR');}
function fDT(s){if(!s)return'<span style="color:var(--muted)">Nunca</span>';return new Date(s).toLocaleString('pt-BR');}
function venc(s){return s&&new Date(s)<new Date();}
async function carregar(){
  try{
    const d=await(await fetch('/admin/dados')).json();
    if(!d.usuarios)return;
    document.getElementById('s-total').innerText=d.usuarios.length;
    document.getElementById('s-ativos').innerText=d.usuarios.filter(u=>u.ativo).length;
    document.getElementById('s-bloq').innerText=d.usuarios.filter(u=>!u.ativo).length;
    document.getElementById('s-hoje').innerText=d.logs_hoje;
    document.getElementById('tabela').innerHTML=d.usuarios.map(u=>`
      <tr>
        <td><b>${u.nome}</b><br><small style="color:var(--muted);font-size:11px">${u.email||''}</small></td>
        <td><span class="chave" onclick="cp('${u.chave}')">${u.chave}</span></td>
        <td style="color:${venc(u.expira)?'var(--red)':'var(--muted)'}">${u.expira?fD(u.expira):'Sem limite'}</td>
        <td style="font-size:12px;color:var(--muted)">${fDT(u.ultimo_acesso)}</td>
        <td><button class="pill ${u.ativo?'on':'off'}" onclick="toggle('${u.chave}')"><span class="dot ${u.ativo?'don':'doff'}"></span>${u.ativo?'ATIVO':'BLOQUEADO'}</button></td>
        <td><div class="acts"><button class="del" onclick="del('${u.chave}')">✕</button></div></td>
      </tr>`).join('');
    document.getElementById('logs').innerHTML=d.logs.length
      ?d.logs.map(l=>`<div>[${fDT(l.momento)}] <span class="${l.sucesso?'lok':'lfail'}">${l.sucesso?'✓ OK':'✗ NEGADO'}</span> — ${l.chave}</div>`).join('')
      :'<span style="color:var(--muted)">Nenhum acesso ainda.</span>';
  }catch(e){console.error(e);}
}
function cp(c){navigator.clipboard.writeText(c);toast('✓ Chave copiada!');}
async function criar(){
  const nome=document.getElementById('nome').value.trim();
  const email=document.getElementById('email').value.trim();
  const dias=document.getElementById('dias').value;
  if(!nome){toast('⚠ Nome obrigatório');return;}
  const r=await fetch('/admin/criar-auto',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome,email,dias})});
  const data=await r.json();
  if(data.ok){toast('✓ Chave: '+data.chave);document.getElementById('nome').value='';document.getElementById('email').value='';carregar();}
  else toast('✗ '+(data.msg||'Erro desconhecido'));
}
async function toggle(chave){await fetch('/admin/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});carregar();}
async function del(chave){if(!confirm('Remover este cliente?'))return;await fetch('/admin/deletar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});carregar();}
async function bloquearTodos(){if(!confirm('Bloquear TODOS?'))return;await fetch('/admin/bloquear-todos',{method:'POST'});toast('🔒 Todos bloqueados');carregar();}
carregar();setInterval(carregar,15000);
</script>
</body>
</html>"""

# ════════════════════════════════════════════════════════════
#  PÁGINA /dm  — tema roxo
# ════════════════════════════════════════════════════════════
DM_HTML = APP_HTML \
  .replace("Lucs Tech — APP","Lucs Tech — DM") \
  .replace("--c1:#00e5ff","--c1:#c060ff") \
  .replace("--c2:#0057d9","--c2:#5010aa") \
  .replace("--bg:#020c18","--bg:#07030f") \
  .replace("--card:rgba(4,16,36,0.92)","--card:rgba(14,6,28,0.93)") \
  .replace("--text:#d8f4ff","--text:#ecdeff") \
  .replace("--muted:#3a6a88","--muted:#6a4488") \
  .replace("rgba(0,87,217,0.18)","rgba(90,10,180,0.22)") \
  .replace("rgba(0,229,255,0.025)","rgba(160,80,255,0.022)") \
  .replace("rgba(0,229,255,0.2)","rgba(160,80,255,0.2)") \
  .replace("rgba(0,229,255,0.08)","rgba(160,80,255,0.1)") \
  .replace("rgba(0,229,255,0.07)","rgba(160,80,255,0.08)") \
  .replace("rgba(0,229,255,0.025)","rgba(160,80,255,0.022)") \
  .replace("rgba(0,229,255,0.25)","rgba(160,80,255,0.3)") \
  .replace("rgba(0,229,255,0.09)","rgba(160,80,255,0.09)") \
  .replace("rgba(0,229,255,0.14)","rgba(160,80,255,0.16)") \
  .replace("rgba(0,229,255,0.018)","rgba(160,80,255,0.018)") \
  .replace("b-app","b-dm") \
  .replace(".b-app{background:rgba(0,229,255,0.12);border:1px solid var(--c1);color:var(--c1);}",
           ".b-dm{background:rgba(160,80,255,0.14);border:1px solid var(--c1);color:var(--c1);}") \
  .replace("APP MODE","DM MODE") \
  .replace("DM MODE →","APP MODE →") \
  .replace('href="/dm"','href="/app"') \
  .replace("⚡ LUCS TECH","✦ LUCS TECH") \
  .replace("linear-gradient(135deg,#0057d9,#00e5ff)","linear-gradient(135deg,#5010aa,#c060ff)") \
  .replace("color:#000","color:#fff") \
  .replace("box-shadow:0 0 18px rgba(0,229,255,0.25)","box-shadow:0 0 18px rgba(160,80,255,0.25)") \
  .replace("color:#3a7a90","color:#6a3a88") \
  .replace(".lok{color:var(--green);}",".lok{color:var(--c1);}") \
  .replace("rgba(0,229,255,0.1);border:1px solid var(--c1)","rgba(160,80,255,0.12);border:1px solid var(--c1)")

# ════════════════════════════════════════════════════════════
#  ROTAS DE NAVEGAÇÃO
# ════════════════════════════════════════════════════════════
@app.route("/")
def root():
    if os.path.exists('planejador.html'):
        return send_file('planejador.html')
    return redirect("/app")

@app.route("/app")
def pagina_app():
    return render_template_string(APP_HTML)

@app.route("/dm")
def pagina_dm():
    return render_template_string(DM_HTML)

@app.route("/admin-sistema")   # rota legada
def admin_sistema():
    return redirect("/app")

# ════════════════════════════════════════════════════════════
#  ROTAS DE API
# ════════════════════════════════════════════════════════════
@app.route("/api/validar", methods=["POST"])
def validar():
    try:
        dados = request.json or {}
        chave = dados.get("chave", "").strip()
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
        user = cur.fetchone()
        sucesso = 0
        if user:
            exp = user['expira']
            if isinstance(exp, str):
                try: exp = date.fromisoformat(exp)
                except: exp = None
            vencido = exp and exp < datetime.now().date()
            if user['ativo'] and not vencido:
                sucesso = 1
                cur.execute("UPDATE usuarios SET ultimo_acesso = %s WHERE chave = %s", (datetime.now(), chave))
        cur.execute("INSERT INTO logs (chave, sucesso, momento) VALUES (%s,%s,%s)", (chave, sucesso, datetime.now()))
        conn.commit(); cur.close(); conn.close()
        if sucesso:
            return jsonify({"ok": True, "nome": user['nome']})
        return jsonify({"ok": False, "msg": "Acesso negado"}), 403
    except Exception as e:
        print(f"[validar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/dados")
def admin_dados():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome, email, chave, ativo, expira, ultimo_acesso FROM usuarios ORDER BY id DESC")
        usuarios = [serializar(r) for r in cur.fetchall()]
        cur.execute("SELECT chave, sucesso, momento FROM logs ORDER BY id DESC LIMIT 60")
        logs = [serializar(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) AS total FROM logs WHERE momento::date = CURRENT_DATE AND sucesso = 1")
        hoje = cur.fetchone()['total']
        cur.close(); conn.close()
        return jsonify({"usuarios": usuarios, "logs": logs, "logs_hoje": hoje})
    except Exception as e:
        print(f"[admin_dados] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/criar-auto", methods=["POST"])
def criar_auto():
    try:
        d = request.json or {}
        nome = d.get('nome', '').strip()
        if not nome:
            return jsonify({"ok": False, "msg": "Nome obrigatório"}), 400
        email = d.get('email', '').strip() or None
        dias = int(d.get('dias') or 30)
        exp = datetime.now().date() + timedelta(days=dias)
        conn = get_db(); cur = conn.cursor()
        chave = gerar_chave()
        for _ in range(10):
            try:
                cur.execute(
                    "INSERT INTO usuarios (nome,email,chave,expira,ativo) VALUES (%s,%s,%s,%s,%s) RETURNING chave",
                    (nome, email, chave, exp, True)
                )
                chave = cur.fetchone()['chave']
                conn.commit()
                break
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                chave = gerar_chave()
        cur.close(); conn.close()
        return jsonify({"ok": True, "chave": chave})
    except Exception as e:
        print(f"[criar_auto] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    try:
        chave = (request.json or {}).get('chave')
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET ativo = NOT ativo WHERE chave = %s", (chave,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    try:
        chave = (request.json or {}).get('chave')
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM logs WHERE chave = %s", (chave,))
        cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/bloquear-todos", methods=["POST"])
def bloquear_todos():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET ativo = False WHERE ativo = True")
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
