from flask import Flask, request, jsonify, render_template_string, send_file, redirect, make_response
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
import os, random, string, csv, io

app = Flask(__name__)

# ══════════════════════════════════════════
#  CONFIG
#  No Render → Environment Variables, coloque:
#  DATABASE_URL = postgresql://postgres:3HdV2,WYVktfrQS@db.xxx.supabase.co:5432/postgres
#  ADMIN_TOKEN  = sua-senha-aqui  (opcional)
# ══════════════════════════════════════════
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
ADMIN_TOKEN  = os.environ.get("ADMIN_TOKEN", "lucs2025")

# ══════════════════════════════════════════
#  BANCO — Supabase requer sslmode=require
# ══════════════════════════════════════════
def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode='require',
        cursor_factory=psycopg2.extras.RealDictCursor
    )

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
                plano         TEXT DEFAULT 'basic',
                obs           TEXT,
                criado_em     TIMESTAMP DEFAULT NOW(),
                ultimo_acesso TIMESTAMP,
                ip_ultimo     TEXT
            );
            CREATE TABLE IF NOT EXISTS logs (
                id      SERIAL PRIMARY KEY,
                nome    TEXT,
                empresa TEXT,
                chave   TEXT,
                acao    TEXT,
                sucesso INTEGER DEFAULT 1,
                momento TIMESTAMP DEFAULT NOW(),
                ip      TEXT,
                detalhe TEXT
            );
        """)
        conn.commit()

        # Migrations — adicionam colunas novas com segurança
        for sql in [
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS empresa TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS expira DATE",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plano TEXT DEFAULT 'basic'",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS obs TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_acesso TIMESTAMP",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ip_ultimo TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS nome TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS empresa TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS acao TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS ip TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS detalhe TEXT",
        ]:
            try: cur.execute(sql); conn.commit()
            except: conn.rollback()

        # Garante ativo como INTEGER (evita conflito com BOOLEAN)
        try:
            cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name='usuarios' AND column_name='ativo'")
            r = cur.fetchone()
            if r and r['data_type'] == 'boolean':
                cur.execute("ALTER TABLE usuarios ALTER COLUMN ativo TYPE INTEGER USING ativo::integer")
                conn.commit()
                print("[DB] ativo: BOOLEAN -> INTEGER OK")
        except Exception as e:
            conn.rollback(); print(f"[DB] aviso: {e}")

        cur.close(); conn.close()
        print("[DB] Supabase conectado e pronto ✓")
    except Exception as e:
        print(f"[DB] ERRO init: {e}")

with app.app_context():
    init_db()

# ══════════════════════════════════════════
#  HTML — PAINEL v2
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
  --bg:#07090f;--s1:#0c1018;--s2:#101520;--s3:#141b26;
  --line:rgba(255,255,255,.055);--line2:rgba(255,255,255,.1);
  --tx:#d8e8f5;--tx2:#7090a8;--tx3:#384e60;
  --acc:#e05c16;--acc2:#ff6a25;
  --blue:#3b9eff;--green:#22c98a;--red:#ef4444;--amber:#f59e0b;--violet:#8b7cf8;
  --r:11px;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(ellipse 700px 300px at 60% -50px,rgba(224,92,22,.06),transparent),
             radial-gradient(ellipse 500px 400px at 10% 80%,rgba(59,158,255,.04),transparent)}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--line2);border-radius:4px}
.page{max-width:1380px;margin:0 auto;padding:22px 18px;position:relative;z-index:1}

/* BAR */
.bar{display:flex;align-items:center;justify-content:space-between;background:var(--s1);border:1px solid var(--line);border-radius:var(--r);padding:13px 18px;margin-bottom:18px}
.brand{display:flex;align-items:center;gap:11px}
.ico{width:32px;height:32px;border-radius:8px;background:linear-gradient(140deg,var(--acc),#b84000);display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 0 14px rgba(224,92,22,.3);flex-shrink:0}
.brand-nm{font-family:'DM Mono',monospace;font-size:13px;letter-spacing:3px;color:var(--tx)}
.brand-sub{font-size:10px;color:var(--tx3);letter-spacing:1.5px;margin-top:1px}
.nav{display:flex;gap:5px}
.nav a,.nav button{text-decoration:none;padding:6px 13px;border-radius:7px;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--tx2);border:1px solid transparent;transition:all .15s;background:transparent;cursor:pointer}
.nav a.on,.nav button.on{background:rgba(224,92,22,.1);border-color:rgba(224,92,22,.28);color:var(--acc2)}
.nav a:hover:not(.on),.nav button:hover:not(.on){background:var(--s2);border-color:var(--line2);color:var(--tx)}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px}
.kpi{background:var(--s1);border:1px solid var(--line);border-radius:var(--r);padding:16px;position:relative;overflow:hidden;animation:up .35s ease both}
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.kpi:nth-child(1)::before{background:var(--blue)}.kpi:nth-child(2)::before{background:var(--green)}
.kpi:nth-child(3)::before{background:var(--red)}.kpi:nth-child(4)::before{background:var(--amber)}
.kpi:nth-child(5)::before{background:var(--violet)}.kpi:nth-child(6)::before{background:var(--acc)}
.kpi-l{font-family:'DM Mono',monospace;font-size:8px;letter-spacing:2.5px;color:var(--tx3);margin-bottom:7px}
.kpi-n{font-family:'DM Mono',monospace;font-size:28px;font-weight:500;line-height:1;letter-spacing:-1px}
.kpi-s{font-size:10px;color:var(--tx3);margin-top:5px}
.kpi:nth-child(1) .kpi-n{color:var(--blue)}.kpi:nth-child(2) .kpi-n{color:var(--green)}
.kpi:nth-child(3) .kpi-n{color:var(--red)}.kpi:nth-child(4) .kpi-n{color:var(--amber)}
.kpi:nth-child(5) .kpi-n{color:var(--violet)}.kpi:nth-child(6) .kpi-n{color:var(--acc2)}

/* PANEL */
.panel{background:var(--s1);border:1px solid var(--line);border-radius:var(--r);padding:20px;margin-bottom:14px;animation:up .35s .2s ease both}
.ph{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px}
.ptitle{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:3px;color:var(--tx3)}
.pacts{display:flex;gap:7px;align-items:center;flex-wrap:wrap}

/* TABS */
.tabs{display:flex;gap:0;border-bottom:1px solid var(--line);margin-bottom:20px}
.tab{padding:9px 18px;cursor:pointer;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--tx3);border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .15s;background:none;border-top:none;border-left:none;border-right:none}
.tab.on{color:var(--acc2);border-bottom-color:var(--acc2)}
.tab:hover:not(.on){color:var(--tx2)}
.tab-pane{display:none}.tab-pane.on{display:block}

/* FORM */
.fgrid{display:grid;grid-template-columns:1.2fr 1fr 1fr 100px 80px 80px auto;gap:9px;align-items:end}
.fgrid2{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:9px}
.f{display:flex;flex-direction:column;gap:5px}
.f label{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--tx3)}
input,select,textarea{background:var(--bg);border:1px solid var(--line2);padding:10px 12px;border-radius:8px;color:var(--tx);font-family:'DM Sans',sans-serif;font-size:13px;outline:none;transition:border-color .15s,box-shadow .15s;width:100%}
textarea{resize:vertical;min-height:68px}
input::placeholder,textarea::placeholder{color:var(--tx3)}
input:focus,select:focus,textarea:focus{border-color:rgba(224,92,22,.45);box-shadow:0 0 0 3px rgba(224,92,22,.06)}
select option{background:var(--s2)}

/* BTN */
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 14px;border-radius:8px;cursor:pointer;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1.5px;border:none;transition:all .15s;white-space:nowrap}
.btn-main{background:var(--acc);color:#fff;box-shadow:0 2px 12px rgba(224,92,22,.28)}
.btn-main:hover{background:var(--acc2);box-shadow:0 2px 18px rgba(224,92,22,.42)}
.btn-main:active{transform:scale(.97)}
.btn-ghost{background:transparent;color:var(--tx2);border:1px solid var(--line2)}
.btn-ghost:hover{background:var(--s2);border-color:var(--line2);color:var(--tx)}
.btn-red{background:rgba(239,68,68,.08);color:var(--red);border:1px solid rgba(239,68,68,.18)}
.btn-red:hover{background:rgba(239,68,68,.13);border-color:rgba(239,68,68,.28)}
.btn-violet{background:rgba(139,124,248,.08);color:var(--violet);border:1px solid rgba(139,124,248,.18)}
.btn-violet:hover{background:rgba(139,124,248,.14)}
.btn-green{background:rgba(34,201,138,.08);color:var(--green);border:1px solid rgba(34,201,138,.18)}
.btn-green:hover{background:rgba(34,201,138,.14)}
.btn-sm{padding:6px 10px;font-size:8px}
.btn:disabled{opacity:.4;cursor:not-allowed}

/* TOOLBAR */
.toolbar{display:flex;gap:9px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.sw{position:relative;flex:1;min-width:180px}
.sw svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--tx3);pointer-events:none}
.sw input{padding-left:34px}
.chips{display:flex;gap:5px;flex-wrap:wrap}
.chip{padding:4px 12px;border-radius:20px;cursor:pointer;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;border:1px solid var(--line);color:var(--tx3);background:transparent;transition:all .15s}
.chip.on{background:rgba(59,158,255,.09);border-color:rgba(59,158,255,.28);color:var(--blue)}
.chip:hover:not(.on){border-color:var(--line2);color:var(--tx2)}

/* TABLE */
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--tx3);padding:8px 12px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;cursor:pointer;user-select:none}
th:hover{color:var(--tx2)}
th .sort::after{content:'⇅';margin-left:3px;font-size:8px;opacity:.3}
th.asc .sort::after{content:'▲';opacity:1}
th.desc .sort::after{content:'▼';opacity:1}
td{padding:11px 12px;border-bottom:1px solid rgba(255,255,255,.022);vertical-align:middle;font-size:13px}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .1s}
tbody tr:hover td{background:rgba(255,255,255,.013)}
.cn b{font-weight:600}.cn small{font-size:11px;color:var(--tx3);display:block;margin-top:1px}
.etag{display:inline-block;background:rgba(139,124,248,.09);color:var(--violet);border:1px solid rgba(139,124,248,.18);border-radius:5px;padding:2px 8px;font-size:11px;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.plano-badge{display:inline-block;border-radius:5px;padding:2px 8px;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1px}
.pb-basic{background:rgba(112,144,168,.09);color:var(--tx2);border:1px solid rgba(112,144,168,.18)}
.pb-pro{background:rgba(59,158,255,.09);color:var(--blue);border:1px solid rgba(59,158,255,.18)}
.pb-enterprise{background:rgba(139,124,248,.09);color:var(--violet);border:1px solid rgba(139,124,248,.18)}
.kchip{display:inline-flex;align-items:center;gap:6px;background:rgba(245,158,11,.07);color:var(--amber);border:1px solid rgba(245,158,11,.18);border-radius:6px;padding:4px 10px;cursor:pointer;font-family:'DM Mono',monospace;font-size:10px;transition:background .15s,transform .1s}
.kchip:hover{background:rgba(245,158,11,.13)}.kchip:active{transform:scale(.97)}
.ex{font-size:12px}.ex.exp{color:var(--red)}.ex.warn{color:var(--amber)}.ex.ok{color:var(--tx2)}.ex.none{color:var(--tx3)}
.pill{display:inline-flex;align-items:center;gap:5px;padding:4px 11px;border-radius:20px;cursor:pointer;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1px;border:none;transition:all .15s}
.pill.on{background:rgba(34,201,138,.09);color:var(--green);border:1px solid rgba(34,201,138,.2)}
.pill.off{background:rgba(239,68,68,.08);color:var(--red);border:1px solid rgba(239,68,68,.18)}
.pill.on:hover{background:rgba(34,201,138,.16);transform:scale(1.04)}
.pill.off:hover{background:rgba(239,68,68,.14);transform:scale(1.04)}
.dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;display:inline-block}
.dot.on{background:var(--green);animation:blink 2s infinite}.dot.off{background:var(--red)}
.del{background:none;border:none;color:var(--tx3);cursor:pointer;padding:5px 6px;border-radius:6px;transition:color .15s,background .15s}
.del:hover{color:var(--red);background:rgba(239,68,68,.08)}
.edit-btn{background:none;border:none;color:var(--tx3);cursor:pointer;padding:5px 6px;border-radius:6px;transition:color .15s,background .15s}
.edit-btn:hover{color:var(--blue);background:rgba(59,158,255,.08)}
.last{font-size:11px;color:var(--tx3)}.last.fresh{color:var(--green)}
.badge{background:rgba(59,158,255,.09);color:var(--blue);border-radius:20px;padding:2px 9px;font-family:'DM Mono',monospace;font-size:11px}

/* MODAL */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .2s;backdrop-filter:blur(4px)}
.overlay.open{opacity:1;pointer-events:all}
.modal{background:var(--s1);border:1px solid var(--line2);border-radius:14px;padding:24px;width:100%;max-width:520px;max-height:90vh;overflow-y:auto;transform:translateY(12px) scale(.98);transition:transform .22s cubic-bezier(.34,1.3,.64,1)}
.overlay.open .modal{transform:none}
.modal-h{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.modal-t{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:2.5px;color:var(--tx3)}
.modal-x{background:none;border:none;color:var(--tx3);cursor:pointer;font-size:18px;padding:2px 6px;border-radius:6px;transition:color .15s}
.modal-x:hover{color:var(--red)}
.mgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.mgrid.full{grid-template-columns:1fr}
.renew-opts{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
.roption{padding:6px 14px;border-radius:8px;cursor:pointer;font-family:'DM Mono',monospace;font-size:10px;border:1px solid var(--line);color:var(--tx3);background:transparent;transition:all .15s}
.roption.on{background:rgba(34,201,138,.1);border-color:rgba(34,201,138,.3);color:var(--green)}
.roption:hover:not(.on){border-color:var(--line2);color:var(--tx2)}

/* STATS */
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.stat-box{background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:16px}
.stat-title{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--tx3);margin-bottom:12px}
.bar-item{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-size:12px}
.bar-label{width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--tx2);flex-shrink:0}
.bar-track{flex:1;height:5px;background:var(--line);border-radius:3px;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;transition:width .6s ease}
.bar-val{width:28px;text-align:right;font-family:'DM Mono',monospace;font-size:10px;color:var(--tx3);flex-shrink:0}
.donut-wrap{display:flex;align-items:center;gap:16px}
.donut-leg{flex:1}
.dl{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12px;color:var(--tx2)}
.dl-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dl-val{margin-left:auto;font-family:'DM Mono',monospace;font-size:11px}

/* LOGS */
.lw{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:13px;max-height:240px;overflow-y:auto;font-family:'DM Mono',monospace;font-size:10px;line-height:2}
.lr{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap}
.lt{color:var(--tx3);font-size:9px;flex-shrink:0}
.lok{color:var(--green)}.lfail{color:var(--red)}.linfo{color:var(--amber)}.lsys{color:var(--blue)}
.lip{font-size:9px;color:var(--tx3);margin-left:auto}

/* HEALTH */
.health{display:flex;align-items:center;gap:7px;font-family:'DM Mono',monospace;font-size:9px;color:var(--tx3)}
.hdot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:blink 2s infinite}
.hdot.err{background:var(--red);animation:none}

/* TOAST */
.toast{position:fixed;bottom:22px;right:22px;z-index:999;background:var(--s2);border:1px solid var(--line2);padding:11px 16px;border-radius:9px;font-family:'DM Mono',monospace;font-size:10px;color:var(--tx);display:flex;align-items:center;gap:9px;box-shadow:0 8px 28px rgba(0,0,0,.55);opacity:0;transform:translateY(10px) scale(.97);transition:all .22s cubic-bezier(.34,1.3,.64,1);pointer-events:none;max-width:300px}
.toast.show{opacity:1;transform:none}
.tdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.tok{background:var(--green)}.terr{background:var(--red)}.twarn{background:var(--amber)}.tinfo{background:var(--blue)}
.empty{text-align:center;padding:44px;color:var(--tx3);font-size:13px}
.ei{font-size:26px;opacity:.25;display:block;margin-bottom:8px}

@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes blink{0%{box-shadow:0 0 0 0 rgba(34,201,138,.5)}70%{box-shadow:0 0 0 5px rgba(34,201,138,0)}100%{box-shadow:0 0 0 0 rgba(34,201,138,0)}}

body.dm{--acc:#7c6fef;--acc2:#9488f8}
body.dm .ico{background:linear-gradient(140deg,#7c6fef,#5648cc);box-shadow:0 0 14px rgba(124,111,239,.3)}
body.dm .btn-main{background:var(--acc);box-shadow:0 2px 12px rgba(124,111,239,.28)}
body.dm .btn-main:hover{background:var(--acc2)}
body.dm .nav a.on,body.dm .nav button.on{background:rgba(124,111,239,.1);border-color:rgba(124,111,239,.28);color:var(--acc2)}
body.dm input:focus,body.dm select:focus,body.dm textarea:focus{border-color:rgba(124,111,239,.45);box-shadow:0 0 0 3px rgba(124,111,239,.06)}

@media(max-width:1100px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.fgrid{grid-template-columns:1fr 1fr}.stat-grid{grid-template-columns:1fr}}
@media(max-width:560px){.kpis{grid-template-columns:1fr 1fr}.mgrid{grid-template-columns:1fr}}
</style>
</head>
<body id="body">
<div class="page">

  <div class="bar">
    <div class="brand">
      <div class="ico">⚡</div>
      <div><div class="brand-nm">LUCS TECH</div><div class="brand-sub">GERENCIADOR DE LICENÇAS v2</div></div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <div class="health"><div class="hdot" id="hdot"></div><span id="hstatus">CONECTANDO…</span></div>
      <nav class="nav"><a href="/app" id="nav-app">APP</a><a href="/dm" id="nav-dm">DM</a></nav>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="kpi-l">TOTAL</div><div class="kpi-n" id="k-total">—</div><div class="kpi-s">clientes</div></div>
    <div class="kpi"><div class="kpi-l">ATIVOS</div><div class="kpi-n" id="k-ativos">—</div><div class="kpi-s" id="k-ativos-pct">—</div></div>
    <div class="kpi"><div class="kpi-l">BLOQUEADOS</div><div class="kpi-n" id="k-bloq">—</div><div class="kpi-s" id="k-bloq-pct">—</div></div>
    <div class="kpi"><div class="kpi-l">VENCIDOS</div><div class="kpi-n" id="k-venc">—</div><div class="kpi-s">expirados</div></div>
    <div class="kpi"><div class="kpi-l">LOGINS HOJE</div><div class="kpi-n" id="k-hoje">—</div><div class="kpi-s">autenticações</div></div>
    <div class="kpi"><div class="kpi-l">NEGADOS HOJE</div><div class="kpi-n" id="k-negados">—</div><div class="kpi-s">bloqueados</div></div>
  </div>

  <div class="panel" style="padding-bottom:0">
    <div class="tabs">
      <button class="tab on" data-tab="licencas">LICENÇAS</button>
      <button class="tab" data-tab="nova">NOVA LICENÇA</button>
      <button class="tab" data-tab="stats">ESTATÍSTICAS</button>
      <button class="tab" data-tab="logs">ATIVIDADE</button>
    </div>

    <!-- LICENÇAS -->
    <div class="tab-pane on" id="tab-licencas" style="padding-bottom:20px">
      <div class="ph" style="margin-top:4px">
        <div style="display:flex;align-items:center;gap:9px">
          <div class="ptitle">LICENÇAS CADASTRADAS</div>
          <span class="badge" id="badge-n">0</span>
        </div>
        <div class="pacts">
          <a href="/admin/exportar-csv" class="btn btn-violet btn-sm" download>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>CSV
          </a>
          <button class="btn btn-ghost btn-sm" id="btn-rel">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>TXT
          </button>
          <button class="btn btn-green btn-sm" id="btn-renovar-venc">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>RENOVAR VENCIDOS
          </button>
          <button class="btn btn-red btn-sm" id="btn-bloqtodos">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>BLOQUEAR TODOS
          </button>
        </div>
      </div>
      <div class="toolbar">
        <div class="sw">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input id="inp-q" type="text" placeholder="Buscar nome, empresa, chave, e-mail, plano…"/>
        </div>
        <div class="chips">
          <button class="chip on" data-f="todos">TODOS</button>
          <button class="chip" data-f="ativo">ATIVOS</button>
          <button class="chip" data-f="bloqueado">BLOQUEADOS</button>
          <button class="chip" data-f="vencido">VENCIDOS</button>
          <button class="chip" data-f="vence7">VENCE EM 7D</button>
        </div>
      </div>
      <div class="tw">
        <table>
          <thead><tr>
            <th data-col="nome">CLIENTE<span class="sort"></span></th>
            <th data-col="empresa">EMPRESA<span class="sort"></span></th>
            <th>PLANO</th>
            <th data-col="chave">CHAVE<span class="sort"></span></th>
            <th data-col="expira">VENCIMENTO<span class="sort"></span></th>
            <th data-col="ultimo_acesso">ÚLTIMO ACESSO<span class="sort"></span></th>
            <th>STATUS</th>
            <th></th>
          </tr></thead>
          <tbody id="tbody"><tr><td colspan="8" class="empty"><span class="ei">⏳</span>Carregando…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- NOVA LICENÇA -->
    <div class="tab-pane" id="tab-nova" style="padding-bottom:20px">
      <div class="ptitle" style="margin-bottom:16px;margin-top:4px">CRIAR NOVA LICENÇA</div>
      <div class="fgrid">
        <div class="f"><label>NOME *</label><input id="i-nome" type="text" placeholder="Nome completo do cliente"/></div>
        <div class="f"><label>EMPRESA</label><input id="i-empresa" type="text" placeholder="Empresa (opcional)"/></div>
        <div class="f"><label>E-MAIL</label><input id="i-email" type="email" placeholder="email@dominio.com"/></div>
        <div class="f"><label>PLANO</label>
          <select id="i-plano"><option value="basic">BASIC</option><option value="pro">PRO</option><option value="enterprise">ENTERPRISE</option></select>
        </div>
        <div class="f"><label>DIAS</label><input id="i-dias" type="number" value="30" min="1" max="3650"/></div>
        <div class="f"><label>ILIMITADO</label>
          <select id="i-ilimitado"><option value="0">NÃO</option><option value="1">SIM</option></select>
        </div>
        <button class="btn btn-main" id="btn-criar" style="align-self:end">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>GERAR
        </button>
      </div>
      <div class="fgrid2">
        <div class="f"><label>OBSERVAÇÕES</label><textarea id="i-obs" placeholder="Notas internas sobre este cliente…"></textarea></div>
        <div class="f" style="background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:14px">
          <div class="ptitle" style="margin-bottom:10px">CHAVE GERADA</div>
          <div id="preview-chave" style="font-family:'DM Mono',monospace;font-size:13px;color:var(--tx3)">— aguardando —</div>
          <div id="preview-info" style="font-size:11px;color:var(--tx3);margin-top:8px"></div>
        </div>
      </div>
    </div>

    <!-- STATS -->
    <div class="tab-pane" id="tab-stats" style="padding-bottom:20px">
      <div class="stat-grid">
        <div class="stat-box"><div class="stat-title">TOP EMPRESAS</div><div id="st-empresas"></div></div>
        <div class="stat-box"><div class="stat-title">DISTRIBUIÇÃO POR PLANO</div>
          <div class="donut-wrap"><canvas id="donut-canvas" width="90" height="90"></canvas><div class="donut-leg" id="donut-leg"></div></div>
        </div>
        <div class="stat-box"><div class="stat-title">LOGINS — ÚLTIMOS 7 DIAS</div>
          <canvas id="spark-canvas" style="width:100%;height:60px;display:block"></canvas>
          <div id="spark-labels" style="display:flex;justify-content:space-between;font-family:'DM Mono',monospace;font-size:8px;color:var(--tx3);margin-top:4px"></div>
        </div>
      </div>
    </div>

    <!-- LOGS -->
    <div class="tab-pane" id="tab-logs" style="padding-bottom:20px">
      <div class="ph" style="margin-top:4px">
        <div class="ptitle">ATIVIDADE RECENTE</div>
        <div style="display:flex;gap:7px">
          <button class="btn btn-ghost btn-sm" id="btn-exp-logs">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>EXPORTAR
          </button>
          <button class="btn btn-red btn-sm" id="btn-limpar">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>LIMPAR
          </button>
        </div>
      </div>
      <div class="lw" id="logs">Carregando…</div>
    </div>
  </div>
</div>

<!-- MODAL EDITAR -->
<div class="overlay" id="modal-overlay">
  <div class="modal">
    <div class="modal-h">
      <div class="modal-t">EDITAR LICENÇA</div>
      <button class="modal-x" id="modal-close">✕</button>
    </div>
    <div class="mgrid" style="margin-bottom:12px">
      <div class="f"><label>NOME</label><input id="m-nome" type="text"/></div>
      <div class="f"><label>E-MAIL</label><input id="m-email" type="email"/></div>
      <div class="f"><label>EMPRESA</label><input id="m-empresa" type="text"/></div>
      <div class="f"><label>PLANO</label>
        <select id="m-plano"><option value="basic">BASIC</option><option value="pro">PRO</option><option value="enterprise">ENTERPRISE</option></select>
      </div>
    </div>
    <div class="f mgrid full" style="margin-bottom:12px">
      <label>OBSERVAÇÕES</label><textarea id="m-obs"></textarea>
    </div>
    <div class="f" style="margin-bottom:18px">
      <label>RENOVAR LICENÇA</label>
      <div class="renew-opts">
        <button class="roption on" data-d="0">SEM ALTERAÇÃO</button>
        <button class="roption" data-d="7">+7 DIAS</button>
        <button class="roption" data-d="30">+30 DIAS</button>
        <button class="roption" data-d="90">+90 DIAS</button>
        <button class="roption" data-d="365">+1 ANO</button>
        <button class="roption" data-d="-1">ILIMITADO</button>
      </div>
    </div>
    <input type="hidden" id="m-chave"/>
    <div style="display:flex;gap:9px;justify-content:flex-end">
      <button class="btn btn-ghost" id="modal-cancel">CANCELAR</button>
      <button class="btn btn-main" id="modal-save">SALVAR ALTERAÇÕES</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"><div class="tdot tok" id="tdot"></div><span id="tmsg"></span></div>

<script>
const MODO=document.body.dataset.modo||'app';
if(MODO==='dm')document.getElementById('body').classList.add('dm');
document.getElementById('nav-'+MODO).classList.add('on');

let allU=[],allLogs=[],filtro='todos',busca='',sortCol='',sortDir=1,editDias=0;

let _tt;
function toast(msg,tipo='ok'){
  document.getElementById('tdot').className='tdot t'+tipo;
  document.getElementById('tmsg').textContent=msg;
  const el=document.getElementById('toast');
  el.classList.add('show');clearTimeout(_tt);
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
  if(h<48)return'Ontem';
  return fDT(s);
}
function exSt(s){
  if(!s)return'none';
  const d=new Date(s+'T00:00:00'),now=new Date();now.setHours(0,0,0,0);
  const dd=(d-now)/86400000;
  return dd<0?'exp':dd<=7?'warn':'ok';
}
function isExp(s){return s&&new Date(s+'T00:00:00')<new Date(new Date().toDateString())}
function vence7(s){
  if(!s)return false;
  const d=new Date(s+'T00:00:00'),now=new Date();now.setHours(0,0,0,0);
  const dd=(d-now)/86400000;
  return dd>=0&&dd<=7;
}
function planoCls(p){return p==='pro'?'pb-pro':p==='enterprise'?'pb-enterprise':'pb-basic'}

// TABS
document.querySelectorAll('.tab').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    document.querySelectorAll('.tab-pane').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    document.getElementById('tab-'+b.dataset.tab).classList.add('on');
    if(b.dataset.tab==='stats')renderStats();
  }
});

// LOAD
async function load(){
  try{
    const r=await fetch('/admin/dados');
    if(!r.ok)throw 0;
    const d=await r.json();
    if(!d.usuarios)return;
    allU=d.usuarios; allLogs=d.logs||[];
    const total=allU.length;
    const ativos=allU.filter(u=>u.ativo&&!isExp(u.expira)).length;
    const bloq=allU.filter(u=>!u.ativo).length;
    const venc=allU.filter(u=>isExp(u.expira)).length;
    document.getElementById('k-total').textContent=total;
    document.getElementById('k-ativos').textContent=ativos;
    document.getElementById('k-ativos-pct').textContent=total?Math.round(ativos/total*100)+'% do total':'—';
    document.getElementById('k-bloq').textContent=bloq;
    document.getElementById('k-bloq-pct').textContent=total?Math.round(bloq/total*100)+'% do total':'—';
    document.getElementById('k-venc').textContent=venc;
    document.getElementById('k-hoje').textContent=d.logs_hoje||0;
    document.getElementById('k-negados').textContent=d.negados_hoje||0;
    document.getElementById('hdot').className='hdot';
    document.getElementById('hstatus').textContent='SUPABASE OK';
    renderT(); renderLogs();
  }catch(e){
    document.getElementById('hdot').className='hdot err';
    document.getElementById('hstatus').textContent='ERRO BD';
  }
}

function renderT(){
  let list=[...allU];
  if(filtro==='ativo')list=list.filter(u=>u.ativo&&!isExp(u.expira));
  else if(filtro==='bloqueado')list=list.filter(u=>!u.ativo);
  else if(filtro==='vencido')list=list.filter(u=>isExp(u.expira));
  else if(filtro==='vence7')list=list.filter(u=>vence7(u.expira));
  if(busca){const q=busca.toLowerCase();list=list.filter(u=>['nome','empresa','email','chave','plano'].some(k=>(u[k]||'').toLowerCase().includes(q)))}
  if(sortCol)list.sort((a,b)=>String(a[sortCol]||'').localeCompare(String(b[sortCol]||''))*sortDir);
  document.getElementById('badge-n').textContent=list.length;
  const tb=document.getElementById('tbody');
  if(!list.length){tb.innerHTML=`<tr><td colspan="8" class="empty"><span class="ei">🔍</span>Nenhum resultado.</td></tr>`;return}
  const exLbl={exp:'Vencida ✗',warn:'Vence em breve',ok:'',none:'Sem limite'};
  tb.innerHTML=list.map(u=>{
    const es=exSt(u.expira);
    const exTxt=es==='ok'?fDate(u.expira):exLbl[es];
    const a=ago(u.ultimo_acesso);
    const fresh=u.ultimo_acesso&&(Date.now()-new Date(u.ultimo_acesso).getTime())<3600000;
    const plano=u.plano||'basic';
    const ud=JSON.stringify(u).replace(/"/g,'&quot;');
    return`<tr>
      <td class="cn"><b>${esc(u.nome)}</b><small>${esc(u.email||'')}</small></td>
      <td>${u.empresa?`<span class="etag" title="${esc(u.empresa)}">${esc(u.empresa)}</span>`:'<span style="color:var(--tx3)">—</span>'}</td>
      <td><span class="plano-badge ${planoCls(plano)}">${plano.toUpperCase()}</span></td>
      <td><span class="kchip" data-k="${esc(u.chave)}">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="11" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>${esc(u.chave)}</span></td>
      <td><span class="ex ${es}" title="${u.expira||'sem limite'}">${exTxt||'—'}</span></td>
      <td><span class="last${fresh?' fresh':''}">${a||'<span style="color:var(--tx3)">Nunca</span>'}</span></td>
      <td><button class="pill ${u.ativo?'on':'off'}" data-k="${esc(u.chave)}"><span class="dot ${u.ativo?'on':'off'}"></span>${u.ativo?'ATIVO':'BLOQUEADO'}</button></td>
      <td style="display:flex;gap:4px">
        <button class="edit-btn" data-ud="${ud}" title="Editar"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
        <button class="del" data-k="${esc(u.chave)}" title="Remover"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg></button>
      </td></tr>`;
  }).join('');
  tb.querySelectorAll('.kchip').forEach(e=>e.onclick=()=>{navigator.clipboard.writeText(e.dataset.k);toast('Chave copiada ✓','ok')});
  tb.querySelectorAll('.pill').forEach(e=>e.onclick=()=>tog(e.dataset.k));
  tb.querySelectorAll('.del').forEach(e=>e.onclick=()=>rem(e.dataset.k));
  tb.querySelectorAll('.edit-btn').forEach(e=>e.onclick=()=>{
    try{openEdit(JSON.parse(e.dataset.ud.replace(/&quot;/g,'"')))}catch{}
  });
}

// SORT
document.querySelectorAll('th[data-col]').forEach(th=>{
  th.onclick=()=>{
    const col=th.dataset.col;
    if(sortCol===col)sortDir*=-1;else{sortCol=col;sortDir=1}
    document.querySelectorAll('th[data-col]').forEach(t=>t.classList.remove('asc','desc'));
    th.classList.add(sortDir===1?'asc':'desc');
    renderT();
  }
});
document.querySelectorAll('.chip').forEach(b=>{
  b.onclick=()=>{document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));b.classList.add('on');filtro=b.dataset.f;renderT()}
});
document.getElementById('inp-q').oninput=e=>{busca=e.target.value.trim();renderT()};

// CRIAR
document.getElementById('btn-criar').onclick=async()=>{
  const nome=document.getElementById('i-nome').value.trim();
  if(!nome){toast('Informe o nome','warn');return}
  const btn=document.getElementById('btn-criar');
  btn.disabled=true;btn.textContent='…';
  try{
    const r=await fetch('/admin/criar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      nome,
      empresa:document.getElementById('i-empresa').value.trim(),
      email:document.getElementById('i-email').value.trim(),
      plano:document.getElementById('i-plano').value,
      dias:document.getElementById('i-dias').value,
      ilimitado:document.getElementById('i-ilimitado').value==='1',
      obs:document.getElementById('i-obs').value.trim()
    })});
    const d=await r.json();
    if(d.ok){
      document.getElementById('preview-chave').textContent=d.chave;
      document.getElementById('preview-chave').style.color='var(--amber)';
      document.getElementById('preview-info').textContent=`Criado ${new Date().toLocaleString('pt-BR')} · ${document.getElementById('i-plano').value.toUpperCase()} · ${document.getElementById('i-ilimitado').value==='1'?'Sem limite':document.getElementById('i-dias').value+' dias'}`;
      toast(`Chave: ${d.chave}`,'ok');
      ['i-nome','i-empresa','i-email','i-obs'].forEach(id=>document.getElementById(id).value='');
      load();
    }else toast(d.msg||'Erro','err');
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

document.getElementById('btn-renovar-venc').onclick=async()=>{
  const venc=allU.filter(u=>isExp(u.expira));
  if(!venc.length){toast('Nenhum vencido','warn');return}
  const dias=prompt(`Renovar ${venc.length} licença(s) vencida(s) por quantos dias?`,'30');
  if(!dias||isNaN(dias))return;
  try{
    const r=await fetch('/admin/renovar-vencidos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dias:parseInt(dias)})});
    const d=await r.json();
    if(d.ok){toast(`${venc.length} renovados por ${dias} dias`,'ok');load()}
    else toast(d.msg||'Erro','err');
  }catch{toast('Erro','err')}
};

// MODAL EDITAR
let editChave='';
function openEdit(u){
  editChave=u.chave;editDias=0;
  document.getElementById('m-nome').value=u.nome||'';
  document.getElementById('m-email').value=u.email||'';
  document.getElementById('m-empresa').value=u.empresa||'';
  document.getElementById('m-plano').value=u.plano||'basic';
  document.getElementById('m-obs').value=u.obs||'';
  document.querySelectorAll('.roption').forEach(b=>b.classList.remove('on'));
  document.querySelector('.roption[data-d="0"]').classList.add('on');
  document.getElementById('modal-overlay').classList.add('open');
}
document.querySelectorAll('.roption').forEach(b=>{
  b.onclick=()=>{document.querySelectorAll('.roption').forEach(x=>x.classList.remove('on'));b.classList.add('on');editDias=parseInt(b.dataset.d)}
});
function closeModal(){document.getElementById('modal-overlay').classList.remove('open')}
document.getElementById('modal-close').onclick=closeModal;
document.getElementById('modal-cancel').onclick=closeModal;
document.getElementById('modal-overlay').onclick=e=>{if(e.target===e.currentTarget)closeModal()};
document.getElementById('modal-save').onclick=async()=>{
  try{
    const r=await fetch('/admin/editar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      chave:editChave,
      nome:document.getElementById('m-nome').value.trim(),
      email:document.getElementById('m-email').value.trim(),
      empresa:document.getElementById('m-empresa').value.trim(),
      plano:document.getElementById('m-plano').value,
      obs:document.getElementById('m-obs').value.trim(),
      renovar_dias:editDias
    })});
    const d=await r.json();
    if(d.ok){toast('Salvo ✓','ok');closeModal();load()}
    else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexão','err')}
};

// LOGS
function renderLogs(){
  const lb=document.getElementById('logs');
  if(!allLogs.length){lb.innerHTML='<span style="color:var(--tx3)">Sem atividade.</span>';return}
  lb.innerHTML=allLogs.map(l=>{
    let cls,icon,lbl;
    if(l.acao==='login'){cls=l.sucesso?'lok':'lfail';icon=l.sucesso?'✓':'✗';lbl=l.sucesso?'LOGIN':'NEGADO'}
    else if(l.acao==='bloqueio_geral'){cls='lsys';icon='⚡';lbl='BLOQ.GERAL'}
    else if(l.acao==='criacao'){cls='linfo';icon='✦';lbl='CRIAÇÃO'}
    else if(l.acao==='edicao'){cls='linfo';icon='✎';lbl='EDIÇÃO'}
    else if(l.acao==='renovacao'){cls='lok';icon='↺';lbl='RENOVAÇÃO'}
    else{cls='linfo';icon='◆';lbl=(l.acao||'').toUpperCase()}
    const nm=l.nome?` <b>${esc(l.nome)}</b>`:'';
    const em=l.empresa?` <span style="color:var(--violet)">[${esc(l.empresa)}]</span>`:'';
    const ts=l.momento?new Date(l.momento).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
    const ip=l.ip?`<span class="lip">${esc(l.ip)}</span>`:'';
    return`<div class="lr"><span class="lt">${ts}</span><span class="${cls}">${icon} ${lbl}</span>${nm}${em}<span style="color:var(--tx3);font-size:9px">${esc(l.chave||'')}</span>${ip}</div>`;
  }).join('');
}

// STATS
function renderStats(){
  const emp={};
  allU.forEach(u=>{if(u.empresa)emp[u.empresa]=(emp[u.empresa]||0)+1});
  const topEmp=Object.entries(emp).sort((a,b)=>b[1]-a[1]).slice(0,6);
  const maxE=topEmp[0]?.[1]||1;
  const colors=['var(--blue)','var(--green)','var(--acc2)','var(--violet)','var(--amber)','var(--red)'];
  document.getElementById('st-empresas').innerHTML=topEmp.length
    ?topEmp.map(([nm,n],i)=>`<div class="bar-item"><span class="bar-label" title="${esc(nm)}">${esc(nm)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.round(n/maxE*100)}%;background:${colors[i%colors.length]}"></div></div><span class="bar-val">${n}</span></div>`).join('')
    :'<span style="color:var(--tx3);font-size:12px">Sem dados</span>';

  const planos={basic:0,pro:0,enterprise:0};
  allU.forEach(u=>planos[u.plano||'basic']=(planos[u.plano||'basic']||0)+1);
  const pColors={basic:'#7090a8',pro:'#3b9eff',enterprise:'#8b7cf8'};
  const total=allU.length||1;
  const dc=document.getElementById('donut-canvas');
  const ctx=dc.getContext('2d');
  ctx.clearRect(0,0,90,90);
  let start=-Math.PI/2;
  Object.entries(planos).forEach(([p,n])=>{
    const slice=(n/total)*Math.PI*2;
    ctx.beginPath();ctx.moveTo(45,45);ctx.arc(45,45,40,start,start+slice);ctx.fillStyle=pColors[p];ctx.fill();
    start+=slice;
  });
  ctx.beginPath();ctx.arc(45,45,22,0,Math.PI*2);ctx.fillStyle='#0c1018';ctx.fill();
  document.getElementById('donut-leg').innerHTML=Object.entries(planos).map(([p,n])=>`<div class="dl"><div class="dl-dot" style="background:${pColors[p]}"></div>${p.toUpperCase()}<span class="dl-val">${n}</span></div>`).join('');

  const dias7=[],labels7=[];
  for(let i=6;i>=0;i--){
    const d=new Date();d.setDate(d.getDate()-i);
    const iso=d.toISOString().slice(0,10);
    dias7.push(allLogs.filter(l=>l.acao==='login'&&l.sucesso&&(l.momento||'').slice(0,10)===iso).length);
    labels7.push(d.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'}));
  }
  const sc=document.getElementById('spark-canvas');
  sc.width=sc.parentElement.clientWidth||300;sc.height=60;
  const sx=sc.getContext('2d');
  const maxS=Math.max(...dias7,1),w=sc.width,pts=dias7.length,step=w/(pts-1);
  const grad=sx.createLinearGradient(0,0,0,60);
  grad.addColorStop(0,'rgba(59,158,255,.35)');grad.addColorStop(1,'rgba(59,158,255,0)');
  sx.beginPath();sx.moveTo(0,60-(dias7[0]/maxS)*52);
  dias7.forEach((v,i)=>{if(i>0)sx.lineTo(i*step,60-(v/maxS)*52)});
  sx.lineTo(w,60);sx.lineTo(0,60);sx.fillStyle=grad;sx.fill();
  sx.beginPath();sx.moveTo(0,60-(dias7[0]/maxS)*52);
  dias7.forEach((v,i)=>{if(i>0)sx.lineTo(i*step,60-(v/maxS)*52)});
  sx.strokeStyle='#3b9eff';sx.lineWidth=2;sx.stroke();
  document.getElementById('spark-labels').innerHTML=labels7.map(l=>`<span>${l}</span>`).join('');
}

// RELATÓRIO TXT
document.getElementById('btn-rel').onclick=()=>{
  if(!allU.length){toast('Sem dados','warn');return}
  const now=new Date().toLocaleString('pt-BR');
  const atv=allU.filter(u=>u.ativo&&!isExp(u.expira)).length;
  let t=`LUCS TECH — RELATÓRIO\nGerado: ${now}\n${'═'.repeat(55)}\n\nRESUMO\n  Total     : ${allU.length}\n  Ativos    : ${atv}\n  Bloqueados: ${allU.filter(u=>!u.ativo).length}\n  Vencidos  : ${allU.filter(u=>isExp(u.expira)).length}\n\n${'═'.repeat(55)}\n\n`;
  allU.forEach((u,i)=>{
    t+=`${String(i+1).padStart(3,'0')}. ${u.nome} [${(u.plano||'basic').toUpperCase()}]\n`;
    if(u.empresa)t+=`     Empresa   : ${u.empresa}\n`;
    if(u.email)t+=`     E-mail    : ${u.email}\n`;
    t+=`     Chave     : ${u.chave}\n     Status    : ${u.ativo?'ATIVO':'BLOQUEADO'}\n     Vencimento: ${u.expira?fDate(u.expira):'Sem limite'}\n     Últ.acesso: ${u.ultimo_acesso?fDT(u.ultimo_acesso):'Nunca'}\n`;
    if(u.obs)t+=`     Obs       : ${u.obs}\n`;
    t+='\n';
  });
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{type:'text/plain;charset=utf-8'}));
  a.download=`lucs-${Date.now()}.txt`;a.click();
  toast('Relatório exportado','ok');
};

// EXPORTAR LOGS CSV
document.getElementById('btn-exp-logs').onclick=()=>{
  if(!allLogs.length){toast('Sem logs','warn');return}
  let t='DATA/HORA;ACAO;NOME;EMPRESA;CHAVE;IP;SUCESSO\n';
  allLogs.forEach(l=>{t+=`${l.momento||''};${l.acao||''};${l.nome||''};${l.empresa||''};${l.chave||''};${l.ip||''};${l.sucesso?'SIM':'NAO'}\n`});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{type:'text/csv;charset=utf-8'}));
  a.download=`lucs-logs-${Date.now()}.csv`;a.click();
  toast('Logs exportados','ok');
};

document.getElementById('btn-limpar').onclick=async()=>{
  if(!confirm('Limpar todos os logs de login?'))return;
  try{await fetch('/admin/limpar-logs',{method:'POST'});toast('Logs limpos','info');load()}
  catch{toast('Erro','err')}
};

load();
setInterval(load,20000);
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
#  API — VALIDAR (usado pelo seu software cliente)
# ══════════════════════════════════════════
@app.route("/api/validar", methods=["POST"])
def validar():
    try:
        dados = request.json or {}
        chave = dados.get("chave", "").strip()
        ip    = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()

        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome, empresa, ativo, expira, plano FROM usuarios WHERE chave=%s", (chave,))
        u = cur.fetchone()

        sucesso = 0
        nome = empresa = plano = ""

        if u:
            nome    = u['nome']
            empresa = u['empresa'] or ''
            plano   = u['plano'] or 'basic'
            exp     = u['expira']
            if isinstance(exp, str):
                try: exp = date.fromisoformat(exp)
                except: exp = None
            vencido = exp and exp < datetime.now().date()
            ativo   = int(u['ativo']) if u['ativo'] is not None else 0
            if ativo == 1 and not vencido:
                sucesso = 1
                cur.execute(
                    "UPDATE usuarios SET ultimo_acesso=%s, ip_ultimo=%s WHERE chave=%s",
                    (datetime.now(), ip, chave)
                )

        cur.execute(
            "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento,ip) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (nome or None, empresa or None, chave, 'login', sucesso, datetime.now(), ip)
        )
        conn.commit(); cur.close(); conn.close()

        if sucesso:
            return jsonify({"ok": True, "nome": nome, "empresa": empresa, "plano": plano})
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
        cur.execute("""
            SELECT nome,email,empresa,chave,ativo,expira,plano,obs,ultimo_acesso,ip_ultimo
            FROM usuarios ORDER BY id DESC
        """)
        usuarios = []
        for r in cur.fetchall():
            d = row_to_dict(r)
            raw = r['ativo']
            if raw is None: d['ativo'] = False
            elif isinstance(raw, bool): d['ativo'] = raw
            else: d['ativo'] = int(raw) == 1
            usuarios.append(d)

        cur.execute("SELECT nome,empresa,chave,acao,sucesso,momento,ip FROM logs ORDER BY id DESC LIMIT 150")
        logs = [row_to_dict(r) for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*) AS n FROM logs WHERE momento::date=CURRENT_DATE AND acao='login' AND sucesso=1")
        hoje = cur.fetchone()['n']

        cur.execute("SELECT COUNT(*) AS n FROM logs WHERE momento::date=CURRENT_DATE AND acao='login' AND sucesso=0")
        negados = cur.fetchone()['n']

        cur.close(); conn.close()
        return jsonify({"usuarios": usuarios, "logs": logs, "logs_hoje": hoje, "negados_hoje": negados})

    except Exception as e:
        print(f"[admin_dados] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — CRIAR
# ══════════════════════════════════════════
@app.route("/admin/criar", methods=["POST"])
def admin_criar():
    try:
        d         = request.json or {}
        nome      = d.get('nome','').strip()
        empresa   = (d.get('empresa') or '').strip() or None
        email     = (d.get('email')   or '').strip() or None
        plano     = d.get('plano', 'basic')
        dias      = int(d.get('dias') or 30)
        ilimitado = d.get('ilimitado', False)
        obs       = (d.get('obs') or '').strip() or None

        if not nome:
            return jsonify({"ok": False, "msg": "Nome obrigatório"}), 400

        exp   = None if ilimitado else (datetime.now().date() + timedelta(days=dias))
        chave = nova_chave()

        conn = get_db(); cur = conn.cursor()
        chave_final = None
        for _ in range(10):
            try:
                cur.execute(
                    "INSERT INTO usuarios (nome,empresa,email,chave,expira,ativo,plano,obs,criado_em) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING chave",
                    (nome, empresa, email, chave, exp, 1, plano, obs, datetime.now())
                )
                chave_final = cur.fetchone()['chave']
                conn.commit(); break
            except psycopg2.errors.UniqueViolation:
                conn.rollback(); chave = nova_chave()

        if not chave_final:
            cur.close(); conn.close()
            return jsonify({"ok": False, "msg": "Não foi possível gerar chave única"}), 500

        cur.execute(
            "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento,detalhe) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (nome, empresa, chave_final, 'criacao', 1, datetime.now(), f"plano={plano}")
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True, "chave": chave_final})

    except Exception as e:
        print(f"[admin_criar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — EDITAR (nome, email, empresa, plano, obs, renovação)
# ══════════════════════════════════════════
@app.route("/admin/editar", methods=["POST"])
def admin_editar():
    try:
        d    = request.json or {}
        chave        = d.get('chave','')
        nome         = d.get('nome','').strip()
        email        = (d.get('email') or '').strip() or None
        empresa      = (d.get('empresa') or '').strip() or None
        plano        = d.get('plano','basic')
        obs          = (d.get('obs') or '').strip() or None
        renovar_dias = int(d.get('renovar_dias', 0))

        if not nome:
            return jsonify({"ok": False, "msg": "Nome obrigatório"}), 400

        conn = get_db(); cur = conn.cursor()

        if renovar_dias == -1:
            cur.execute(
                "UPDATE usuarios SET nome=%s,email=%s,empresa=%s,plano=%s,obs=%s,expira=NULL WHERE chave=%s",
                (nome, email, empresa, plano, obs, chave)
            )
        elif renovar_dias > 0:
            cur.execute("SELECT expira FROM usuarios WHERE chave=%s", (chave,))
            row = cur.fetchone()
            base = row['expira'] if row and row['expira'] else datetime.now().date()
            if isinstance(base, str): base = date.fromisoformat(base)
            nova_exp = max(base, datetime.now().date()) + timedelta(days=renovar_dias)
            cur.execute(
                "UPDATE usuarios SET nome=%s,email=%s,empresa=%s,plano=%s,obs=%s,expira=%s WHERE chave=%s",
                (nome, email, empresa, plano, obs, nova_exp, chave)
            )
        else:
            cur.execute(
                "UPDATE usuarios SET nome=%s,email=%s,empresa=%s,plano=%s,obs=%s WHERE chave=%s",
                (nome, email, empresa, plano, obs, chave)
            )

        conn.commit()
        cur.execute(
            "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (nome, empresa, chave, 'edicao', 1, datetime.now())
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})

    except Exception as e:
        print(f"[admin_editar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — TOGGLE
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

        raw   = row['ativo']
        atual = 1 if (raw is True or (not isinstance(raw, bool) and int(raw or 0)==1)) else 0
        novo  = 0 if atual==1 else 1

        cur.execute("UPDATE usuarios SET ativo=%s WHERE chave=%s", (novo, chave))
        conn.commit()
        cur.execute(
            "INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (row['nome'], row['empresa'], chave, 'ativacao' if novo==1 else 'bloqueio', 1, datetime.now())
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
        row = cur.fetchone()
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
#  API — RENOVAR VENCIDOS (em lote)
# ══════════════════════════════════════════
@app.route("/admin/renovar-vencidos", methods=["POST"])
def renovar_vencidos():
    try:
        dias     = int((request.json or {}).get('dias', 30))
        hoje     = datetime.now().date()
        nova_exp = hoje + timedelta(days=dias)
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET expira=%s WHERE expira < %s", (nova_exp, hoje))
        cur.execute(
            "INSERT INTO logs (nome,chave,acao,sucesso,momento,detalhe) VALUES (%s,%s,%s,%s,%s,%s)",
            ('SISTEMA','TODOS','renovacao',1,datetime.now(),f"+{dias} dias")
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[renovar_vencidos] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — EXPORTAR CSV
# ══════════════════════════════════════════
@app.route("/admin/exportar-csv")
def exportar_csv():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            SELECT nome,empresa,email,chave,ativo,expira,plano,obs,criado_em,ultimo_acesso,ip_ultimo
            FROM usuarios ORDER BY id DESC
        """)
        rows = cur.fetchall(); cur.close(); conn.close()
        si = io.StringIO()
        w  = csv.writer(si, delimiter=';')
        w.writerow(['Nome','Empresa','E-mail','Chave','Ativo','Plano','Vencimento','Obs','Criado em','Último acesso','IP último'])
        for r in rows:
            raw_at = r['ativo']
            ativo_str = 'Sim' if (int(raw_at)==1 if raw_at is not None else False) else 'Não'
            w.writerow([
                r['nome'] or '', r['empresa'] or '', r['email'] or '', r['chave'] or '',
                ativo_str, r['plano'] or 'basic',
                r['expira'].isoformat() if r['expira'] else '',
                r['obs'] or '',
                r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else '',
                r['ultimo_acesso'].strftime('%d/%m/%Y %H:%M') if r['ultimo_acesso'] else '',
                r['ip_ultimo'] or '',
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

# ══════════════════════════════════════════
#  HEALTH CHECK  →  GET /health
# ══════════════════════════════════════════
@app.route("/health")
def health():
    try:
        conn = get_db(); conn.close()
        return jsonify({"ok": True, "db": "supabase", "ts": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
