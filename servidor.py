from flask import Flask, request, jsonify, render_template_string, send_file, redirect, make_response
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
import os, random, string, csv, io

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

# ══════════════════════════════════════════
#  BANCO
# ══════════════════════════════════════════
def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def row_to_dict(row):
    d = dict(row)
    for k, v in d.items():
        if v is None or isinstance(v, (str, float, bool)):
            pass
        elif isinstance(v, int):
            d[k] = bool(v) if k == 'ativo' else v
        elif hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
        else:
            d[k] = str(v)
    return d

def nova_chave():
    chars = string.ascii_uppercase + string.digits
    return "LUCS-" + "-".join(''.join(random.choices(chars, k=4)) for _ in range(3))

def init_db():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id            SERIAL PRIMARY KEY,
                nome          TEXT NOT NULL,
                email         TEXT,
                empresa       TEXT,
                chave         TEXT UNIQUE NOT NULL,
                ativo         INTEGER DEFAULT 1,
                expira        DATE,
                criado_em     TIMESTAMP DEFAULT NOW(),
                ultimo_acesso TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS logs (
                id      SERIAL PRIMARY KEY,
                nome    TEXT,
                empresa TEXT,
                chave   TEXT,
                acao    TEXT,
                sucesso INTEGER DEFAULT 1,
                momento TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
        for sql in [
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS empresa TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS expira DATE",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_acesso TIMESTAMP",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS nome TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS empresa TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS acao TEXT",
        ]:
            try: cur.execute(sql); conn.commit()
            except: conn.rollback()

        # Força ativo como INTEGER — elimina problema com BOOLEAN
        try:
            cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name='usuarios' AND column_name='ativo'")
            r = cur.fetchone()
            if r and r['data_type'] in ('boolean',):
                cur.execute("ALTER TABLE usuarios ALTER COLUMN ativo TYPE INTEGER USING ativo::integer")
                conn.commit()
                print("[DB] ativo: BOOLEAN -> INTEGER OK")
        except Exception as e:
            conn.rollback(); print(f"[DB] aviso: {e}")

        cur.close(); conn.close()
        print("[DB] pronto")
    except Exception as e:
        print(f"[DB] ERRO: {e}")

with app.app_context():
    init_db()

# ══════════════════════════════════════════
#  HTML — PAINEL PROFISSIONAL
# ══════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lucs Tech — Licenças</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:    #07090f;
  --s1:    #0c1018;
  --s2:    #101520;
  --s3:    #141b26;
  --line:  rgba(255,255,255,.055);
  --line2: rgba(255,255,255,.1);
  --tx:    #d8e8f5;
  --tx2:   #7090a8;
  --tx3:   #384e60;
  --acc:   #e05c16;
  --acc2:  #ff6a25;
  --blue:  #3b9eff;
  --green: #22c98a;
  --red:   #ef4444;
  --amber: #f59e0b;
  --violet:#8b7cf8;
  --r:     11px;
}

body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}

body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 700px 300px at 60% -50px,rgba(224,92,22,.06),transparent),
    radial-gradient(ellipse 500px 400px at 10% 80%,rgba(59,158,255,.04),transparent);
}

::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:4px}

.page{max-width:1300px;margin:0 auto;padding:22px 18px;position:relative;z-index:1}

/* TOP BAR */
.bar{
  display:flex;align-items:center;justify-content:space-between;
  background:var(--s1);border:1px solid var(--line);border-radius:var(--r);
  padding:13px 18px;margin-bottom:18px;
}
.brand{display:flex;align-items:center;gap:11px}
.ico{
  width:32px;height:32px;border-radius:8px;
  background:linear-gradient(140deg,var(--acc),#b84000);
  display:flex;align-items:center;justify-content:center;font-size:15px;
  box-shadow:0 0 14px rgba(224,92,22,.3);flex-shrink:0;
}
.brand-nm{font-family:'DM Mono',monospace;font-size:13px;letter-spacing:3px;color:var(--tx)}
.brand-sub{font-size:10px;color:var(--tx3);letter-spacing:1.5px;margin-top:1px}
.nav{display:flex;gap:5px}
.nav a{
  text-decoration:none;padding:6px 13px;border-radius:7px;
  font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;
  color:var(--tx2);border:1px solid transparent;transition:all .15s;
}
.nav a.on{background:rgba(224,92,22,.1);border-color:rgba(224,92,22,.28);color:var(--acc2)}
.nav a:hover:not(.on){background:var(--s2);border-color:var(--line2);color:var(--tx)}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.kpi{
  background:var(--s1);border:1px solid var(--line);border-radius:var(--r);
  padding:18px 16px;position:relative;overflow:hidden;
  animation:up .35s ease both;
}
.kpi:nth-child(1){animation-delay:.04s}.kpi:nth-child(2){animation-delay:.08s}
.kpi:nth-child(3){animation-delay:.12s}.kpi:nth-child(4){animation-delay:.16s}
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.kpi:nth-child(1)::before{background:var(--blue)}
.kpi:nth-child(2)::before{background:var(--green)}
.kpi:nth-child(3)::before{background:var(--red)}
.kpi:nth-child(4)::before{background:var(--amber)}
.kpi-l{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2.5px;color:var(--tx3);margin-bottom:8px}
.kpi-n{font-family:'DM Mono',monospace;font-size:34px;font-weight:500;line-height:1;letter-spacing:-1px}
.kpi:nth-child(1) .kpi-n{color:var(--blue)}
.kpi:nth-child(2) .kpi-n{color:var(--green)}
.kpi:nth-child(3) .kpi-n{color:var(--red)}
.kpi:nth-child(4) .kpi-n{color:var(--amber)}

/* PANEL */
.panel{
  background:var(--s1);border:1px solid var(--line);border-radius:var(--r);
  padding:20px;margin-bottom:14px;animation:up .35s .2s ease both;
}
.ph{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.ptitle{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:3px;color:var(--tx3)}
.pacts{display:flex;gap:7px;align-items:center;flex-wrap:wrap}

/* FORM */
.frow{display:grid;grid-template-columns:1fr 1fr 1fr 76px auto;gap:9px;align-items:end}
.f{display:flex;flex-direction:column;gap:5px}
.f label{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--tx3)}
input,select{
  background:var(--bg);border:1px solid var(--line2);padding:10px 12px;border-radius:8px;
  color:var(--tx);font-family:'DM Sans',sans-serif;font-size:13px;
  outline:none;transition:border-color .15s,box-shadow .15s;width:100%;
}
input::placeholder{color:var(--tx3)}
input:focus,select:focus{border-color:rgba(224,92,22,.45);box-shadow:0 0 0 3px rgba(224,92,22,.06)}

/* BUTTONS */
.btn{
  display:inline-flex;align-items:center;gap:6px;padding:9px 14px;border-radius:8px;
  cursor:pointer;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1.5px;
  border:none;transition:all .15s;white-space:nowrap;
}
.btn-main{background:var(--acc);color:#fff;box-shadow:0 2px 12px rgba(224,92,22,.28)}
.btn-main:hover{background:var(--acc2);box-shadow:0 2px 18px rgba(224,92,22,.42)}
.btn-main:active{transform:scale(.97)}
.btn-ghost{background:transparent;color:var(--tx2);border:1px solid var(--line2)}
.btn-ghost:hover{background:var(--s2);border-color:var(--line2);color:var(--tx)}
.btn-red{background:rgba(239,68,68,.08);color:var(--red);border:1px solid rgba(239,68,68,.18)}
.btn-red:hover{background:rgba(239,68,68,.13);border-color:rgba(239,68,68,.28)}
.btn-violet{background:rgba(139,124,248,.08);color:var(--violet);border:1px solid rgba(139,124,248,.18)}
.btn-violet:hover{background:rgba(139,124,248,.14)}

/* TOOLBAR */
.toolbar{display:flex;gap:9px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.sw{position:relative;flex:1;min-width:180px}
.sw svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--tx3);pointer-events:none}
.sw input{padding-left:34px}
.chips{display:flex;gap:5px;flex-wrap:wrap}
.chip{
  padding:4px 12px;border-radius:20px;cursor:pointer;
  font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;
  border:1px solid var(--line);color:var(--tx3);background:transparent;transition:all .15s;
}
.chip.on{background:rgba(59,158,255,.09);border-color:rgba(59,158,255,.28);color:var(--blue)}
.chip:hover:not(.on){border-color:var(--line2);color:var(--tx2)}

/* TABLE */
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{
  font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--tx3);
  padding:8px 12px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;
}
td{padding:12px;border-bottom:1px solid rgba(255,255,255,.022);vertical-align:middle;font-size:13px}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .1s}
tbody tr:hover td{background:rgba(255,255,255,.013)}

.cn b{font-weight:600}
.cn small{font-size:11px;color:var(--tx3);display:block;margin-top:1px}

.etag{
  display:inline-block;background:rgba(139,124,248,.09);color:var(--violet);
  border:1px solid rgba(139,124,248,.18);border-radius:5px;
  padding:2px 8px;font-size:11px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}

.kchip{
  display:inline-flex;align-items:center;gap:6px;
  background:rgba(245,158,11,.07);color:var(--amber);
  border:1px solid rgba(245,158,11,.18);border-radius:6px;
  padding:4px 10px;cursor:pointer;
  font-family:'DM Mono',monospace;font-size:10px;
  transition:background .15s,transform .1s;
}
.kchip:hover{background:rgba(245,158,11,.13)}
.kchip:active{transform:scale(.97)}

.ex{font-size:12px}
.ex.exp{color:var(--red)}.ex.warn{color:var(--amber)}.ex.ok{color:var(--tx2)}.ex.none{color:var(--tx3)}

.pill{
  display:inline-flex;align-items:center;gap:5px;
  padding:4px 11px;border-radius:20px;cursor:pointer;
  font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1px;
  border:none;transition:all .15s;
}
.pill.on{background:rgba(34,201,138,.09);color:var(--green);border:1px solid rgba(34,201,138,.2)}
.pill.off{background:rgba(239,68,68,.08);color:var(--red);border:1px solid rgba(239,68,68,.18)}
.pill.on:hover{background:rgba(34,201,138,.16);transform:scale(1.04)}
.pill.off:hover{background:rgba(239,68,68,.14);transform:scale(1.04)}

.dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;display:inline-block}
.dot.on{background:var(--green);animation:blink 2s infinite}
.dot.off{background:var(--red)}

@keyframes blink{
  0%{box-shadow:0 0 0 0 rgba(34,201,138,.5)}
  70%{box-shadow:0 0 0 5px rgba(34,201,138,0)}
  100%{box-shadow:0 0 0 0 rgba(34,201,138,0)}
}

.del{
  background:none;border:none;color:var(--tx3);cursor:pointer;
  padding:5px 6px;border-radius:6px;transition:color .15s,background .15s;
}
.del:hover{color:var(--red);background:rgba(239,68,68,.08)}

.last{font-size:11px;color:var(--tx3)}
.last.fresh{color:var(--green)}

.badge{
  background:rgba(59,158,255,.09);color:var(--blue);
  border-radius:20px;padding:2px 9px;
  font-family:'DM Mono',monospace;font-size:11px;
}

/* LOGS */
.lw{
  background:var(--bg);border:1px solid var(--line);border-radius:8px;
  padding:13px;max-height:190px;overflow-y:auto;
  font-family:'DM Mono',monospace;font-size:10px;line-height:2;
}
.lr{display:flex;gap:9px;align-items:baseline}
.lt{color:var(--tx3);font-size:9px;flex-shrink:0}
.lok{color:var(--green)}.lfail{color:var(--red)}.linfo{color:var(--amber)}.lsys{color:var(--blue)}

/* TOAST */
.toast{
  position:fixed;bottom:22px;right:22px;z-index:999;
  background:var(--s2);border:1px solid var(--line2);
  padding:11px 16px;border-radius:9px;
  font-family:'DM Mono',monospace;font-size:10px;color:var(--tx);
  display:flex;align-items:center;gap:9px;
  box-shadow:0 8px 28px rgba(0,0,0,.55);
  opacity:0;transform:translateY(10px) scale(.97);
  transition:all .22s cubic-bezier(.34,1.3,.64,1);
  pointer-events:none;max-width:300px;
}
.toast.show{opacity:1;transform:none}
.tdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.tok{background:var(--green)}.terr{background:var(--red)}.twarn{background:var(--amber)}.tinfo{background:var(--blue)}

/* EMPTY */
.empty{text-align:center;padding:44px;color:var(--tx3);font-size:13px}
.ei{font-size:26px;opacity:.25;display:block;margin-bottom:8px}

/* ANIM */
@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

/* DM */
body.dm{--acc:#7c6fef;--acc2:#9488f8}
body.dm .ico{background:linear-gradient(140deg,#7c6fef,#5648cc);box-shadow:0 0 14px rgba(124,111,239,.3)}
body.dm .btn-main{background:var(--acc);box-shadow:0 2px 12px rgba(124,111,239,.28)}
body.dm .btn-main:hover{background:var(--acc2);box-shadow:0 2px 18px rgba(124,111,239,.42)}
body.dm .nav a.on{background:rgba(124,111,239,.1);border-color:rgba(124,111,239,.28);color:var(--acc2)}
body.dm input:focus,body.dm select:focus{border-color:rgba(124,111,239,.45);box-shadow:0 0 0 3px rgba(124,111,239,.06)}

@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.frow{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.kpis{grid-template-columns:1fr 1fr}.frow{grid-template-columns:1fr}.pacts{gap:4px}}
</style>
</head>
<body id="body">
<div class="page">

  <div class="bar">
    <div class="brand">
      <div class="ico">⚡</div>
      <div><div class="brand-nm">LUCS TECH</div><div class="brand-sub">GERENCIADOR DE LICENÇAS</div></div>
    </div>
    <nav class="nav"><a href="/app" id="nav-app">APP</a><a href="/dm" id="nav-dm">DM</a></nav>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="kpi-l">CLIENTES</div><div class="kpi-n" id="k-total">—</div></div>
    <div class="kpi"><div class="kpi-l">ATIVOS</div><div class="kpi-n" id="k-ativos">—</div></div>
    <div class="kpi"><div class="kpi-l">BLOQUEADOS</div><div class="kpi-n" id="k-bloq">—</div></div>
    <div class="kpi"><div class="kpi-l">LOGINS HOJE</div><div class="kpi-n" id="k-hoje">—</div></div>
  </div>

  <!-- CRIAR -->
  <div class="panel">
    <div class="ptitle" style="margin-bottom:16px">NOVA LICENÇA</div>
    <div class="frow">
      <div class="f"><label>NOME</label><input id="i-nome" type="text" placeholder="Nome do cliente"/></div>
      <div class="f"><label>EMPRESA</label><input id="i-empresa" type="text" placeholder="Empresa (opcional)"/></div>
      <div class="f"><label>E-MAIL</label><input id="i-email" type="email" placeholder="email@dominio.com"/></div>
      <div class="f"><label>DIAS</label><input id="i-dias" type="number" value="30" min="1"/></div>
      <button class="btn btn-main" id="btn-criar">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
        GERAR
      </button>
    </div>
  </div>

  <!-- TABELA -->
  <div class="panel">
    <div class="ph">
      <div style="display:flex;align-items:center;gap:9px">
        <div class="ptitle">LICENÇAS</div>
        <span class="badge" id="badge-n">0</span>
      </div>
      <div class="pacts">
        <a href="/admin/exportar-csv" class="btn btn-violet" download>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
          CSV
        </a>
        <button class="btn btn-ghost" id="btn-rel">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
          RELATÓRIO
        </button>
        <button class="btn btn-red" id="btn-bloqtodos">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
          BLOQUEAR TODOS
        </button>
      </div>
    </div>

    <div class="toolbar">
      <div class="sw">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input id="inp-q" type="text" placeholder="Buscar nome, empresa, chave, e-mail…"/>
      </div>
      <div class="chips">
        <button class="chip on" data-f="todos">TODOS</button>
        <button class="chip" data-f="ativo">ATIVOS</button>
        <button class="chip" data-f="bloqueado">BLOQUEADOS</button>
        <button class="chip" data-f="vencido">VENCIDOS</button>
      </div>
    </div>

    <div class="tw">
      <table>
        <thead><tr>
          <th>CLIENTE</th><th>EMPRESA</th><th>CHAVE</th>
          <th>VENCIMENTO</th><th>ÚLTIMO ACESSO</th><th>STATUS</th><th></th>
        </tr></thead>
        <tbody id="tbody">
          <tr><td colspan="7" class="empty"><span class="ei">⏳</span>Carregando…</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- LOGS -->
  <div class="panel">
    <div class="ph">
      <div class="ptitle">ATIVIDADE</div>
      <button class="btn btn-ghost" id="btn-limpar" style="font-size:9px;padding:7px 11px">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>
        LIMPAR
      </button>
    </div>
    <div class="lw" id="logs">Carregando…</div>
  </div>

</div>
<div class="toast" id="toast"><div class="tdot tok" id="tdot"></div><span id="tmsg"></span></div>

<script>
const MODO = document.body.dataset.modo||'app';
if(MODO==='dm') document.getElementById('body').classList.add('dm');
document.getElementById('nav-'+MODO).classList.add('on');

let allU=[], filtro='todos', busca='';

let _tt;
function toast(msg,tipo='ok'){
  document.getElementById('tdot').className='tdot t'+tipo;
  document.getElementById('tmsg').textContent=msg;
  const el=document.getElementById('toast');
  el.classList.add('show'); clearTimeout(_tt);
  _tt=setTimeout(()=>el.classList.remove('show'),2800);
}

function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fDate(s){return s?new Date(s+'T00:00:00').toLocaleDateString('pt-BR'):''}
function fDT(s){return s?new Date(s).toLocaleString('pt-BR'):null}
function ago(s){
  if(!s)return null;
  const d=Date.now()-new Date(s).getTime(),h=d/3600000;
  if(h<1)return'Agora há pouco';
  if(h<24)return Math.floor(h)+'h atrás';
  return fDT(s);
}
function exSt(s){
  if(!s)return'none';
  const d=new Date(s+'T00:00:00'),now=new Date();now.setHours(0,0,0,0);
  const dd=(d-now)/86400000;
  return dd<0?'exp':dd<=7?'warn':'ok';
}
function isExp(s){return s&&new Date(s+'T00:00:00')<new Date(new Date().toDateString())}

async function load(){
  try{
    const r=await fetch('/admin/dados');
    if(!r.ok)throw 0;
    const d=await r.json();
    if(!d.usuarios)return;
    allU=d.usuarios;
    document.getElementById('k-total').textContent=d.usuarios.length;
    document.getElementById('k-ativos').textContent=d.usuarios.filter(u=>u.ativo).length;
    document.getElementById('k-bloq').textContent=d.usuarios.filter(u=>!u.ativo).length;
    document.getElementById('k-hoje').textContent=d.logs_hoje;
    renderT();
    const lb=document.getElementById('logs');
    if(!d.logs.length){lb.innerHTML='<span style="color:var(--tx3)">Sem atividade.</span>';return}
    lb.innerHTML=d.logs.map(l=>{
      let cls,icon,lbl;
      if(l.acao==='login'){cls=l.sucesso?'lok':'lfail';icon=l.sucesso?'✓':'✗';lbl=l.sucesso?'LOGIN':'NEGADO'}
      else if(l.acao==='bloqueio_geral'){cls='lsys';icon='⚡';lbl='BLOQ. GERAL'}
      else{cls='linfo';icon='◆';lbl=(l.acao||'').toUpperCase()}
      const nm=l.nome?` <b>${esc(l.nome)}</b>`:'';
      const em=l.empresa?` <span style="color:var(--violet)">[${esc(l.empresa)}]</span>`:'';
      const ts=l.momento?new Date(l.momento).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
      return`<div class="lr"><span class="lt">${ts}</span><span class="${cls}">${icon} ${lbl}</span>${nm}${em} <span style="color:var(--tx3);font-size:9px">${esc(l.chave||'')}</span></div>`;
    }).join('');
  }catch(e){console.error(e)}
}

function renderT(){
  let list=allU.filter(u=>{
    if(filtro==='ativo')return u.ativo&&!isExp(u.expira);
    if(filtro==='bloqueado')return!u.ativo;
    if(filtro==='vencido')return isExp(u.expira);
    return true;
  });
  if(busca){const q=busca.toLowerCase();list=list.filter(u=>['nome','empresa','email','chave'].some(k=>(u[k]||'').toLowerCase().includes(q)))}
  document.getElementById('badge-n').textContent=list.length;
  const tb=document.getElementById('tbody');
  if(!list.length){tb.innerHTML=`<tr><td colspan="7" class="empty"><span class="ei">🔍</span>Nenhum resultado.</td></tr>`;return}
  const exLbl={exp:'Vencida ✗',warn:'Vence em breve',ok:'',none:'Sem limite'};
  tb.innerHTML=list.map(u=>{
    const es=exSt(u.expira);
    const exTxt=es==='ok'?fDate(u.expira):exLbl[es];
    const a=ago(u.ultimo_acesso);
    const fresh=u.ultimo_acesso&&(Date.now()-new Date(u.ultimo_acesso).getTime())<86400000;
    return`<tr>
      <td class="cn"><b>${esc(u.nome)}</b><small>${esc(u.email||'')}</small></td>
      <td>${u.empresa?`<span class="etag" title="${esc(u.empresa)}">${esc(u.empresa)}</span>`:'<span style="color:var(--tx3)">—</span>'}</td>
      <td><span class="kchip" data-k="${esc(u.chave)}">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="11" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
        ${esc(u.chave)}</span></td>
      <td><span class="ex ${es}">${exTxt}</span></td>
      <td><span class="last${fresh?' fresh':''}">${a||'<span style="color:var(--tx3)">Nunca</span>'}</span></td>
      <td><button class="pill ${u.ativo?'on':'off'}" data-k="${esc(u.chave)}">
        <span class="dot ${u.ativo?'on':'off'}"></span>${u.ativo?'ATIVO':'BLOQUEADO'}
      </button></td>
      <td><button class="del" data-k="${esc(u.chave)}">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>
      </button></td>
    </tr>`;
  }).join('');
  tb.querySelectorAll('.kchip').forEach(e=>e.onclick=()=>{navigator.clipboard.writeText(e.dataset.k);toast('Chave copiada','ok')});
  tb.querySelectorAll('.pill').forEach(e=>e.onclick=()=>tog(e.dataset.k));
  tb.querySelectorAll('.del').forEach(e=>e.onclick=()=>rem(e.dataset.k));
}

document.querySelectorAll('.chip').forEach(b=>{
  b.onclick=()=>{document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));b.classList.add('on');filtro=b.dataset.f;renderT()}
});
document.getElementById('inp-q').oninput=e=>{busca=e.target.value.trim();renderT()};

document.getElementById('btn-criar').onclick=async()=>{
  const nome=document.getElementById('i-nome').value.trim();
  const empresa=document.getElementById('i-empresa').value.trim();
  const email=document.getElementById('i-email').value.trim();
  const dias=document.getElementById('i-dias').value;
  if(!nome){toast('Informe o nome','warn');return}
  const btn=document.getElementById('btn-criar');
  btn.disabled=true;btn.textContent='…';
  try{
    const r=await fetch('/admin/criar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome,empresa,email,dias})});
    const d=await r.json();
    if(d.ok){toast(`Chave: ${d.chave}`,'ok');['i-nome','i-empresa','i-email'].forEach(id=>document.getElementById(id).value='');load()}
    else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexão','err')}
  finally{btn.disabled=false;btn.innerHTML='<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg> GERAR'}
};

async function tog(chave){
  try{
    const r=await fetch('/admin/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});
    const d=await r.json();
    if(d.ok){toast(d.ativo?'Ativado ✓':'Bloqueado 🔒',d.ativo?'ok':'warn');load()}
    else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexão','err')}
}

async function rem(chave){
  if(!confirm('Remover este cliente permanentemente?'))return;
  try{
    const r=await fetch('/admin/deletar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});
    const d=await r.json();
    if(d.ok){toast('Removido','info');load()}else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexão','err')}
}

document.getElementById('btn-bloqtodos').onclick=async()=>{
  const n=allU.filter(u=>u.ativo).length;
  if(!n){toast('Nenhum ativo','warn');return}
  if(!confirm(`Bloquear os ${n} clientes ativos?`))return;
  try{await fetch('/admin/bloquear-todos',{method:'POST'});toast(`${n} bloqueados`,'warn');load()}
  catch{toast('Erro','err')}
};

document.getElementById('btn-rel').onclick=()=>{
  if(!allU.length){toast('Sem dados','warn');return}
  const now=new Date().toLocaleString('pt-BR');
  const atv=allU.filter(u=>u.ativo).length;
  let t=`LUCS TECH — RELATÓRIO\nGerado: ${now}\n${'─'.repeat(50)}\n\nRESUMO\n  Total     : ${allU.length}\n  Ativos    : ${atv}\n  Bloqueados: ${allU.length-atv}\n\n${'─'.repeat(50)}\n\n`;
  allU.forEach((u,i)=>{
    t+=`${String(i+1).padStart(3,'0')}. ${u.nome}\n`;
    if(u.empresa)t+=`     Empresa   : ${u.empresa}\n`;
    if(u.email)t+=`     E-mail    : ${u.email}\n`;
    t+=`     Chave     : ${u.chave}\n     Status    : ${u.ativo?'ATIVO':'BLOQUEADO'}\n     Vencimento: ${u.expira?fDate(u.expira):'Sem limite'}\n     Últ.acesso: ${u.ultimo_acesso?fDT(u.ultimo_acesso):'Nunca'}\n\n`;
  });
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{type:'text/plain;charset=utf-8'}));
  a.download=`lucs-${Date.now()}.txt`;a.click();
  toast('Relatório exportado','ok');
};

document.getElementById('btn-limpar').onclick=async()=>{
  if(!confirm('Limpar logs de login?'))return;
  try{await fetch('/admin/limpar-logs',{method:'POST'});toast('Logs limpos','info');load()}
  catch{toast('Erro','err')}
};

load();
setInterval(load,15000);
</script>
</body>
</html>"""

# ══════════════════════════════════════════
#  ROTAS
# ══════════════════════════════════════════
@app.route("/")
def root():
    if os.path.exists('planejador.html'):
        return send_file('planejador.html')
    return redirect("/app")

@app.route("/app")
def pg_app():
    return render_template_string(HTML.replace('<body id="body">', '<body id="body" data-modo="app">'))

@app.route("/dm")
def pg_dm():
    return render_template_string(HTML.replace('<body id="body">', '<body id="body" data-modo="dm">'))

@app.route("/admin-sistema")
def legado():
    return redirect("/app")

# ══════════════════════════════════════════
#  API — VALIDAR
# ══════════════════════════════════════════
@app.route("/api/validar", methods=["POST"])
def validar():
    try:
        dados = request.json or {}
        chave = dados.get("chave","").strip()
        conn  = get_db(); cur = conn.cursor()

        cur.execute("SELECT nome, empresa, ativo, expira FROM usuarios WHERE chave=%s", (chave,))
        u = cur.fetchone()

        sucesso = 0
        nome = empresa = ""

        if u:
            nome    = u['nome']
            empresa = u['empresa'] or ''
            exp     = u['expira']
            if isinstance(exp, str):
                try: exp = date.fromisoformat(exp)
                except: exp = None
            vencido = exp and exp < datetime.now().date()
            ativo   = int(u['ativo']) if u['ativo'] is not None else 0
            if ativo == 1 and not vencido:
                sucesso = 1
                cur.execute("UPDATE usuarios SET ultimo_acesso=%s WHERE chave=%s", (datetime.now(), chave))

        cur.execute(
            "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (nome or None, empresa or None, chave, 'login', sucesso, datetime.now())
        )
        conn.commit(); cur.close(); conn.close()

        if sucesso:
            return jsonify({"ok": True, "nome": nome, "empresa": empresa})
        return jsonify({"ok": False, "msg": "Acesso negado"}), 403

    except Exception as e:
        print(f"[validar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — DADOS
# ══════════════════════════════════════════
@app.route("/admin/dados")
def admin_dados():
    try:
        conn = get_db(); cur = conn.cursor()

        cur.execute("SELECT nome,email,empresa,chave,ativo,expira,ultimo_acesso FROM usuarios ORDER BY id DESC")
        usuarios = []
        for r in cur.fetchall():
            d = row_to_dict(r)
            # normaliza ativo para bool de forma segura
            raw = r['ativo']
            if raw is None:
                d['ativo'] = False
            elif isinstance(raw, bool):
                d['ativo'] = raw
            else:
                d['ativo'] = int(raw) == 1
            usuarios.append(d)

        cur.execute("SELECT nome,empresa,chave,acao,sucesso,momento FROM logs ORDER BY id DESC LIMIT 100")
        logs = [row_to_dict(r) for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*) AS n FROM logs WHERE momento::date=CURRENT_DATE AND acao='login' AND sucesso=1")
        hoje = cur.fetchone()['n']

        cur.close(); conn.close()
        return jsonify({"usuarios": usuarios, "logs": logs, "logs_hoje": hoje})

    except Exception as e:
        print(f"[admin_dados] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — CRIAR
# ══════════════════════════════════════════
@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    try:
        d       = request.json or {}
        nome    = d.get('nome','').strip()
        empresa = (d.get('empresa') or '').strip() or None
        email   = (d.get('email')   or '').strip() or None
        dias    = int(d.get('dias') or 30)

        if not nome:
            return jsonify({"ok": False, "msg": "Nome obrigatório"}), 400

        exp   = datetime.now().date() + timedelta(days=dias)
        chave = nova_chave()

        conn = get_db(); cur = conn.cursor()

        chave_final = None
        for _ in range(10):
            try:
                cur.execute(
                    "INSERT INTO usuarios (nome,empresa,email,chave,expira,ativo,criado_em) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING chave",
                    (nome, empresa, email, chave, exp, 1, datetime.now())
                )
                chave_final = cur.fetchone()['chave']
                conn.commit()
                break
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                chave = nova_chave()

        if not chave_final:
            cur.close(); conn.close()
            return jsonify({"ok": False, "msg": "Não foi possível gerar chave única"}), 500

        cur.execute(
            "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (nome, empresa, chave_final, 'criacao', 1, datetime.now())
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True, "chave": chave_final})

    except Exception as e:
        print(f"[admin_criar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — TOGGLE  (0/1 explícito, sem NOT)
# ══════════════════════════════════════════
@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    try:
        chave = (request.json or {}).get('chave','')
        conn  = get_db(); cur = conn.cursor()

        cur.execute("SELECT nome, empresa, ativo FROM usuarios WHERE chave=%s", (chave,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"ok": False, "msg": "Chave não encontrada"}), 404

        # lê ativo como int de forma segura
        raw  = row['ativo']
        if raw is None:
            atual = 0
        elif isinstance(raw, bool):
            atual = 1 if raw else 0
        else:
            atual = int(raw)

        novo = 0 if atual == 1 else 1   # inverte com int puro

        cur.execute("UPDATE usuarios SET ativo=%s WHERE chave=%s", (novo, chave))
        conn.commit()

        acao = 'ativacao' if novo == 1 else 'bloqueio'
        cur.execute(
            "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (row['nome'], row['empresa'], chave, acao, 1, datetime.now())
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True, "ativo": bool(novo)})

    except Exception as e:
        print(f"[admin_toggle] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — DELETAR
# ══════════════════════════════════════════
@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    try:
        chave = (request.json or {}).get('chave','')
        conn  = get_db(); cur = conn.cursor()

        cur.execute("SELECT nome, empresa FROM usuarios WHERE chave=%s", (chave,))
        row  = cur.fetchone()
        nome    = row['nome']    if row else None
        empresa = row['empresa'] if row else None

        cur.execute("DELETE FROM logs WHERE chave=%s AND acao='login'", (chave,))
        cur.execute("DELETE FROM usuarios WHERE chave=%s", (chave,))
        if nome:
            cur.execute(
                "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
                (nome, empresa, chave, 'remocao', 1, datetime.now())
            )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})

    except Exception as e:
        print(f"[admin_deletar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — BLOQUEAR TODOS
# ══════════════════════════════════════════
@app.route("/admin/bloquear-todos", methods=["POST"])
def bloquear_todos():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET ativo=0 WHERE ativo=1")
        cur.execute(
            "INSERT INTO logs (nome,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s)",
            ('SISTEMA','TODOS','bloqueio_geral',1,datetime.now())
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[bloquear_todos] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — EXPORTAR CSV
# ══════════════════════════════════════════
@app.route("/admin/exportar-csv")
def exportar_csv():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome,empresa,email,chave,ativo,expira,criado_em,ultimo_acesso FROM usuarios ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()

        si = io.StringIO()
        w  = csv.writer(si, delimiter=';')
        w.writerow(['Nome','Empresa','E-mail','Chave','Ativo','Vencimento','Criado em','Último acesso'])
        for r in rows:
            raw_at = r['ativo']
            ativo_str = 'Sim' if (int(raw_at)==1 if raw_at is not None else False) else 'Não'
            w.writerow([
                r['nome'] or '',
                r['empresa'] or '',
                r['email'] or '',
                r['chave'] or '',
                ativo_str,
                r['expira'].isoformat() if r['expira'] else '',
                r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else '',
                r['ultimo_acesso'].strftime('%d/%m/%Y %H:%M') if r['ultimo_acesso'] else '',
            ])
        out = make_response(si.getvalue())
        out.headers["Content-Disposition"] = f"attachment; filename=lucs-{datetime.now().strftime('%Y%m%d')}.csv"
        out.headers["Content-type"] = "text/csv; charset=utf-8"
        return out
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — LIMPAR LOGS
# ══════════════════════════════════════════
@app.route("/admin/limpar-logs", methods=["POST"])
def limpar_logs():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM logs WHERE acao='login'")
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
