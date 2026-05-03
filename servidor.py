from flask import Flask, request, jsonify, render_template_string, send_file, redirect, make_response
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
import os, random, string, csv, io

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
ADMIN_TOKEN  = os.environ.get("ADMIN_TOKEN", "lucs2025")

def get_db():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL nao configurada. Adicione a variavel de ambiente no Render.")
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
        try:
            cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name='usuarios' AND column_name='ativo'")
            r = cur.fetchone()
            if r and r['data_type'] == 'boolean':
                cur.execute("ALTER TABLE usuarios ALTER COLUMN ativo TYPE INTEGER USING ativo::integer")
                conn.commit()
        except Exception as e:
            conn.rollback(); print(f"[DB] aviso: {e}")
        cur.close(); conn.close()
        print("[DB] Conectado e pronto!")
    except Exception as e:
        print(f"[DB] ERRO init: {e}")

with app.app_context():
    init_db()

HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lucs Tech &mdash; Licencas</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --black:#080a0f;
  --black2:#0f1117;
  --black3:#161b24;
  --black4:#1e2533;
  --red:#dc2626;
  --red2:#ef4444;
  --red3:#fca5a5;
  --red-glow:rgba(220,38,38,.18);
  --blue:#38bdf8;
  --blue2:#7dd3fc;
  --blue-glow:rgba(56,189,248,.12);
  --white:#f1f5f9;
  --white2:#cbd5e1;
  --white3:#94a3b8;
  --white4:#475569;
  --green:#22c55e;
  --amber:#f59e0b;
  --violet:#a78bfa;
  --r:12px;
  --r2:7px;
}
html{scroll-behavior:smooth}
body{font-family:'Space Grotesk',sans-serif;background:var(--black);color:var(--white);min-height:100vh;overflow-x:hidden}
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 1000px 600px at 75% -80px,rgba(220,38,38,.06),transparent),
    radial-gradient(ellipse 700px 700px at -5% 85%,rgba(56,189,248,.04),transparent),
    radial-gradient(ellipse 500px 300px at 50% 110%,rgba(167,139,250,.03),transparent);
}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:var(--black2)}
::-webkit-scrollbar-thumb{background:var(--black4);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--white4)}
.page{max-width:1440px;margin:0 auto;padding:22px 18px;position:relative;z-index:1}

/* TOPBAR */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  background:rgba(15,17,23,.85);
  border:1px solid rgba(255,255,255,.055);
  border-radius:var(--r);padding:13px 20px;margin-bottom:20px;
  position:sticky;top:0;z-index:50;backdrop-filter:blur(16px);
  box-shadow:0 4px 24px rgba(0,0,0,.3);
}
.brand{display:flex;align-items:center;gap:13px}
.brand-logo{
  width:38px;height:38px;border-radius:10px;
  background:linear-gradient(145deg,var(--red) 0%,#991b1b 100%);
  display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;
  box-shadow:0 0 20px var(--red-glow),0 2px 10px rgba(0,0,0,.5);
}
.brand-name{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:500;letter-spacing:3.5px;color:var(--white)}
.brand-tag{font-size:10px;color:var(--white4);letter-spacing:1.5px;margin-top:2px}
.topbar-right{display:flex;align-items:center;gap:12px}
.status-badge{
  display:flex;align-items:center;gap:8px;
  font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1px;color:var(--white4);
  background:var(--black3);border:1px solid rgba(255,255,255,.055);
  border-radius:20px;padding:6px 13px;
}
.sdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.sdot.ok{background:var(--green);animation:pulseG 2s infinite}
.sdot.err{background:var(--red2);animation:pulseR 1.5s infinite}
.sdot.warn{background:var(--amber)}
.nav-btns{display:flex;gap:4px}
.nav-btn{
  padding:6px 14px;border-radius:var(--r2);cursor:pointer;
  font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;
  color:var(--white4);border:1px solid rgba(255,255,255,.07);background:transparent;transition:all .15s;
  text-decoration:none;display:inline-block;
}
.nav-btn.on,.nav-btn:hover{background:var(--red);border-color:var(--red);color:#fff;box-shadow:0 0 14px var(--red-glow)}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:20px}
.kpi{
  background:var(--black2);border:1px solid rgba(255,255,255,.055);
  border-radius:var(--r);padding:18px 16px;
  position:relative;overflow:hidden;
  animation:slideUp .4s ease both;
  transition:border-color .2s,box-shadow .2s;
}
.kpi:hover{border-color:rgba(255,255,255,.1);box-shadow:0 6px 28px rgba(0,0,0,.35)}
.kpi::after{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.kpi:nth-child(1)::after{background:var(--blue)}
.kpi:nth-child(2)::after{background:var(--green)}
.kpi:nth-child(3)::after{background:var(--red)}
.kpi:nth-child(4)::after{background:var(--amber)}
.kpi:nth-child(5)::after{background:var(--violet)}
.kpi:nth-child(6)::after{background:#fb7185}
.kpi-icon{position:absolute;top:13px;right:13px;font-size:15px;opacity:.15}
.kpi-label{font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:3px;color:var(--white4);margin-bottom:10px}
.kpi-value{font-family:'JetBrains Mono',monospace;font-size:30px;font-weight:500;line-height:1;letter-spacing:-1px}
.kpi-sub{font-size:10px;color:var(--white4);margin-top:7px}
.kpi:nth-child(1) .kpi-value{color:var(--blue)}
.kpi:nth-child(2) .kpi-value{color:var(--green)}
.kpi:nth-child(3) .kpi-value{color:var(--red2)}
.kpi:nth-child(4) .kpi-value{color:var(--amber)}
.kpi:nth-child(5) .kpi-value{color:var(--violet)}
.kpi:nth-child(6) .kpi-value{color:#fb7185}

/* PANEL */
.panel{
  background:var(--black2);border:1px solid rgba(255,255,255,.055);
  border-radius:var(--r);overflow:hidden;animation:slideUp .4s .12s ease both;
}
.tabs{
  display:flex;border-bottom:1px solid rgba(255,255,255,.055);
  padding:0 20px;background:var(--black3);
}
.tab-btn{
  padding:14px 20px;cursor:pointer;
  font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2.5px;color:var(--white4);
  border:none;border-bottom:2px solid transparent;margin-bottom:-1px;
  background:transparent;transition:all .15s;white-space:nowrap;
}
.tab-btn.on{color:var(--white);border-bottom-color:var(--red)}
.tab-btn:hover:not(.on){color:var(--white2)}
.tab-pane{display:none;padding:24px 20px 28px}
.tab-pane.on{display:block}

/* SECTION HEADER */
.sec-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px}
.sec-title-wrap{display:flex;align-items:center;gap:10px}
.sec-title{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:3px;color:var(--white4)}
.count-badge{
  background:var(--blue-glow);color:var(--blue);
  border:1px solid rgba(56,189,248,.2);border-radius:20px;
  padding:2px 11px;font-family:'JetBrains Mono',monospace;font-size:10px;
}
.sec-actions{display:flex;gap:7px;flex-wrap:wrap;align-items:center}

/* BUTTONS */
.btn{
  display:inline-flex;align-items:center;gap:7px;padding:8px 15px;
  border-radius:var(--r2);cursor:pointer;
  font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1.5px;
  border:none;transition:all .15s;white-space:nowrap;font-weight:500;
}
.btn-primary{background:var(--red);color:#fff;box-shadow:0 2px 14px var(--red-glow)}
.btn-primary:hover{background:var(--red2);box-shadow:0 4px 22px rgba(220,38,38,.35);transform:translateY(-1px)}
.btn-primary:active{transform:translateY(0)}
.btn-outline{background:transparent;color:var(--white3);border:1px solid rgba(255,255,255,.1)}
.btn-outline:hover{background:var(--black3);border-color:rgba(255,255,255,.18);color:var(--white)}
.btn-blue{background:var(--blue-glow);color:var(--blue);border:1px solid rgba(56,189,248,.2)}
.btn-blue:hover{background:rgba(56,189,248,.18)}
.btn-green{background:rgba(34,197,94,.07);color:var(--green);border:1px solid rgba(34,197,94,.18)}
.btn-green:hover{background:rgba(34,197,94,.14)}
.btn-danger{background:rgba(220,38,38,.07);color:var(--red2);border:1px solid rgba(220,38,38,.18)}
.btn-danger:hover{background:rgba(220,38,38,.14)}
.btn-sm{padding:6px 11px;font-size:8px}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none!important}

/* TOOLBAR */
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
.search-wrap{position:relative;flex:1;min-width:200px}
.search-wrap svg{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--white4);pointer-events:none}
.search-wrap input{padding-left:36px}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.fchip{
  padding:5px 13px;border-radius:20px;cursor:pointer;
  font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;
  border:1px solid rgba(255,255,255,.07);color:var(--white4);background:transparent;transition:all .15s;
}
.fchip.on{background:var(--blue-glow);border-color:rgba(56,189,248,.25);color:var(--blue)}
.fchip:hover:not(.on){border-color:rgba(255,255,255,.14);color:var(--white2)}

/* INPUTS */
input,select,textarea{
  background:var(--black3);border:1px solid rgba(255,255,255,.08);
  padding:10px 13px;border-radius:var(--r2);
  color:var(--white);font-family:'Space Grotesk',sans-serif;font-size:13px;
  outline:none;transition:border-color .15s,box-shadow .15s;width:100%;
}
textarea{resize:vertical;min-height:72px}
input::placeholder,textarea::placeholder{color:var(--white4)}
input:focus,select:focus,textarea:focus{border-color:rgba(220,38,38,.5);box-shadow:0 0 0 3px rgba(220,38,38,.07)}
select option{background:var(--black3)}
.f-label{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--white4);display:block;margin-bottom:5px}
.f-group{display:flex;flex-direction:column}
.f-grid{display:grid;grid-template-columns:1.3fr 1fr 1fr 110px 85px 95px auto;gap:10px;align-items:end}
.f-grid2{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:13px}

/* TABLE */
.tw{overflow-x:auto;border-radius:var(--r2);border:1px solid rgba(255,255,255,.055)}
table{width:100%;border-collapse:collapse}
thead{background:var(--black3)}
th{
  font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:2.5px;color:var(--white4);
  padding:11px 14px;border-bottom:1px solid rgba(255,255,255,.055);
  text-align:left;white-space:nowrap;cursor:pointer;user-select:none;
}
th:hover{color:var(--white2)}
th .si::after{content:'⇅';margin-left:4px;font-size:8px;opacity:.22}
th.asc .si::after{content:'▲';opacity:1;color:var(--blue)}
th.desc .si::after{content:'▼';opacity:1;color:var(--blue)}
td{padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.025);vertical-align:middle;font-size:13px}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .1s}
tbody tr:hover td{background:rgba(255,255,255,.018)}
.cn b{font-weight:600}
.cn small{font-size:11px;color:var(--white4);display:block;margin-top:2px}
.etag{
  display:inline-flex;align-items:center;
  background:var(--blue-glow);color:var(--blue2);
  border:1px solid rgba(56,189,248,.15);border-radius:var(--r2);
  padding:3px 9px;font-size:11px;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.pbadge{display:inline-block;border-radius:var(--r2);padding:3px 9px;font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px}
.pb-basic{background:rgba(148,163,184,.08);color:var(--white3);border:1px solid rgba(148,163,184,.14)}
.pb-pro{background:var(--blue-glow);color:var(--blue);border:1px solid rgba(56,189,248,.18)}
.pb-enterprise{background:rgba(167,139,250,.08);color:var(--violet);border:1px solid rgba(167,139,250,.18)}
.kchip{
  display:inline-flex;align-items:center;gap:6px;
  background:rgba(245,158,11,.06);color:var(--amber);
  border:1px solid rgba(245,158,11,.14);border-radius:var(--r2);
  padding:4px 10px;cursor:pointer;font-family:'JetBrains Mono',monospace;font-size:10px;
  transition:background .15s,transform .1s;
}
.kchip:hover{background:rgba(245,158,11,.12)}.kchip:active{transform:scale(.97)}
.ex{font-size:12px}
.ex.exp{color:var(--red2)}.ex.warn{color:var(--amber)}.ex.ok{color:var(--white3)}.ex.none{color:var(--white4)}
.spill{
  display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:20px;cursor:pointer;
  font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;border:none;transition:all .15s;
}
.spill.on{background:rgba(34,197,94,.08);color:var(--green);border:1px solid rgba(34,197,94,.18)}
.spill.off{background:rgba(220,38,38,.07);color:var(--red2);border:1px solid rgba(220,38,38,.15)}
.spill.on:hover{background:rgba(34,197,94,.15);transform:scale(1.04)}
.spill.off:hover{background:rgba(220,38,38,.13);transform:scale(1.04)}
.pdot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.pdot.on{background:var(--green);animation:pulseG 2s infinite}.pdot.off{background:var(--red2)}
.last{font-size:11px;color:var(--white4)}.last.fresh{color:var(--green)}
.row-acts{display:flex;gap:4px}
.ibtn{background:none;border:none;color:var(--white4);cursor:pointer;padding:5px 7px;border-radius:var(--r2);transition:color .15s,background .15s}
.ibtn.edit:hover{color:var(--blue);background:rgba(56,189,248,.08)}
.ibtn.del:hover{color:var(--red2);background:rgba(220,38,38,.08)}
.empty{text-align:center;padding:52px;color:var(--white4);font-size:13px}
.ei{font-size:26px;opacity:.2;display:block;margin-bottom:10px}

/* MODAL */
.overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:200;
  display:flex;align-items:center;justify-content:center;
  opacity:0;pointer-events:none;transition:opacity .2s;backdrop-filter:blur(8px);
}
.overlay.open{opacity:1;pointer-events:all}
.modal{
  background:var(--black2);border:1px solid rgba(255,255,255,.09);
  border-radius:16px;padding:28px;width:100%;max-width:540px;max-height:92vh;overflow-y:auto;
  transform:translateY(18px) scale(.97);transition:transform .25s cubic-bezier(.34,1.4,.64,1);
  box-shadow:0 28px 80px rgba(0,0,0,.65);
}
.overlay.open .modal{transform:none}
.modal-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}
.modal-title{
  display:flex;align-items:center;gap:11px;
  font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:3px;color:var(--white3);
}
.modal-icon{
  width:30px;height:30px;background:var(--red-glow);border:1px solid rgba(220,38,38,.25);
  border-radius:8px;display:flex;align-items:center;justify-content:center;
}
.modal-close{background:none;border:none;color:var(--white4);cursor:pointer;font-size:18px;padding:4px 8px;border-radius:var(--r2);transition:all .15s}
.modal-close:hover{color:var(--red2);background:rgba(220,38,38,.08)}
.mgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.mgrid.full{grid-template-columns:1fr}
.ropts{display:flex;gap:7px;flex-wrap:wrap;margin-top:7px}
.ropt{
  padding:6px 15px;border-radius:8px;cursor:pointer;
  font-family:'JetBrains Mono',monospace;font-size:10px;
  border:1px solid rgba(255,255,255,.07);color:var(--white4);background:transparent;transition:all .15s;
}
.ropt.on{background:rgba(34,197,94,.1);border-color:rgba(34,197,94,.3);color:var(--green)}
.ropt:hover:not(.on){border-color:rgba(255,255,255,.14);color:var(--white2)}
.modal-footer{display:flex;gap:10px;justify-content:flex-end;margin-top:22px}

/* STATS */
.sg{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.sc{background:var(--black3);border:1px solid rgba(255,255,255,.055);border-radius:var(--r);padding:18px}
.sc-title{font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:3px;color:var(--white4);margin-bottom:14px}
.br{display:flex;align-items:center;gap:10px;margin-bottom:9px;font-size:12px}
.bn{width:85px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--white3);flex-shrink:0}
.bt{flex:1;height:4px;background:rgba(255,255,255,.055);border-radius:2px;overflow:hidden}
.bf{height:100%;border-radius:2px;transition:width .7s ease}
.bv{width:24px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--white4);flex-shrink:0}
.drow{display:flex;align-items:center;gap:18px}
.dleg{flex:1}
.dlr{display:flex;align-items:center;gap:8px;margin-bottom:9px;font-size:12px;color:var(--white3)}
.dld{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dlv{margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:11px}

/* LOGS */
.lb{
  background:var(--black3);border:1px solid rgba(255,255,255,.055);
  border-radius:var(--r);padding:14px;max-height:260px;overflow-y:auto;
  font-family:'JetBrains Mono',monospace;font-size:10px;line-height:2.1;
}
.lr{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.lts{color:var(--white4);font-size:9px;flex-shrink:0}
.lok{color:var(--green)}.lfail{color:var(--red2)}.linf{color:var(--amber)}.lsys{color:var(--blue)}
.lip{font-size:9px;color:var(--white4);margin-left:auto}

/* TOAST */
.toast{
  position:fixed;bottom:24px;right:24px;z-index:999;
  background:var(--black3);border:1px solid rgba(255,255,255,.1);
  padding:12px 18px;border-radius:11px;
  font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--white);
  display:flex;align-items:center;gap:10px;
  box-shadow:0 14px 44px rgba(0,0,0,.6);
  opacity:0;transform:translateY(12px) scale(.97);
  transition:all .22s cubic-bezier(.34,1.3,.64,1);pointer-events:none;max-width:320px;
}
.toast.show{opacity:1;transform:none}
.tdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.tok{background:var(--green)}.terr{background:var(--red2)}.twarn{background:var(--amber)}.tinf{background:var(--blue)}

/* KEY PREVIEW */
.kprev{background:var(--black3);border:1px solid rgba(255,255,255,.055);border-radius:var(--r);padding:16px}
.kprev-label{font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:3px;color:var(--white4);margin-bottom:10px}
.kprev-val{font-family:'JetBrains Mono',monospace;font-size:14px;color:var(--white4)}
.kprev-val.ready{color:var(--amber)}
.kprev-info{font-size:11px;color:var(--white4);margin-top:8px}

/* ANIMATIONS */
@keyframes slideUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes pulseG{0%{box-shadow:0 0 0 0 rgba(34,197,94,.5)}70%{box-shadow:0 0 0 6px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
@keyframes pulseR{0%{box-shadow:0 0 0 0 rgba(220,38,38,.5)}70%{box-shadow:0 0 0 6px rgba(220,38,38,0)}100%{box-shadow:0 0 0 0 rgba(220,38,38,0)}}

/* RESPONSIVE */
@media(max-width:1200px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.f-grid{grid-template-columns:1fr 1fr}.sg{grid-template-columns:1fr}}
@media(max-width:580px){.kpis{grid-template-columns:1fr 1fr}.mgrid{grid-template-columns:1fr}}
</style>
</head>
<body data-modo="app">
<div class="page">

  <div class="topbar">
    <div class="brand">
      <div class="brand-logo">&#9889;</div>
      <div>
        <div class="brand-name">LUCS TECH</div>
        <div class="brand-tag">GERENCIADOR DE LICENCAS v2</div>
      </div>
    </div>
    <div class="topbar-right">
      <div class="status-badge">
        <div class="sdot warn" id="hdot"></div>
        <span id="hstatus">CONECTANDO...</span>
      </div>
      <div class="nav-btns">
        <a href="/app" class="nav-btn" id="nav-app">APP</a>
        <a href="/dm"  class="nav-btn" id="nav-dm">DM</a>
      </div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><span class="kpi-icon">&#128101;</span><div class="kpi-label">TOTAL</div><div class="kpi-value" id="k-total">&#8212;</div><div class="kpi-sub">clientes</div></div>
    <div class="kpi"><span class="kpi-icon">&#9989;</span><div class="kpi-label">ATIVOS</div><div class="kpi-value" id="k-ativos">&#8212;</div><div class="kpi-sub" id="k-ativos-pct">&#8212;</div></div>
    <div class="kpi"><span class="kpi-icon">&#128274;</span><div class="kpi-label">BLOQUEADOS</div><div class="kpi-value" id="k-bloq">&#8212;</div><div class="kpi-sub" id="k-bloq-pct">&#8212;</div></div>
    <div class="kpi"><span class="kpi-icon">&#9888;</span><div class="kpi-label">VENCIDOS</div><div class="kpi-value" id="k-venc">&#8212;</div><div class="kpi-sub">expirados</div></div>
    <div class="kpi"><span class="kpi-icon">&#128273;</span><div class="kpi-label">LOGINS HOJE</div><div class="kpi-value" id="k-hoje">&#8212;</div><div class="kpi-sub">autenticacoes</div></div>
    <div class="kpi"><span class="kpi-icon">&#128683;</span><div class="kpi-label">NEGADOS HOJE</div><div class="kpi-value" id="k-neg">&#8212;</div><div class="kpi-sub">bloqueados</div></div>
  </div>

  <div class="panel">
    <div class="tabs">
      <button class="tab-btn on" data-tab="licencas">LICENCAS</button>
      <button class="tab-btn" data-tab="nova">NOVA LICENCA</button>
      <button class="tab-btn" data-tab="stats">ESTATISTICAS</button>
      <button class="tab-btn" data-tab="logs">ATIVIDADE</button>
    </div>

    <div class="tab-pane on" id="tab-licencas">
      <div class="sec-hd">
        <div class="sec-title-wrap">
          <div class="sec-title">LICENCAS CADASTRADAS</div>
          <span class="count-badge" id="badge-n">0</span>
        </div>
        <div class="sec-actions">
          <a href="/admin/exportar-csv" class="btn btn-blue btn-sm" download>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>CSV
          </a>
          <button class="btn btn-outline btn-sm" id="btn-rel">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>TXT
          </button>
          <button class="btn btn-green btn-sm" id="btn-renovar-venc">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>RENOVAR VENCIDOS
          </button>
          <button class="btn btn-danger btn-sm" id="btn-bloqtodos">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>BLOQUEAR TODOS
          </button>
        </div>
      </div>
      <div class="toolbar">
        <div class="search-wrap">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input id="inp-q" type="text" placeholder="Buscar nome, empresa, chave, e-mail, plano..."/>
        </div>
        <div class="filters">
          <button class="fchip on" data-f="todos">TODOS</button>
          <button class="fchip" data-f="ativo">ATIVOS</button>
          <button class="fchip" data-f="bloqueado">BLOQUEADOS</button>
          <button class="fchip" data-f="vencido">VENCIDOS</button>
          <button class="fchip" data-f="vence7">VENCE EM 7D</button>
        </div>
      </div>
      <div class="tw">
        <table>
          <thead><tr>
            <th data-col="nome">CLIENTE<span class="si"></span></th>
            <th data-col="empresa">EMPRESA<span class="si"></span></th>
            <th>PLANO</th>
            <th data-col="chave">CHAVE<span class="si"></span></th>
            <th data-col="expira">VENCIMENTO<span class="si"></span></th>
            <th data-col="ultimo_acesso">ULTIMO ACESSO<span class="si"></span></th>
            <th>STATUS</th>
            <th></th>
          </tr></thead>
          <tbody id="tbody">
            <tr><td colspan="8" class="empty"><span class="ei">&#8987;</span>Carregando dados...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="tab-pane" id="tab-nova">
      <div class="sec-hd"><div class="sec-title">CRIAR NOVA LICENCA</div></div>
      <div class="f-grid">
        <div class="f-group"><label class="f-label">NOME *</label><input id="i-nome" type="text" placeholder="Nome completo do cliente"/></div>
        <div class="f-group"><label class="f-label">EMPRESA</label><input id="i-empresa" type="text" placeholder="Empresa (opcional)"/></div>
        <div class="f-group"><label class="f-label">E-MAIL</label><input id="i-email" type="email" placeholder="email@dominio.com"/></div>
        <div class="f-group"><label class="f-label">PLANO</label>
          <select id="i-plano"><option value="basic">BASIC</option><option value="pro">PRO</option><option value="enterprise">ENTERPRISE</option></select>
        </div>
        <div class="f-group"><label class="f-label">DIAS</label><input id="i-dias" type="number" value="30" min="1" max="3650"/></div>
        <div class="f-group"><label class="f-label">ILIMITADO</label>
          <select id="i-ilimitado"><option value="0">NAO</option><option value="1">SIM</option></select>
        </div>
        <button class="btn btn-primary" id="btn-criar" style="align-self:end">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>GERAR
        </button>
      </div>
      <div class="f-grid2">
        <div class="f-group"><label class="f-label">OBSERVACOES</label><textarea id="i-obs" placeholder="Notas internas sobre este cliente..."></textarea></div>
        <div class="kprev">
          <div class="kprev-label">CHAVE GERADA</div>
          <div class="kprev-val" id="preview-chave">&#8212; aguardando &#8212;</div>
          <div class="kprev-info" id="preview-info"></div>
        </div>
      </div>
    </div>

    <div class="tab-pane" id="tab-stats">
      <div class="sg">
        <div class="sc"><div class="sc-title">TOP EMPRESAS</div><div id="st-empresas"></div></div>
        <div class="sc">
          <div class="sc-title">DISTRIBUICAO POR PLANO</div>
          <div class="drow"><canvas id="donut-canvas" width="90" height="90"></canvas><div class="dleg" id="donut-leg"></div></div>
        </div>
        <div class="sc">
          <div class="sc-title">LOGINS &mdash; ULTIMOS 7 DIAS</div>
          <canvas id="spark-canvas" style="width:100%;height:64px;display:block"></canvas>
          <div id="spark-labels" style="display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--white4);margin-top:5px"></div>
        </div>
      </div>
    </div>

    <div class="tab-pane" id="tab-logs">
      <div class="sec-hd">
        <div class="sec-title">ATIVIDADE RECENTE</div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-outline btn-sm" id="btn-exp-logs">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>EXPORTAR
          </button>
          <button class="btn btn-danger btn-sm" id="btn-limpar">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>LIMPAR
          </button>
        </div>
      </div>
      <div class="lb" id="logs">Carregando...</div>
    </div>
  </div>
</div>

<div class="overlay" id="modal-overlay">
  <div class="modal">
    <div class="modal-hd">
      <div class="modal-title">
        <div class="modal-icon">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--red2)" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </div>
        EDITAR LICENCA
      </div>
      <button class="modal-close" id="modal-close">&#10005;</button>
    </div>
    <div class="mgrid">
      <div class="f-group"><label class="f-label">NOME</label><input id="m-nome" type="text"/></div>
      <div class="f-group"><label class="f-label">E-MAIL</label><input id="m-email" type="email"/></div>
      <div class="f-group"><label class="f-label">EMPRESA</label><input id="m-empresa" type="text"/></div>
      <div class="f-group"><label class="f-label">PLANO</label>
        <select id="m-plano"><option value="basic">BASIC</option><option value="pro">PRO</option><option value="enterprise">ENTERPRISE</option></select>
      </div>
    </div>
    <div class="f-group mgrid full" style="margin-bottom:16px">
      <label class="f-label">OBSERVACOES</label><textarea id="m-obs"></textarea>
    </div>
    <div class="f-group">
      <label class="f-label">RENOVAR LICENCA</label>
      <div class="ropts">
        <button class="ropt on" data-d="0">SEM ALTERACAO</button>
        <button class="ropt" data-d="7">+7 DIAS</button>
        <button class="ropt" data-d="30">+30 DIAS</button>
        <button class="ropt" data-d="90">+90 DIAS</button>
        <button class="ropt" data-d="365">+1 ANO</button>
        <button class="ropt" data-d="-1">ILIMITADO</button>
      </div>
    </div>
    <input type="hidden" id="m-chave"/>
    <div class="modal-footer">
      <button class="btn btn-outline" id="modal-cancel">CANCELAR</button>
      <button class="btn btn-primary" id="modal-save">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v14a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
        SALVAR
      </button>
    </div>
  </div>
</div>

<div class="toast" id="toast">
  <div class="tdot tok" id="tdot"></div>
  <span id="tmsg"></span>
</div>

<script>
const MODO = document.body.dataset.modo || 'app';
const navEl = document.getElementById('nav-' + MODO);
if (navEl) navEl.classList.add('on');

let allU=[], allLogs=[], filtro='todos', busca='', sortCol='', sortDir=1, editDias=0;

let _tt;
function toast(msg, tipo='ok') {
  document.getElementById('tdot').className = 'tdot t' + tipo;
  document.getElementById('tmsg').textContent = msg;
  const el = document.getElementById('toast');
  el.classList.add('show'); clearTimeout(_tt);
  _tt = setTimeout(() => el.classList.remove('show'), 3000);
}

function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fDate(s){return s?new Date(s+'T00:00:00').toLocaleDateString('pt-BR'):''}
function fDT(s){return s?new Date(s).toLocaleString('pt-BR'):null}
function ago(s){
  if(!s)return null;
  const h=(Date.now()-new Date(s).getTime())/3600000;
  if(h<1)return'Agora ha pouco';
  if(h<24)return Math.floor(h)+'h atras';
  if(h<48)return'Ontem';
  return fDT(s);
}
function exSt(s){
  if(!s)return'none';
  const dd=(new Date(s+'T00:00:00')-new Date(new Date().toDateString()))/86400000;
  return dd<0?'exp':dd<=7?'warn':'ok';
}
function isExp(s){return s&&new Date(s+'T00:00:00')<new Date(new Date().toDateString())}
function vence7(s){
  if(!s)return false;
  const dd=(new Date(s+'T00:00:00')-new Date(new Date().toDateString()))/86400000;
  return dd>=0&&dd<=7;
}
function planoCls(p){return p==='pro'?'pb-pro':p==='enterprise'?'pb-enterprise':'pb-basic'}

document.querySelectorAll('.tab-btn').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('.tab-btn').forEach(x=>x.classList.remove('on'));
    document.querySelectorAll('.tab-pane').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    document.getElementById('tab-'+b.dataset.tab).classList.add('on');
    if(b.dataset.tab==='stats')renderStats();
  }
});

async function load(){
  try{
    const r=await fetch('/admin/dados');
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();
    if(!d.usuarios)throw new Error('Sem dados');
    allU=d.usuarios; allLogs=d.logs||[];
    const total=allU.length;
    const ativos=allU.filter(u=>u.ativo&&!isExp(u.expira)).length;
    const bloq=allU.filter(u=>!u.ativo).length;
    const venc=allU.filter(u=>isExp(u.expira)).length;
    document.getElementById('k-total').textContent=total;
    document.getElementById('k-ativos').textContent=ativos;
    document.getElementById('k-ativos-pct').textContent=total?Math.round(ativos/total*100)+'% do total':'--';
    document.getElementById('k-bloq').textContent=bloq;
    document.getElementById('k-bloq-pct').textContent=total?Math.round(bloq/total*100)+'% do total':'--';
    document.getElementById('k-venc').textContent=venc;
    document.getElementById('k-hoje').textContent=d.logs_hoje||0;
    document.getElementById('k-neg').textContent=d.negados_hoje||0;
    document.getElementById('hdot').className='sdot ok';
    document.getElementById('hstatus').textContent='SUPABASE OK';
    renderT(); renderLogs();
  }catch(e){
    document.getElementById('hdot').className='sdot err';
    document.getElementById('hstatus').textContent='ERRO BD';
    console.error('Load error:',e);
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
  if(!list.length){tb.innerHTML='<tr><td colspan="8" class="empty"><span class="ei">&#128269;</span>Nenhum resultado.</td></tr>';return}
  const exLbl={exp:'Vencida',warn:'Vence em breve',ok:'',none:'Sem limite'};
  tb.innerHTML=list.map(u=>{
    const es=exSt(u.expira);
    const exTxt=es==='ok'?fDate(u.expira):exLbl[es];
    const a=ago(u.ultimo_acesso);
    const fresh=u.ultimo_acesso&&(Date.now()-new Date(u.ultimo_acesso).getTime())<3600000;
    const plano=u.plano||'basic';
    const ud=JSON.stringify(u).replace(/"/g,'&quot;');
    return`<tr>
      <td class="cn"><b>${esc(u.nome)}</b><small>${esc(u.email||'')}</small></td>
      <td>${u.empresa?`<span class="etag" title="${esc(u.empresa)}">${esc(u.empresa)}</span>`:'<span style="color:var(--white4)">--</span>'}</td>
      <td><span class="pbadge ${planoCls(plano)}">${plano.toUpperCase()}</span></td>
      <td><span class="kchip" data-k="${esc(u.chave)}">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="11" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>${esc(u.chave)}</span></td>
      <td><span class="ex ${es}">${exTxt||'--'}</span></td>
      <td><span class="last${fresh?' fresh':''}">${a||'<span style="color:var(--white4)">Nunca</span>'}</span></td>
      <td><button class="spill ${u.ativo?'on':'off'}" data-k="${esc(u.chave)}"><span class="pdot ${u.ativo?'on':'off'}"></span>${u.ativo?'ATIVO':'BLOQUEADO'}</button></td>
      <td><div class="row-acts">
        <button class="ibtn edit" data-ud="${ud}" title="Editar"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
        <button class="ibtn del" data-k="${esc(u.chave)}" title="Remover"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg></button>
      </div></td>
    </tr>`;
  }).join('');
  tb.querySelectorAll('.kchip').forEach(e=>e.onclick=()=>{navigator.clipboard.writeText(e.dataset.k);toast('Chave copiada!')});
  tb.querySelectorAll('.spill').forEach(e=>e.onclick=()=>tog(e.dataset.k));
  tb.querySelectorAll('.ibtn.del').forEach(e=>e.onclick=()=>rem(e.dataset.k));
  tb.querySelectorAll('.ibtn.edit').forEach(e=>e.onclick=()=>{
    try{openEdit(JSON.parse(e.dataset.ud.replace(/&quot;/g,'"')))}catch{}
  });
}

document.querySelectorAll('th[data-col]').forEach(th=>{
  th.onclick=()=>{
    const col=th.dataset.col;
    if(sortCol===col)sortDir*=-1;else{sortCol=col;sortDir=1}
    document.querySelectorAll('th[data-col]').forEach(t=>t.classList.remove('asc','desc'));
    th.classList.add(sortDir===1?'asc':'desc');
    renderT();
  }
});
document.querySelectorAll('.fchip').forEach(b=>{
  b.onclick=()=>{document.querySelectorAll('.fchip').forEach(x=>x.classList.remove('on'));b.classList.add('on');filtro=b.dataset.f;renderT()}
});
document.getElementById('inp-q').oninput=e=>{busca=e.target.value.trim();renderT()};

document.getElementById('btn-criar').onclick=async()=>{
  const nome=document.getElementById('i-nome').value.trim();
  if(!nome){toast('Informe o nome do cliente','warn');return}
  const btn=document.getElementById('btn-criar');
  btn.disabled=true;btn.textContent='...';
  try{
    const r=await fetch('/admin/criar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      nome,empresa:document.getElementById('i-empresa').value.trim(),
      email:document.getElementById('i-email').value.trim(),
      plano:document.getElementById('i-plano').value,
      dias:document.getElementById('i-dias').value,
      ilimitado:document.getElementById('i-ilimitado').value==='1',
      obs:document.getElementById('i-obs').value.trim()
    })});
    const d=await r.json();
    if(d.ok){
      const prev=document.getElementById('preview-chave');
      prev.textContent=d.chave;prev.classList.add('ready');
      document.getElementById('preview-info').textContent='Criado '+new Date().toLocaleString('pt-BR')+' · '+document.getElementById('i-plano').value.toUpperCase()+' · '+(document.getElementById('i-ilimitado').value==='1'?'Sem limite':document.getElementById('i-dias').value+' dias');
      toast('Licenca gerada: '+d.chave);
      ['i-nome','i-empresa','i-email','i-obs'].forEach(id=>document.getElementById(id).value='');
      load();
    }else toast(d.msg||'Erro ao criar','err');
  }catch{toast('Erro de conexao','err')}
  finally{btn.disabled=false;btn.innerHTML='<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>GERAR'}
};

async function tog(chave){
  try{
    const r=await fetch('/admin/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});
    const d=await r.json();
    if(d.ok){toast(d.ativo?'Ativado!':'Bloqueado!',d.ativo?'ok':'warn');load()}
    else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexao','err')}
}

async function rem(chave){
  if(!confirm('Remover este cliente permanentemente?'))return;
  try{
    const r=await fetch('/admin/deletar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});
    const d=await r.json();
    if(d.ok){toast('Removido','inf');load()}else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexao','err')}
}

document.getElementById('btn-bloqtodos').onclick=async()=>{
  const n=allU.filter(u=>u.ativo).length;
  if(!n){toast('Nenhum ativo','warn');return}
  if(!confirm('Bloquear '+n+' cliente(s) ativo(s)?'))return;
  try{await fetch('/admin/bloquear-todos',{method:'POST'});toast(n+' clientes bloqueados','warn');load()}
  catch{toast('Erro','err')}
};

document.getElementById('btn-renovar-venc').onclick=async()=>{
  const venc=allU.filter(u=>isExp(u.expira));
  if(!venc.length){toast('Nenhum vencido','warn');return}
  const dias=prompt('Renovar '+venc.length+' licenca(s) vencida(s) por quantos dias?','30');
  if(!dias||isNaN(dias))return;
  try{
    const r=await fetch('/admin/renovar-vencidos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dias:parseInt(dias)})});
    const d=await r.json();
    if(d.ok){toast(venc.length+' licencas renovadas por '+dias+' dias');load()}else toast(d.msg||'Erro','err');
  }catch{toast('Erro','err')}
};

let editChave='';
function openEdit(u){
  editChave=u.chave;editDias=0;
  document.getElementById('m-nome').value=u.nome||'';
  document.getElementById('m-email').value=u.email||'';
  document.getElementById('m-empresa').value=u.empresa||'';
  document.getElementById('m-plano').value=u.plano||'basic';
  document.getElementById('m-obs').value=u.obs||'';
  document.querySelectorAll('.ropt').forEach(b=>b.classList.remove('on'));
  document.querySelector('.ropt[data-d="0"]').classList.add('on');
  document.getElementById('modal-overlay').classList.add('open');
}
document.querySelectorAll('.ropt').forEach(b=>{
  b.onclick=()=>{document.querySelectorAll('.ropt').forEach(x=>x.classList.remove('on'));b.classList.add('on');editDias=parseInt(b.dataset.d)}
});
function closeModal(){document.getElementById('modal-overlay').classList.remove('open')}
document.getElementById('modal-close').onclick=closeModal;
document.getElementById('modal-cancel').onclick=closeModal;
document.getElementById('modal-overlay').onclick=e=>{if(e.target===e.currentTarget)closeModal()};
document.getElementById('modal-save').onclick=async()=>{
  try{
    const r=await fetch('/admin/editar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      chave:editChave,nome:document.getElementById('m-nome').value.trim(),
      email:document.getElementById('m-email').value.trim(),
      empresa:document.getElementById('m-empresa').value.trim(),
      plano:document.getElementById('m-plano').value,
      obs:document.getElementById('m-obs').value.trim(),
      renovar_dias:editDias
    })});
    const d=await r.json();
    if(d.ok){toast('Salvo!');closeModal();load()}else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexao','err')}
};

function renderLogs(){
  const lb=document.getElementById('logs');
  if(!allLogs.length){lb.innerHTML='<span style="color:var(--white4)">Sem atividade.</span>';return}
  lb.innerHTML=allLogs.map(l=>{
    let cls,icon,lbl;
    if(l.acao==='login'){cls=l.sucesso?'lok':'lfail';icon=l.sucesso?'&#10003;':'&#10007;';lbl=l.sucesso?'LOGIN':'NEGADO'}
    else if(l.acao==='bloqueio_geral'){cls='lsys';icon='&#9889;';lbl='BLOQ.GERAL'}
    else if(l.acao==='criacao'){cls='linf';icon='&#10022;';lbl='CRIACAO'}
    else if(l.acao==='edicao'){cls='linf';icon='&#9998;';lbl='EDICAO'}
    else if(l.acao==='renovacao'){cls='lok';icon='&#8635;';lbl='RENOVACAO'}
    else{cls='linf';icon='&#9670;';lbl=(l.acao||'').toUpperCase()}
    const nm=l.nome?' <b>'+esc(l.nome)+'</b>':'';
    const em=l.empresa?' <span style="color:var(--blue2)">['+esc(l.empresa)+']</span>':'';
    const ts=l.momento?new Date(l.momento).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
    const ip=l.ip?'<span class="lip">'+esc(l.ip)+'</span>':'';
    return'<div class="lr"><span class="lts">'+ts+'</span><span class="'+cls+'">'+icon+' '+lbl+'</span>'+nm+em+'<span style="color:var(--white4);font-size:9px">'+esc(l.chave||'')+'</span>'+ip+'</div>';
  }).join('');
}

function renderStats(){
  const emp={};
  allU.forEach(u=>{if(u.empresa)emp[u.empresa]=(emp[u.empresa]||0)+1});
  const topEmp=Object.entries(emp).sort((a,b)=>b[1]-a[1]).slice(0,6);
  const maxE=topEmp[0]?.[1]||1;
  const colors=['var(--blue)','var(--green)','var(--red2)','var(--violet)','var(--amber)','#fb7185'];
  document.getElementById('st-empresas').innerHTML=topEmp.length
    ?topEmp.map(([nm,n],i)=>'<div class="br"><span class="bn" title="'+esc(nm)+'">'+esc(nm)+'</span><div class="bt"><div class="bf" style="width:'+Math.round(n/maxE*100)+'%;background:'+colors[i%colors.length]+'"></div></div><span class="bv">'+n+'</span></div>').join('')
    :'<span style="color:var(--white4);font-size:12px">Sem dados</span>';

  const planos={basic:0,pro:0,enterprise:0};
  allU.forEach(u=>planos[u.plano||'basic']=(planos[u.plano||'basic']||0)+1);
  const pColors={basic:'#94a3b8',pro:'#38bdf8',enterprise:'#a78bfa'};
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
  ctx.beginPath();ctx.arc(45,45,22,0,Math.PI*2);ctx.fillStyle='#0f1117';ctx.fill();
  document.getElementById('donut-leg').innerHTML=Object.entries(planos).map(([p,n])=>'<div class="dlr"><div class="dld" style="background:'+pColors[p]+'"></div>'+p.toUpperCase()+'<span class="dlv">'+n+'</span></div>').join('');

  const dias7=[],labels7=[];
  for(let i=6;i>=0;i--){
    const d=new Date();d.setDate(d.getDate()-i);
    const iso=d.toISOString().slice(0,10);
    dias7.push(allLogs.filter(l=>l.acao==='login'&&l.sucesso&&(l.momento||'').slice(0,10)===iso).length);
    labels7.push(d.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'}));
  }
  const sc=document.getElementById('spark-canvas');
  sc.width=sc.parentElement.clientWidth||300;sc.height=64;
  const sx=sc.getContext('2d');
  const maxS=Math.max(...dias7,1),w=sc.width,step=w/(dias7.length-1);
  const grad=sx.createLinearGradient(0,0,0,64);
  grad.addColorStop(0,'rgba(220,38,38,.3)');grad.addColorStop(1,'rgba(220,38,38,0)');
  sx.beginPath();sx.moveTo(0,64-(dias7[0]/maxS)*56);
  dias7.forEach((v,i)=>{if(i>0)sx.lineTo(i*step,64-(v/maxS)*56)});
  sx.lineTo(w,64);sx.lineTo(0,64);sx.fillStyle=grad;sx.fill();
  sx.beginPath();sx.moveTo(0,64-(dias7[0]/maxS)*56);
  dias7.forEach((v,i)=>{if(i>0)sx.lineTo(i*step,64-(v/maxS)*56)});
  sx.strokeStyle='var(--red2)';sx.lineWidth=2;sx.stroke();
  document.getElementById('spark-labels').innerHTML=labels7.map(l=>'<span>'+l+'</span>').join('');
}

document.getElementById('btn-rel').onclick=()=>{
  if(!allU.length){toast('Sem dados','warn');return}
  const now=new Date().toLocaleString('pt-BR');
  const atv=allU.filter(u=>u.ativo&&!isExp(u.expira)).length;
  let t='LUCS TECH - RELATORIO\nGerado: '+now+'\n'+'='.repeat(56)+'\n\nRESUMO\n  Total     : '+allU.length+'\n  Ativos    : '+atv+'\n  Bloqueados: '+allU.filter(u=>!u.ativo).length+'\n  Vencidos  : '+allU.filter(u=>isExp(u.expira)).length+'\n\n'+'='.repeat(56)+'\n\n';
  allU.forEach((u,i)=>{
    t+=String(i+1).padStart(3,'0')+'. '+u.nome+' ['+((u.plano||'basic').toUpperCase())+']\n';
    if(u.empresa)t+='     Empresa   : '+u.empresa+'\n';
    if(u.email)t+='     E-mail    : '+u.email+'\n';
    t+='     Chave     : '+u.chave+'\n     Status    : '+(u.ativo?'ATIVO':'BLOQUEADO')+'\n     Vencimento: '+(u.expira?fDate(u.expira):'Sem limite')+'\n     Ult.acesso: '+(u.ultimo_acesso?fDT(u.ultimo_acesso):'Nunca')+'\n';
    if(u.obs)t+='     Obs       : '+u.obs+'\n';
    t+='\n';
  });
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{type:'text/plain;charset=utf-8'}));
  a.download='lucs-'+Date.now()+'.txt';a.click();
  toast('Relatorio exportado');
};

document.getElementById('btn-exp-logs').onclick=()=>{
  if(!allLogs.length){toast('Sem logs','warn');return}
  let t='DATA/HORA;ACAO;NOME;EMPRESA;CHAVE;IP;SUCESSO\n';
  allLogs.forEach(l=>{t+=`${l.momento||''};${l.acao||''};${l.nome||''};${l.empresa||''};${l.chave||''};${l.ip||''};${l.sucesso?'SIM':'NAO'}\n`});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{type:'text/csv;charset=utf-8'}));
  a.download='lucs-logs-'+Date.now()+'.csv';a.click();
  toast('Logs exportados');
};

document.getElementById('btn-limpar').onclick=async()=>{
  if(!confirm('Limpar todos os logs de login?'))return;
  try{await fetch('/admin/limpar-logs',{method:'POST'});toast('Logs limpos','inf');load()}
  catch{toast('Erro','err')}
};

load();
setInterval(load,20000);
</script>
</body>
</html>"""

@app.route("/")
def root():
    if os.path.exists('planejador.html'):
        return send_file('planejador.html')
    return redirect("/app")

@app.route("/app")
def pg_app():
    return render_template_string(HTML.replace('data-modo="app"', 'data-modo="app"'))

@app.route("/dm")
def pg_dm():
    return render_template_string(HTML.replace('data-modo="app"', 'data-modo="dm"'))

@app.route("/admin-sistema")
def legado():
    return redirect("/app")

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
                cur.execute("UPDATE usuarios SET ultimo_acesso=%s, ip_ultimo=%s WHERE chave=%s", (datetime.now(), ip, chave))
        cur.execute("INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento,ip) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (nome or None, empresa or None, chave, 'login', sucesso, datetime.now(), ip))
        conn.commit(); cur.close(); conn.close()
        if sucesso:
            return jsonify({"ok": True, "nome": nome, "empresa": empresa, "plano": plano})
        return jsonify({"ok": False, "msg": "Acesso negado"}), 403
    except Exception as e:
        print(f"[validar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/dados")
def admin_dados():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome,email,empresa,chave,ativo,expira,plano,obs,ultimo_acesso,ip_ultimo FROM usuarios ORDER BY id DESC")
        usuarios = []
        for r in cur.fetchall():
            d = row_to_dict(r)
            raw = r['ativo']
            if raw is None:             d['ativo'] = False
            elif isinstance(raw, bool): d['ativo'] = raw
            else:                       d['ativo'] = int(raw) == 1
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
            return jsonify({"ok": False, "msg": "Nome obrigatorio"}), 400
        exp = None if ilimitado else (datetime.now().date() + timedelta(days=dias))
        chave = nova_chave()
        conn = get_db(); cur = conn.cursor()
        chave_final = None
        for _ in range(10):
            try:
                cur.execute("INSERT INTO usuarios (nome,empresa,email,chave,expira,ativo,plano,obs,criado_em) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING chave",
                    (nome, empresa, email, chave, exp, 1, plano, obs, datetime.now()))
                chave_final = cur.fetchone()['chave']
                conn.commit(); break
            except psycopg2.errors.UniqueViolation:
                conn.rollback(); chave = nova_chave()
        if not chave_final:
            cur.close(); conn.close()
            return jsonify({"ok": False, "msg": "Erro ao gerar chave"}), 500
        cur.execute("INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento,detalhe) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (nome, empresa, chave_final, 'criacao', 1, datetime.now(), f"plano={plano}"))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True, "chave": chave_final})
    except Exception as e:
        print(f"[admin_criar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/editar", methods=["POST"])
def admin_editar():
    try:
        d            = request.json or {}
        chave        = d.get('chave','')
        nome         = d.get('nome','').strip()
        email        = (d.get('email')   or '').strip() or None
        empresa      = (d.get('empresa') or '').strip() or None
        plano        = d.get('plano','basic')
        obs          = (d.get('obs') or '').strip() or None
        renovar_dias = int(d.get('renovar_dias', 0))
        if not nome:
            return jsonify({"ok": False, "msg": "Nome obrigatorio"}), 400
        conn = get_db(); cur = conn.cursor()
        if renovar_dias == -1:
            cur.execute("UPDATE usuarios SET nome=%s,email=%s,empresa=%s,plano=%s,obs=%s,expira=NULL WHERE chave=%s", (nome, email, empresa, plano, obs, chave))
        elif renovar_dias > 0:
            cur.execute("SELECT expira FROM usuarios WHERE chave=%s", (chave,))
            row  = cur.fetchone()
            base = row['expira'] if row and row['expira'] else datetime.now().date()
            if isinstance(base, str): base = date.fromisoformat(base)
            nova_exp = max(base, datetime.now().date()) + timedelta(days=renovar_dias)
            cur.execute("UPDATE usuarios SET nome=%s,email=%s,empresa=%s,plano=%s,obs=%s,expira=%s WHERE chave=%s", (nome, email, empresa, plano, obs, nova_exp, chave))
        else:
            cur.execute("UPDATE usuarios SET nome=%s,email=%s,empresa=%s,plano=%s,obs=%s WHERE chave=%s", (nome, email, empresa, plano, obs, chave))
        conn.commit()
        cur.execute("INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)", (nome, empresa, chave, 'edicao', 1, datetime.now()))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[admin_editar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    try:
        chave = (request.json or {}).get('chave','')
        conn  = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome, empresa, ativo FROM usuarios WHERE chave=%s", (chave,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({"ok": False, "msg": "Chave nao encontrada"}), 404
        raw   = row['ativo']
        atual = 1 if (raw is True or (not isinstance(raw, bool) and int(raw or 0)==1)) else 0
        novo  = 0 if atual == 1 else 1
        cur.execute("UPDATE usuarios SET ativo=%s WHERE chave=%s", (novo, chave))
        conn.commit()
        cur.execute("INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (row['nome'], row['empresa'], chave, 'ativacao' if novo==1 else 'bloqueio', 1, datetime.now()))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True, "ativo": bool(novo)})
    except Exception as e:
        print(f"[admin_toggle] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    try:
        chave = (request.json or {}).get('chave','')
        conn  = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome, empresa FROM usuarios WHERE chave=%s", (chave,))
        row     = cur.fetchone()
        nome    = row['nome']    if row else None
        empresa = row['empresa'] if row else None
        cur.execute("DELETE FROM logs WHERE chave=%s AND acao='login'", (chave,))
        cur.execute("DELETE FROM usuarios WHERE chave=%s", (chave,))
        if nome:
            cur.execute("INSERT INTO logs (nome,empresa,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s,%s)",
                (nome, empresa, chave, 'remocao', 1, datetime.now()))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[admin_deletar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/bloquear-todos", methods=["POST"])
def bloquear_todos():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET ativo=0 WHERE ativo=1")
        cur.execute("INSERT INTO logs (nome,chave,acao,sucesso,momento) VALUES (%s,%s,%s,%s,%s)",
            ('SISTEMA','TODOS','bloqueio_geral',1,datetime.now()))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[bloquear_todos] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/renovar-vencidos", methods=["POST"])
def renovar_vencidos():
    try:
        dias     = int((request.json or {}).get('dias', 30))
        hoje     = datetime.now().date()
        nova_exp = hoje + timedelta(days=dias)
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET expira=%s WHERE expira < %s", (nova_exp, hoje))
        cur.execute("INSERT INTO logs (nome,chave,acao,sucesso,momento,detalhe) VALUES (%s,%s,%s,%s,%s,%s)",
            ('SISTEMA','TODOS','renovacao',1,datetime.now(),f"+{dias} dias"))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[renovar_vencidos] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/exportar-csv")
def exportar_csv():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT nome,empresa,email,chave,ativo,expira,plano,obs,criado_em,ultimo_acesso,ip_ultimo FROM usuarios ORDER BY id DESC")
        rows = cur.fetchall(); cur.close(); conn.close()
        si = io.StringIO()
        w  = csv.writer(si, delimiter=';')
        w.writerow(['Nome','Empresa','E-mail','Chave','Ativo','Plano','Vencimento','Obs','Criado em','Ultimo acesso','IP ultimo'])
        for r in rows:
            raw_at = r['ativo']
            ativo_str = 'Sim' if (int(raw_at)==1 if raw_at is not None else False) else 'Nao'
            w.writerow([r['nome'] or '',r['empresa'] or '',r['email'] or '',r['chave'] or '',ativo_str,r['plano'] or 'basic',
                r['expira'].isoformat() if r['expira'] else '',r['obs'] or '',
                r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else '',
                r['ultimo_acesso'].strftime('%d/%m/%Y %H:%M') if r['ultimo_acesso'] else '',r['ip_ultimo'] or ''])
        out = make_response(si.getvalue())
        out.headers["Content-Disposition"] = f"attachment; filename=lucs-{datetime.now().strftime('%Y%m%d')}.csv"
        out.headers["Content-type"] = "text/csv; charset=utf-8"
        return out
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/admin/limpar-logs", methods=["POST"])
def limpar_logs():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM logs WHERE acao='login'")
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/health")
def health():
    try:
        conn = get_db(); conn.close()
        return jsonify({"ok": True, "db": "supabase", "ts": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
