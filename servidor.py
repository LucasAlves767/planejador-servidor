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
<title>Lucs Tech — Licenças</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,500;0,600;1,300&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:     #080b10;
  --bg1:    #0c1018;
  --bg2:    #111620;
  --bg3:    #181e2c;
  --bg4:    #1f2638;
  --line:   rgba(255,255,255,.06);
  --line2:  rgba(255,255,255,.11);

  --gold:       #e8a020;
  --gold-lt:    #f5c060;
  --gold-bg:    rgba(232,160,32,.09);
  --gold-glow:  rgba(232,160,32,.22);

  --cyan:       #00c8d4;
  --cyan-lt:    #60e8f0;
  --cyan-bg:    rgba(0,200,212,.08);
  --cyan-glow:  rgba(0,200,212,.18);

  --green:      #00c87a;
  --green-bg:   rgba(0,200,122,.08);
  --green-glow: rgba(0,200,122,.2);

  --red:        #e03040;
  --red-bg:     rgba(224,48,64,.08);
  --red-glow:   rgba(224,48,64,.2);

  --txt:    #e8ecf4;
  --txt2:   #8a94a8;
  --txt3:   #5a6278;
  --txt4:   #363d52;

  --r:  10px;
  --r2: 6px;
  --r3: 4px;
}

html{scroll-behavior:smooth}
body{
  font-family:'IBM Plex Sans',sans-serif;
  background:var(--bg);color:var(--txt);
  min-height:100vh;overflow-x:hidden;
  line-height:1.5;
}

/* Subtle scanline texture */
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.03) 2px,rgba(0,0,0,.03) 4px),
    radial-gradient(ellipse 1200px 700px at 80% -100px, rgba(0,200,212,.04), transparent),
    radial-gradient(ellipse 800px 600px at -10% 90%, rgba(232,160,32,.03), transparent);
}

::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg1)}
::-webkit-scrollbar-thumb{background:var(--bg4);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--txt4)}

.page{max-width:1480px;margin:0 auto;padding:20px 20px;position:relative;z-index:1}

/* ── TOPBAR ── */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  background:rgba(12,16,24,.9);
  border:1px solid var(--line2);
  border-radius:var(--r);padding:12px 20px;margin-bottom:18px;
  position:sticky;top:0;z-index:100;backdrop-filter:blur(20px);
  box-shadow:0 1px 0 rgba(255,255,255,.04), 0 8px 32px rgba(0,0,0,.5);
}
.brand{display:flex;align-items:center;gap:14px}
.brand-mark{
  width:36px;height:36px;border-radius:8px;flex-shrink:0;
  background:linear-gradient(135deg,#1a2030 0%,#0e1420 100%);
  border:1px solid var(--gold-bg);
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 0 0 1px rgba(232,160,32,.15), 0 0 20px var(--gold-glow);
  position:relative;overflow:hidden;
}
.brand-mark::after{
  content:'';position:absolute;inset:0;
  background:radial-gradient(circle at 40% 35%, rgba(232,160,32,.15), transparent 60%);
}
.brand-mark svg{position:relative;z-index:1}
.brand-text{}
.brand-name{
  font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;
  letter-spacing:3px;color:var(--txt);line-height:1.2;
}
.brand-sub{font-size:10px;color:var(--txt3);letter-spacing:1.5px;margin-top:1px;font-family:'IBM Plex Mono',monospace}

.topbar-right{display:flex;align-items:center;gap:10px}

.sys-badge{
  display:flex;align-items:center;gap:8px;padding:6px 14px;
  background:var(--bg2);border:1px solid var(--line);border-radius:20px;
  font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--txt3);
}
.sys-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.sys-dot.ok  {background:var(--green);box-shadow:0 0 8px var(--green-glow);animation:blink 3s infinite}
.sys-dot.err {background:var(--red);box-shadow:0 0 8px var(--red-glow);animation:blink 1.2s infinite}
.sys-dot.warn{background:var(--gold);animation:blink 2s infinite}

.nav-tabs{display:flex;gap:2px;background:var(--bg2);border:1px solid var(--line);border-radius:var(--r2);padding:3px}
.nav-tab{
  padding:5px 16px;border-radius:var(--r3);cursor:pointer;
  font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:2px;
  color:var(--txt3);background:transparent;border:none;transition:all .15s;
  text-decoration:none;display:inline-flex;align-items:center;
}
.nav-tab:hover{color:var(--txt2);background:rgba(255,255,255,.04)}
.nav-tab.on{background:var(--gold);color:#0a0a0a;font-weight:600;box-shadow:0 0 12px var(--gold-glow)}

/* ── KPIs ── */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px}
.kpi{
  background:var(--bg1);border:1px solid var(--line);border-radius:var(--r);
  padding:18px 16px 16px;position:relative;overflow:hidden;
  animation:fadeUp .4s ease both;transition:border-color .2s,transform .2s;
  cursor:default;
}
.kpi:hover{border-color:var(--line2);transform:translateY(-2px)}
.kpi-stripe{position:absolute;top:0;left:0;right:0;height:2px;border-radius:2px 2px 0 0}
.kpi:nth-child(1) .kpi-stripe{background:var(--cyan)}
.kpi:nth-child(2) .kpi-stripe{background:var(--green)}
.kpi:nth-child(3) .kpi-stripe{background:var(--red)}
.kpi:nth-child(4) .kpi-stripe{background:var(--gold)}
.kpi:nth-child(5) .kpi-stripe{background:#8b7cf8}
.kpi:nth-child(6) .kpi-stripe{background:#f06080}
.kpi-icon{
  position:absolute;bottom:12px;right:14px;
  font-size:22px;opacity:.06;line-height:1;
  font-family:'IBM Plex Mono',monospace;
}
.kpi-label{
  font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:2.5px;
  color:var(--txt3);margin-bottom:10px;
}
.kpi-val{
  font-family:'IBM Plex Mono',monospace;font-size:32px;font-weight:500;
  line-height:1;letter-spacing:-1px;color:var(--txt);
}
.kpi-sub{font-size:11px;color:var(--txt3);margin-top:6px;font-weight:300}
.kpi:nth-child(1) .kpi-val{color:var(--cyan)}
.kpi:nth-child(2) .kpi-val{color:var(--green)}
.kpi:nth-child(3) .kpi-val{color:var(--red)}
.kpi:nth-child(4) .kpi-val{color:var(--gold)}
.kpi:nth-child(5) .kpi-val{color:#8b7cf8}
.kpi:nth-child(6) .kpi-val{color:#f06080}

/* ── PANEL ── */
.panel{
  background:var(--bg1);border:1px solid var(--line);border-radius:var(--r);
  overflow:hidden;animation:fadeUp .4s .1s ease both;
}
.panel-tabs{
  display:flex;border-bottom:1px solid var(--line);
  background:var(--bg2);padding:0 20px;gap:0;
}
.ptab{
  padding:13px 20px;cursor:pointer;border:none;background:transparent;
  font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:2px;
  color:var(--txt3);border-bottom:2px solid transparent;margin-bottom:-1px;
  transition:all .15s;white-space:nowrap;display:flex;align-items:center;gap:7px;
}
.ptab:hover:not(.on){color:var(--txt2)}
.ptab.on{color:var(--gold);border-bottom-color:var(--gold)}
.ptab svg{opacity:.6}
.ptab.on svg{opacity:1}

.tab-body{display:none;padding:22px 20px 28px}
.tab-body.on{display:block}

/* ── SECTION HEADER ── */
.sec-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px}
.sec-left{display:flex;align-items:center;gap:10px}
.sec-title{
  font-family:'IBM Plex Mono',monospace;font-size:9px;
  letter-spacing:2.5px;color:var(--txt3);
}
.n-badge{
  padding:2px 10px;border-radius:20px;
  background:var(--cyan-bg);color:var(--cyan);
  border:1px solid rgba(0,200,212,.18);
  font-family:'IBM Plex Mono',monospace;font-size:10px;
}
.sec-right{display:flex;gap:6px;flex-wrap:wrap;align-items:center}

/* ── BUTTONS ── */
.btn{
  display:inline-flex;align-items:center;gap:6px;
  padding:7px 14px;border-radius:var(--r2);cursor:pointer;
  font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1.5px;
  border:1px solid transparent;transition:all .15s;white-space:nowrap;font-weight:500;
}
.btn-gold{background:var(--gold);color:#0a0a0a;border-color:var(--gold);box-shadow:0 0 16px var(--gold-glow)}
.btn-gold:hover{background:var(--gold-lt);box-shadow:0 0 24px var(--gold-glow);transform:translateY(-1px)}
.btn-ghost{background:transparent;color:var(--txt3);border-color:var(--line2)}
.btn-ghost:hover{background:var(--bg3);color:var(--txt);border-color:rgba(255,255,255,.15)}
.btn-cyan{background:var(--cyan-bg);color:var(--cyan);border-color:rgba(0,200,212,.2)}
.btn-cyan:hover{background:rgba(0,200,212,.14)}
.btn-green{background:var(--green-bg);color:var(--green);border-color:rgba(0,200,122,.2)}
.btn-green:hover{background:rgba(0,200,122,.14)}
.btn-red{background:var(--red-bg);color:var(--red);border-color:rgba(224,48,64,.2)}
.btn-red:hover{background:rgba(224,48,64,.14)}
.btn-sm{padding:5px 11px;font-size:8px}
.btn:disabled{opacity:.35;cursor:not-allowed;transform:none!important}

/* ── TOOLBAR ── */
.toolbar{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.search-wrap{position:relative;flex:1;min-width:220px}
.search-wrap .ico{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--txt4);pointer-events:none}
.search-wrap input{padding-left:34px}
.filters{display:flex;gap:4px;flex-wrap:wrap}
.fchip{
  padding:5px 12px;border-radius:20px;cursor:pointer;
  font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:1.5px;
  border:1px solid var(--line);color:var(--txt3);background:transparent;transition:all .15s;
}
.fchip:hover:not(.on){border-color:var(--line2);color:var(--txt2)}
.fchip.on{background:var(--cyan-bg);border-color:rgba(0,200,212,.25);color:var(--cyan)}

/* ── INPUTS ── */
input,select,textarea{
  background:var(--bg2);border:1px solid var(--line2);
  padding:9px 12px;border-radius:var(--r2);
  color:var(--txt);font-family:'IBM Plex Sans',sans-serif;font-size:13px;
  outline:none;transition:border-color .15s,box-shadow .15s;width:100%;
}
textarea{resize:vertical;min-height:76px}
input::placeholder,textarea::placeholder{color:var(--txt4)}
input:focus,select:focus,textarea:focus{
  border-color:rgba(232,160,32,.5);
  box-shadow:0 0 0 3px rgba(232,160,32,.08);
}
select option{background:var(--bg2)}
.flabel{
  font-family:'IBM Plex Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--txt3);display:block;margin-bottom:5px;
}
.fgroup{display:flex;flex-direction:column}
.fgrid{display:grid;grid-template-columns:1.3fr 1fr 1fr 110px 80px 90px auto;gap:10px;align-items:end}
.fgrid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}

/* ── TABLE ── */
.tw{overflow-x:auto;border-radius:var(--r2);border:1px solid var(--line)}
table{width:100%;border-collapse:collapse}
thead{background:var(--bg2)}
th{
  font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:2px;color:var(--txt3);
  padding:10px 14px;border-bottom:1px solid var(--line);
  text-align:left;white-space:nowrap;cursor:pointer;user-select:none;
}
th:hover{color:var(--txt2)}
th .si::after{content:' ⇅';opacity:.2;font-size:9px}
th.asc .si::after{content:' ▲';opacity:1;color:var(--cyan)}
th.desc .si::after{content:' ▼';opacity:1;color:var(--cyan)}
td{padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:middle;font-size:13px}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .1s}
tbody tr:hover td{background:rgba(255,255,255,.015)}

/* client name cell */
.cname b{font-weight:500;color:var(--txt)}
.cname small{font-size:11px;color:var(--txt3);display:block;margin-top:2px;font-weight:300}

/* empresa tag */
.etag{
  display:inline-flex;align-items:center;gap:5px;
  background:var(--bg3);color:var(--txt2);
  border:1px solid var(--line2);border-radius:var(--r3);
  padding:3px 9px;font-size:11px;
  max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}

/* plan badge */
.pbadge{
  display:inline-block;border-radius:var(--r3);padding:3px 9px;
  font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:1px;font-weight:500;
}
.pb-basic     {background:rgba(90,98,120,.15);color:var(--txt3);border:1px solid rgba(90,98,120,.2)}
.pb-pro       {background:var(--cyan-bg);color:var(--cyan);border:1px solid rgba(0,200,212,.2)}
.pb-enterprise{background:rgba(139,124,248,.08);color:#8b7cf8;border:1px solid rgba(139,124,248,.2)}

/* key chip */
.kchip{
  display:inline-flex;align-items:center;gap:6px;cursor:pointer;
  background:var(--bg3);color:var(--gold);
  border:1px solid rgba(232,160,32,.2);border-radius:var(--r3);
  padding:4px 10px;font-family:'IBM Plex Mono',monospace;font-size:10px;
  transition:all .15s;
}
.kchip:hover{background:var(--gold-bg);border-color:rgba(232,160,32,.35)}
.kchip:active{transform:scale(.97)}

/* expiry */
.ex{font-size:12px;font-family:'IBM Plex Mono',monospace}
.ex.exp {color:var(--red)}
.ex.warn{color:var(--gold)}
.ex.ok  {color:var(--txt3)}
.ex.none{color:var(--txt4)}

/* status toggle */
.stoggle{
  display:inline-flex;align-items:center;gap:7px;
  padding:4px 12px;border-radius:20px;cursor:pointer;
  font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1px;
  border:1px solid transparent;transition:all .15s;
}
.stoggle.on {background:var(--green-bg);color:var(--green);border-color:rgba(0,200,122,.2)}
.stoggle.off{background:var(--red-bg);color:var(--red);border-color:rgba(224,48,64,.2)}
.stoggle.on:hover {background:rgba(0,200,122,.14);transform:scale(1.03)}
.stoggle.off:hover{background:rgba(224,48,64,.14);transform:scale(1.03)}
.sdot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.sdot.on {background:var(--green);box-shadow:0 0 6px var(--green-glow);animation:blink 2.5s infinite}
.sdot.off{background:var(--red)}

/* last access */
.lacc{font-size:11px;color:var(--txt3);font-weight:300}
.lacc.fresh{color:var(--green)}

/* row actions */
.row-acts{display:flex;gap:3px;justify-content:flex-end}
.ibtn{
  background:none;border:none;color:var(--txt4);cursor:pointer;
  padding:5px 7px;border-radius:var(--r3);transition:all .15s;
}
.ibtn.edit:hover{color:var(--cyan);background:var(--cyan-bg)}
.ibtn.del:hover {color:var(--red);background:var(--red-bg)}

.empty{text-align:center;padding:52px;color:var(--txt3);font-size:13px}
.ei{font-size:24px;opacity:.15;display:block;margin-bottom:10px;font-family:'IBM Plex Mono',monospace}

/* ── MODAL ── */
.overlay{
  position:fixed;inset:0;background:rgba(4,6,10,.85);z-index:300;
  display:flex;align-items:center;justify-content:center;
  opacity:0;pointer-events:none;transition:opacity .2s;backdrop-filter:blur(12px);
}
.overlay.open{opacity:1;pointer-events:all}
.modal{
  background:var(--bg2);border:1px solid var(--line2);
  border-radius:var(--r);padding:28px;width:100%;max-width:520px;max-height:90vh;overflow-y:auto;
  transform:translateY(16px) scale(.98);transition:transform .25s cubic-bezier(.34,1.4,.64,1);
  box-shadow:0 40px 100px rgba(0,0,0,.7), 0 0 0 1px rgba(232,160,32,.06);
}
.overlay.open .modal{transform:none}
.modal-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}
.modal-title{
  display:flex;align-items:center;gap:10px;
  font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2.5px;color:var(--txt2);
}
.modal-icon{
  width:28px;height:28px;
  background:var(--gold-bg);border:1px solid rgba(232,160,32,.2);
  border-radius:var(--r3);display:flex;align-items:center;justify-content:center;
}
.mclose{
  background:none;border:none;color:var(--txt3);cursor:pointer;
  padding:4px 8px;border-radius:var(--r3);font-size:16px;transition:all .15s;
}
.mclose:hover{color:var(--red);background:var(--red-bg)}
.mgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.mgrid.full{grid-template-columns:1fr}
.ropts{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.ropt{
  padding:5px 13px;border-radius:var(--r3);cursor:pointer;
  font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1px;
  border:1px solid var(--line2);color:var(--txt3);background:transparent;transition:all .15s;
}
.ropt:hover:not(.on){border-color:var(--line2);color:var(--txt2)}
.ropt.on{background:var(--green-bg);border-color:rgba(0,200,122,.3);color:var(--green)}
.modal-footer{display:flex;gap:8px;justify-content:flex-end;margin-top:22px;padding-top:18px;border-top:1px solid var(--line)}

/* ── STATS ── */
.sgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.scard{background:var(--bg2);border:1px solid var(--line);border-radius:var(--r);padding:18px}
.scard-title{font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:2.5px;color:var(--txt3);margin-bottom:14px}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-size:12px}
.bar-name{width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--txt2);flex-shrink:0;font-weight:300}
.bar-track{flex:1;height:3px;background:var(--bg4);border-radius:2px;overflow:hidden}
.bar-fill{height:100%;border-radius:2px;transition:width .6s ease}
.bar-val{width:22px;text-align:right;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--txt3);flex-shrink:0}
.drow{display:flex;align-items:center;gap:18px}
.dleg{flex:1}
.dleg-row{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12px;color:var(--txt2);font-weight:300}
.dleg-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dleg-val{margin-left:auto;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--txt3)}

/* ── LOGS ── */
.logbox{
  background:var(--bg2);border:1px solid var(--line);border-radius:var(--r2);
  padding:14px;max-height:280px;overflow-y:auto;
  font-family:'IBM Plex Mono',monospace;font-size:10px;line-height:2;
}
.lrow{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.lts{color:var(--txt4);font-size:9px;flex-shrink:0;min-width:80px}
.lok  {color:var(--green)}
.lfail{color:var(--red)}
.linf {color:var(--gold)}
.lsys {color:var(--cyan)}
.lip  {font-size:9px;color:var(--txt4);margin-left:auto}
.lsep{border:none;border-top:1px solid var(--line);margin:4px 0}

/* ── KEY PREVIEW ── */
.kprev{
  background:var(--bg2);border:1px solid var(--line);border-radius:var(--r2);
  padding:18px;display:flex;flex-direction:column;justify-content:center;
}
.kprev-label{font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:2px;color:var(--txt3);margin-bottom:10px}
.kprev-val{font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--txt4);word-break:break-all}
.kprev-val.ready{color:var(--gold);text-shadow:0 0 20px var(--gold-glow)}
.kprev-info{font-size:11px;color:var(--txt3);margin-top:10px;font-weight:300;line-height:1.6}

/* ── DIVIDER ── */
.divider{height:1px;background:var(--line);margin:18px 0}

/* ── TOAST ── */
.toast{
  position:fixed;bottom:22px;right:22px;z-index:999;
  background:var(--bg3);border:1px solid var(--line2);
  padding:11px 18px;border-radius:var(--r2);
  font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.5px;color:var(--txt);
  display:flex;align-items:center;gap:10px;
  box-shadow:0 16px 48px rgba(0,0,0,.6);
  opacity:0;transform:translateY(10px) scale(.97);
  transition:all .2s cubic-bezier(.34,1.3,.64,1);pointer-events:none;max-width:300px;
}
.toast.show{opacity:1;transform:none}
.tdot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.tok  {background:var(--green)}
.terr {background:var(--red)}
.twarn{background:var(--gold)}
.tinf {background:var(--cyan)}

/* ── ANIMATIONS ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.4}}

/* ── RESPONSIVE ── */
@media(max-width:1200px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px) {.kpis{grid-template-columns:repeat(2,1fr)}.fgrid{grid-template-columns:1fr 1fr}.sgrid{grid-template-columns:1fr}}
@media(max-width:600px) {.kpis{grid-template-columns:1fr 1fr}.mgrid{grid-template-columns:1fr}}
</style>
</head>
<body data-modo="app">
<div class="page">

  <!-- TOPBAR -->
  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--gold)" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div class="brand-text">
        <div class="brand-name">LUCS TECH</div>
        <div class="brand-sub">ACCESS CONTROL v2</div>
      </div>
    </div>
    <div class="topbar-right">
      <div class="sys-badge">
        <div class="sys-dot warn" id="hdot"></div>
        <span id="hstatus">CONECTANDO</span>
      </div>
      <div class="nav-tabs">
        <a href="/app" class="nav-tab" id="nav-app">APP</a>
        <a href="/dm"  class="nav-tab" id="nav-dm">DM</a>
      </div>
    </div>
  </div>

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi" style="animation-delay:.05s">
      <div class="kpi-stripe"></div>
      <div class="kpi-icon">⬡</div>
      <div class="kpi-label">TOTAL</div>
      <div class="kpi-val" id="k-total">—</div>
      <div class="kpi-sub">clientes cadastrados</div>
    </div>
    <div class="kpi" style="animation-delay:.08s">
      <div class="kpi-stripe"></div>
      <div class="kpi-icon">◉</div>
      <div class="kpi-label">ATIVOS</div>
      <div class="kpi-val" id="k-ativos">—</div>
      <div class="kpi-sub" id="k-ativos-pct">—</div>
    </div>
    <div class="kpi" style="animation-delay:.11s">
      <div class="kpi-stripe"></div>
      <div class="kpi-icon">⊘</div>
      <div class="kpi-label">BLOQUEADOS</div>
      <div class="kpi-val" id="k-bloq">—</div>
      <div class="kpi-sub" id="k-bloq-pct">—</div>
    </div>
    <div class="kpi" style="animation-delay:.14s">
      <div class="kpi-stripe"></div>
      <div class="kpi-icon">◌</div>
      <div class="kpi-label">VENCIDOS</div>
      <div class="kpi-val" id="k-venc">—</div>
      <div class="kpi-sub">licenças expiradas</div>
    </div>
    <div class="kpi" style="animation-delay:.17s">
      <div class="kpi-stripe"></div>
      <div class="kpi-icon">◈</div>
      <div class="kpi-label">LOGINS HOJE</div>
      <div class="kpi-val" id="k-hoje">—</div>
      <div class="kpi-sub">autenticações válidas</div>
    </div>
    <div class="kpi" style="animation-delay:.20s">
      <div class="kpi-stripe"></div>
      <div class="kpi-icon">◫</div>
      <div class="kpi-label">NEGADOS HOJE</div>
      <div class="kpi-val" id="k-neg">—</div>
      <div class="kpi-sub">acessos bloqueados</div>
    </div>
  </div>

  <!-- PANEL -->
  <div class="panel">
    <div class="panel-tabs">
      <button class="ptab on" data-tab="licencas">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>
        LICENÇAS
      </button>
      <button class="ptab" data-tab="nova">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
        NOVA LICENÇA
      </button>
      <button class="ptab" data-tab="stats">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        ESTATÍSTICAS
      </button>
      <button class="ptab" data-tab="logs">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M9 13h6M9 17h6M9 9h1"/></svg>
        ATIVIDADE
      </button>
    </div>

    <!-- TAB: LICENÇAS -->
    <div class="tab-body on" id="tab-licencas">
      <div class="sec-hd">
        <div class="sec-left">
          <div class="sec-title">LICENÇAS CADASTRADAS</div>
          <span class="n-badge" id="badge-n">0</span>
        </div>
        <div class="sec-right">
          <a href="/admin/exportar-csv" class="btn btn-cyan btn-sm" download>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            CSV
          </a>
          <button class="btn btn-ghost btn-sm" id="btn-rel">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
            TXT
          </button>
          <button class="btn btn-green btn-sm" id="btn-renovar-venc">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            RENOVAR VENCIDOS
          </button>
          <button class="btn btn-red btn-sm" id="btn-bloqtodos">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
            BLOQUEAR TODOS
          </button>
        </div>
      </div>

      <div class="toolbar">
        <div class="search-wrap">
          <svg class="ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input id="inp-q" type="text" placeholder="Buscar por nome, empresa, chave, e-mail, plano..."/>
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
            <th data-col="nome">CLIENTE <span class="si"></span></th>
            <th data-col="empresa">EMPRESA <span class="si"></span></th>
            <th>PLANO</th>
            <th data-col="chave">CHAVE <span class="si"></span></th>
            <th data-col="expira">VENCIMENTO <span class="si"></span></th>
            <th data-col="ultimo_acesso">ÚLTIMO ACESSO <span class="si"></span></th>
            <th>STATUS</th>
            <th></th>
          </tr></thead>
          <tbody id="tbody">
            <tr><td colspan="8" class="empty"><span class="ei">⟳</span>Carregando dados...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB: NOVA LICENÇA -->
    <div class="tab-body" id="tab-nova">
      <div class="sec-hd"><div class="sec-title">CRIAR NOVA LICENÇA</div></div>
      <div class="fgrid">
        <div class="fgroup"><label class="flabel">NOME *</label><input id="i-nome" type="text" placeholder="Nome completo do cliente"/></div>
        <div class="fgroup"><label class="flabel">EMPRESA</label><input id="i-empresa" type="text" placeholder="Empresa (opcional)"/></div>
        <div class="fgroup"><label class="flabel">E-MAIL</label><input id="i-email" type="email" placeholder="email@dominio.com"/></div>
        <div class="fgroup"><label class="flabel">PLANO</label>
          <select id="i-plano"><option value="basic">BASIC</option><option value="pro">PRO</option><option value="enterprise">ENTERPRISE</option></select>
        </div>
        <div class="fgroup"><label class="flabel">DIAS</label><input id="i-dias" type="number" value="30" min="1" max="3650"/></div>
        <div class="fgroup"><label class="flabel">ILIMITADO</label>
          <select id="i-ilimitado"><option value="0">NÃO</option><option value="1">SIM</option></select>
        </div>
        <button class="btn btn-gold" id="btn-criar" style="align-self:end">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
          GERAR
        </button>
      </div>
      <div class="fgrid2">
        <div class="fgroup"><label class="flabel">OBSERVAÇÕES</label><textarea id="i-obs" placeholder="Notas internas sobre este cliente..."></textarea></div>
        <div class="kprev">
          <div class="kprev-label">CHAVE GERADA</div>
          <div class="kprev-val" id="preview-chave">— aguardando —</div>
          <div class="kprev-info" id="preview-info"></div>
        </div>
      </div>
    </div>

    <!-- TAB: ESTATÍSTICAS -->
    <div class="tab-body" id="tab-stats">
      <div class="sgrid">
        <div class="scard"><div class="scard-title">TOP EMPRESAS</div><div id="st-empresas"></div></div>
        <div class="scard">
          <div class="scard-title">DISTRIBUIÇÃO POR PLANO</div>
          <div class="drow" style="margin-top:8px">
            <canvas id="donut-canvas" width="86" height="86"></canvas>
            <div class="dleg" id="donut-leg"></div>
          </div>
        </div>
        <div class="scard">
          <div class="scard-title">LOGINS — ÚLTIMOS 7 DIAS</div>
          <canvas id="spark-canvas" style="width:100%;height:60px;display:block;margin-top:8px"></canvas>
          <div id="spark-labels" style="display:flex;justify-content:space-between;font-family:'IBM Plex Mono',monospace;font-size:8px;color:var(--txt4);margin-top:5px"></div>
        </div>
      </div>
    </div>

    <!-- TAB: ATIVIDADE -->
    <div class="tab-body" id="tab-logs">
      <div class="sec-hd">
        <div class="sec-title">ATIVIDADE RECENTE</div>
        <div style="display:flex;gap:6px">
          <button class="btn btn-ghost btn-sm" id="btn-exp-logs">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            EXPORTAR
          </button>
          <button class="btn btn-red btn-sm" id="btn-limpar">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>
            LIMPAR LOGS
          </button>
        </div>
      </div>
      <div class="logbox" id="logs">Carregando...</div>
    </div>
  </div>
</div>

<!-- MODAL EDITAR -->
<div class="overlay" id="modal-overlay">
  <div class="modal">
    <div class="modal-hd">
      <div class="modal-title">
        <div class="modal-icon">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--gold)" stroke-width="2">
            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </div>
        EDITAR LICENÇA
      </div>
      <button class="mclose" id="modal-close">✕</button>
    </div>
    <div class="mgrid">
      <div class="fgroup"><label class="flabel">NOME</label><input id="m-nome" type="text"/></div>
      <div class="fgroup"><label class="flabel">E-MAIL</label><input id="m-email" type="email"/></div>
      <div class="fgroup"><label class="flabel">EMPRESA</label><input id="m-empresa" type="text"/></div>
      <div class="fgroup"><label class="flabel">PLANO</label>
        <select id="m-plano">
          <option value="basic">BASIC</option>
          <option value="pro">PRO</option>
          <option value="enterprise">ENTERPRISE</option>
        </select>
      </div>
    </div>
    <div class="fgroup mgrid full" style="margin-bottom:16px">
      <label class="flabel">OBSERVAÇÕES</label><textarea id="m-obs"></textarea>
    </div>
    <div class="fgroup">
      <label class="flabel">RENOVAR LICENÇA</label>
      <div class="ropts">
        <button class="ropt on" data-d="0">SEM ALTERAÇÃO</button>
        <button class="ropt" data-d="7">+7 DIAS</button>
        <button class="ropt" data-d="30">+30 DIAS</button>
        <button class="ropt" data-d="90">+90 DIAS</button>
        <button class="ropt" data-d="365">+1 ANO</button>
        <button class="ropt" data-d="-1">ILIMITADO</button>
      </div>
    </div>
    <input type="hidden" id="m-chave"/>
    <div class="modal-footer">
      <button class="btn btn-ghost" id="modal-cancel">CANCELAR</button>
      <button class="btn btn-gold" id="modal-save">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v14a2 2 0 01-2 2z"/>
          <polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>
        </svg>
        SALVAR
      </button>
    </div>
  </div>
</div>

<!-- TOAST -->
<div class="toast" id="toast">
  <div class="tdot tok" id="tdot"></div>
  <span id="tmsg"></span>
</div>

<script>
/* ── INIT ── */
const MODO = document.body.dataset.modo || 'app';
const navEl = document.getElementById('nav-' + MODO);
if (navEl) navEl.classList.add('on');

let allU=[], allLogs=[], filtro='todos', busca='', sortCol='', sortDir=1, editDias=0;

/* ── TOAST ── */
let _tt;
function toast(msg, tipo='ok'){
  document.getElementById('tdot').className='tdot t'+tipo;
  document.getElementById('tmsg').textContent=msg;
  const el=document.getElementById('toast');
  el.classList.add('show'); clearTimeout(_tt);
  _tt=setTimeout(()=>el.classList.remove('show'),3000);
}

/* ── UTILS ── */
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fDate(s){return s?new Date(s+'T00:00:00').toLocaleDateString('pt-BR'):''}
function fDT(s){return s?new Date(s).toLocaleString('pt-BR'):null}
function ago(s){
  if(!s)return null;
  const h=(Date.now()-new Date(s).getTime())/3600000;
  if(h<1)return'Agora';
  if(h<24)return Math.floor(h)+'h atrás';
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

/* ── TABS ── */
document.querySelectorAll('.ptab').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('.ptab').forEach(x=>x.classList.remove('on'));
    document.querySelectorAll('.tab-body').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    document.getElementById('tab-'+b.dataset.tab).classList.add('on');
    if(b.dataset.tab==='stats')renderStats();
  }
});

/* ── LOAD DATA ── */
async function load(){
  try{
    const r=await fetch('/admin/dados');
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();
    if(!d.usuarios)throw new Error('sem dados');
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
    document.getElementById('k-neg').textContent=d.negados_hoje||0;
    document.getElementById('hdot').className='sys-dot ok';
    document.getElementById('hstatus').textContent='ONLINE';
    renderT(); renderLogs();
  }catch(e){
    document.getElementById('hdot').className='sys-dot err';
    document.getElementById('hstatus').textContent='ERRO BD';
    console.error('Load error:',e);
  }
}

/* ── RENDER TABLE ── */
function renderT(){
  let list=[...allU];
  if(filtro==='ativo')    list=list.filter(u=>u.ativo&&!isExp(u.expira));
  else if(filtro==='bloqueado')list=list.filter(u=>!u.ativo);
  else if(filtro==='vencido')  list=list.filter(u=>isExp(u.expira));
  else if(filtro==='vence7')   list=list.filter(u=>vence7(u.expira));
  if(busca){const q=busca.toLowerCase();list=list.filter(u=>['nome','empresa','email','chave','plano'].some(k=>(u[k]||'').toLowerCase().includes(q)))}
  if(sortCol)list.sort((a,b)=>String(a[sortCol]||'').localeCompare(String(b[sortCol]||''))*sortDir);
  document.getElementById('badge-n').textContent=list.length;
  const tb=document.getElementById('tbody');
  if(!list.length){tb.innerHTML='<tr><td colspan="8" class="empty"><span class="ei">⌀</span>Nenhum resultado.</td></tr>';return}
  const exLbl={exp:'Vencida',warn:'Vence em breve',ok:'',none:'Sem limite'};
  tb.innerHTML=list.map(u=>{
    const es=exSt(u.expira);
    const exTxt=es==='ok'?fDate(u.expira):exLbl[es];
    const a=ago(u.ultimo_acesso);
    const fresh=u.ultimo_acesso&&(Date.now()-new Date(u.ultimo_acesso).getTime())<3600000;
    const plano=u.plano||'basic';
    const ud=JSON.stringify(u).replace(/"/g,'&quot;');
    return`<tr>
      <td class="cname"><b>${esc(u.nome)}</b><small>${esc(u.email||'')}</small></td>
      <td>${u.empresa?`<span class="etag">${esc(u.empresa)}</span>`:'<span style="color:var(--txt4)">—</span>'}</td>
      <td><span class="pbadge ${planoCls(plano)}">${plano.toUpperCase()}</span></td>
      <td><span class="kchip" data-k="${esc(u.chave)}">
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="11" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
        ${esc(u.chave)}</span></td>
      <td><span class="ex ${es}">${exTxt||'—'}</span></td>
      <td><span class="lacc${fresh?' fresh':''}">${a||'<span style="color:var(--txt4)">Nunca</span>'}</span></td>
      <td><button class="stoggle ${u.ativo?'on':'off'}" data-k="${esc(u.chave)}">
        <span class="sdot ${u.ativo?'on':'off'}"></span>${u.ativo?'ATIVO':'BLOQUEADO'}
      </button></td>
      <td><div class="row-acts">
        <button class="ibtn edit" data-ud="${ud}" title="Editar">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button class="ibtn del" data-k="${esc(u.chave)}" title="Remover">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>
        </button>
      </div></td>
    </tr>`;
  }).join('');
  tb.querySelectorAll('.kchip').forEach(e=>e.onclick=()=>{navigator.clipboard.writeText(e.dataset.k);toast('Chave copiada!')});
  tb.querySelectorAll('.stoggle').forEach(e=>e.onclick=()=>tog(e.dataset.k));
  tb.querySelectorAll('.ibtn.del').forEach(e=>e.onclick=()=>rem(e.dataset.k));
  tb.querySelectorAll('.ibtn.edit').forEach(e=>e.onclick=()=>{
    try{openEdit(JSON.parse(e.dataset.ud.replace(/&quot;/g,'"')))}catch{}
  });
}

/* ── SORT & FILTER ── */
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

/* ── CRIAR ── */
document.getElementById('btn-criar').onclick=async()=>{
  const nome=document.getElementById('i-nome').value.trim();
  if(!nome){toast('Informe o nome do cliente','warn');return}
  const btn=document.getElementById('btn-criar');
  btn.disabled=true;btn.textContent='...';
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
      const prev=document.getElementById('preview-chave');
      prev.textContent=d.chave;prev.classList.add('ready');
      document.getElementById('preview-info').innerHTML=
        'Gerado em '+new Date().toLocaleString('pt-BR')+
        '<br>Plano: '+document.getElementById('i-plano').value.toUpperCase()+
        ' · '+(document.getElementById('i-ilimitado').value==='1'?'Sem limite':document.getElementById('i-dias').value+' dias');
      toast('Licença gerada: '+d.chave);
      ['i-nome','i-empresa','i-email','i-obs'].forEach(id=>document.getElementById(id).value='');
      load();
    }else toast(d.msg||'Erro ao criar','err');
  }catch{toast('Erro de conexão','err')}
  finally{
    btn.disabled=false;
    btn.innerHTML='<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>GERAR';
  }
};

/* ── TOGGLE ── */
async function tog(chave){
  try{
    const r=await fetch('/admin/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});
    const d=await r.json();
    if(d.ok){toast(d.ativo?'Ativado!':'Bloqueado!',d.ativo?'ok':'warn');load()}
    else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexão','err')}
}

/* ── DELETAR ── */
async function rem(chave){
  if(!confirm('Remover este cliente permanentemente?'))return;
  try{
    const r=await fetch('/admin/deletar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});
    const d=await r.json();
    if(d.ok){toast('Removido','inf');load()}else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexão','err')}
}

/* ── BLOQUEAR TODOS ── */
document.getElementById('btn-bloqtodos').onclick=async()=>{
  const n=allU.filter(u=>u.ativo).length;
  if(!n){toast('Nenhum ativo','warn');return}
  if(!confirm('Bloquear '+n+' cliente(s) ativo(s)?'))return;
  try{await fetch('/admin/bloquear-todos',{method:'POST'});toast(n+' clientes bloqueados','warn');load()}
  catch{toast('Erro','err')}
};

/* ── RENOVAR VENCIDOS ── */
document.getElementById('btn-renovar-venc').onclick=async()=>{
  const venc=allU.filter(u=>isExp(u.expira));
  if(!venc.length){toast('Nenhum vencido','warn');return}
  const dias=prompt('Renovar '+venc.length+' licença(s) vencida(s) por quantos dias?','30');
  if(!dias||isNaN(dias))return;
  try{
    const r=await fetch('/admin/renovar-vencidos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dias:parseInt(dias)})});
    const d=await r.json();
    if(d.ok){toast(venc.length+' licenças renovadas por '+dias+' dias');load()}else toast(d.msg||'Erro','err');
  }catch{toast('Erro','err')}
};

/* ── MODAL EDITAR ── */
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
      chave:editChave,
      nome:document.getElementById('m-nome').value.trim(),
      email:document.getElementById('m-email').value.trim(),
      empresa:document.getElementById('m-empresa').value.trim(),
      plano:document.getElementById('m-plano').value,
      obs:document.getElementById('m-obs').value.trim(),
      renovar_dias:editDias
    })});
    const d=await r.json();
    if(d.ok){toast('Salvo com sucesso!');closeModal();load()}else toast(d.msg||'Erro','err');
  }catch{toast('Erro de conexão','err')}
};

/* ── RENDER LOGS ── */
function renderLogs(){
  const lb=document.getElementById('logs');
  if(!allLogs.length){lb.innerHTML='<span style="color:var(--txt4)">Sem atividade registrada.</span>';return}
  lb.innerHTML=allLogs.map(l=>{
    let cls,icon,lbl;
    if(l.acao==='login'){cls=l.sucesso?'lok':'lfail';icon=l.sucesso?'✓':'✗';lbl=l.sucesso?'LOGIN OK':'NEGADO'}
    else if(l.acao==='bloqueio_geral'){cls='lsys';icon='⊘';lbl='BLOQ.GERAL'}
    else if(l.acao==='criacao'){cls='linf';icon='+';lbl='CRIAÇÃO'}
    else if(l.acao==='edicao'){cls='linf';icon='~';lbl='EDIÇÃO'}
    else if(l.acao==='renovacao'){cls='lok';icon='↻';lbl='RENOVAÇÃO'}
    else{cls='linf';icon='·';lbl=(l.acao||'').toUpperCase()}
    const nm=l.nome?' <span style="color:var(--txt2)">'+esc(l.nome)+'</span>':'';
    const em=l.empresa?' <span style="color:var(--cyan)">'+esc(l.empresa)+'</span>':'';
    const ts=l.momento?new Date(l.momento).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
    const ip=l.ip?'<span class="lip">'+esc(l.ip)+'</span>':'';
    return'<div class="lrow"><span class="lts">'+ts+'</span><span class="'+cls+'">'+icon+' '+lbl+'</span>'+nm+em+'<span style="color:var(--txt4);font-size:9px">'+esc(l.chave||'')+'</span>'+ip+'</div>';
  }).join('');
}

/* ── RENDER STATS ── */
function renderStats(){
  // Empresas
  const emp={};
  allU.forEach(u=>{if(u.empresa)emp[u.empresa]=(emp[u.empresa]||0)+1});
  const topEmp=Object.entries(emp).sort((a,b)=>b[1]-a[1]).slice(0,6);
  const maxE=topEmp[0]?.[1]||1;
  const bColors=['var(--cyan)','var(--green)','var(--gold)','#8b7cf8','#f06080','#60d4a0'];
  document.getElementById('st-empresas').innerHTML=topEmp.length
    ?topEmp.map(([nm,n],i)=>`<div class="bar-row"><span class="bar-name" title="${esc(nm)}">${esc(nm)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.round(n/maxE*100)}%;background:${bColors[i%bColors.length]}"></div></div><span class="bar-val">${n}</span></div>`).join('')
    :'<span style="color:var(--txt4);font-size:12px">Sem dados</span>';

  // Donut planos
  const planos={basic:0,pro:0,enterprise:0};
  allU.forEach(u=>planos[u.plano||'basic']=(planos[u.plano||'basic']||0)+1);
  const pColors={basic:'#4a5268',pro:'#00c8d4',enterprise:'#8b7cf8'};
  const pNames={basic:'Basic',pro:'Pro',enterprise:'Enterprise'};
  const total=allU.length||1;
  const dc=document.getElementById('donut-canvas');
  const ctx=dc.getContext('2d');
  ctx.clearRect(0,0,86,86);
  let start=-Math.PI/2;
  Object.entries(planos).forEach(([p,n])=>{
    const slice=(n/total)*Math.PI*2;
    ctx.beginPath();ctx.moveTo(43,43);ctx.arc(43,43,38,start,start+slice);
    ctx.fillStyle=pColors[p];ctx.fill();
    start+=slice;
  });
  // inner circle
  ctx.beginPath();ctx.arc(43,43,24,0,Math.PI*2);
  ctx.fillStyle='#111620';ctx.fill();
  // center text
  ctx.fillStyle='#8a94a8';ctx.font='500 9px IBM Plex Mono';ctx.textAlign='center';
  ctx.fillText(total,43,41);
  ctx.font='300 7px IBM Plex Sans';ctx.fillText('total',43,51);

  document.getElementById('donut-leg').innerHTML=Object.entries(planos).map(([p,n])=>
    `<div class="dleg-row"><div class="dleg-dot" style="background:${pColors[p]}"></div>${pNames[p]}<span class="dleg-val">${n}</span></div>`
  ).join('');

  // Sparkline
  const dias7=[],labels7=[];
  for(let i=6;i>=0;i--){
    const d=new Date();d.setDate(d.getDate()-i);
    const iso=d.toISOString().slice(0,10);
    dias7.push(allLogs.filter(l=>l.acao==='login'&&l.sucesso&&(l.momento||'').slice(0,10)===iso).length);
    labels7.push(d.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'}));
  }
  const sc=document.getElementById('spark-canvas');
  sc.width=sc.parentElement.clientWidth||280;sc.height=60;
  const sx=sc.getContext('2d');
  const maxS=Math.max(...dias7,1),w=sc.width,step=w/(dias7.length-1);
  // gradient area
  const grad=sx.createLinearGradient(0,0,0,60);
  grad.addColorStop(0,'rgba(0,200,212,.18)');grad.addColorStop(1,'rgba(0,200,212,0)');
  sx.beginPath();sx.moveTo(0,60-(dias7[0]/maxS)*50);
  dias7.forEach((v,i)=>{if(i>0)sx.lineTo(i*step,60-(v/maxS)*50)});
  sx.lineTo(w,60);sx.lineTo(0,60);sx.fillStyle=grad;sx.fill();
  // line
  sx.beginPath();sx.moveTo(0,60-(dias7[0]/maxS)*50);
  dias7.forEach((v,i)=>{if(i>0)sx.lineTo(i*step,60-(v/maxS)*50)});
  sx.strokeStyle='var(--cyan)';sx.lineWidth=1.5;sx.stroke();
  // dots
  dias7.forEach((v,i)=>{
    sx.beginPath();sx.arc(i*step,60-(v/maxS)*50,2.5,0,Math.PI*2);
    sx.fillStyle='var(--cyan)';sx.fill();
  });
  document.getElementById('spark-labels').innerHTML=labels7.map(l=>'<span>'+l+'</span>').join('');
}

/* ── EXPORT TXT ── */
document.getElementById('btn-rel').onclick=()=>{
  if(!allU.length){toast('Sem dados','warn');return}
  const now=new Date().toLocaleString('pt-BR');
  const atv=allU.filter(u=>u.ativo&&!isExp(u.expira)).length;
  let t='LUCS TECH — RELATÓRIO DE LICENÇAS\nGerado: '+now+'\n'+'─'.repeat(56)+'\n\nRESUMO\n  Total     : '+allU.length+'\n  Ativos    : '+atv+'\n  Bloqueados: '+allU.filter(u=>!u.ativo).length+'\n  Vencidos  : '+allU.filter(u=>isExp(u.expira)).length+'\n\n'+'─'.repeat(56)+'\n\n';
  allU.forEach((u,i)=>{
    t+=String(i+1).padStart(3,'0')+'. '+u.nome+' ['+((u.plano||'basic').toUpperCase())+']\n';
    if(u.empresa)t+='     Empresa   : '+u.empresa+'\n';
    if(u.email)  t+='     E-mail    : '+u.email+'\n';
    t+='     Chave     : '+u.chave+'\n     Status    : '+(u.ativo?'ATIVO':'BLOQUEADO')+'\n     Vencimento: '+(u.expira?fDate(u.expira):'Sem limite')+'\n     Últ.acesso: '+(u.ultimo_acesso?fDT(u.ultimo_acesso):'Nunca')+'\n';
    if(u.obs)t+='     Obs       : '+u.obs+'\n';
    t+='\n';
  });
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{type:'text/plain;charset=utf-8'}));
  a.download='lucs-'+Date.now()+'.txt';a.click();
  toast('Relatório exportado');
};

/* ── EXPORT LOGS CSV ── */
document.getElementById('btn-exp-logs').onclick=()=>{
  if(!allLogs.length){toast('Sem logs','warn');return}
  let t='DATA/HORA;AÇÃO;NOME;EMPRESA;CHAVE;IP;SUCESSO\n';
  allLogs.forEach(l=>{t+=`${l.momento||''};${l.acao||''};${l.nome||''};${l.empresa||''};${l.chave||''};${l.ip||''};${l.sucesso?'SIM':'NÃO'}\n`});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([t],{type:'text/csv;charset=utf-8'}));
  a.download='lucs-logs-'+Date.now()+'.csv';a.click();
  toast('Logs exportados');
};

/* ── LIMPAR LOGS ── */
document.getElementById('btn-limpar').onclick=async()=>{
  if(!confirm('Limpar todos os logs de login?'))return;
  try{await fetch('/admin/limpar-logs',{method:'POST'});toast('Logs limpos','inf');load()}
  catch{toast('Erro','err')}
};

/* ── START ── */
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
