from flask import Flask, request, jsonify, render_template_string, send_file, redirect, make_response
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
import os
import random
import string
import csv
import io

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def row_to_dict(row):
    d = dict(row)
    for k, v in d.items():
        if v is None or isinstance(v, (str, float, bool)):
            pass
        elif isinstance(v, int):
            if k == 'ativo':
                d[k] = bool(v)
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
                id            SERIAL PRIMARY KEY,
                nome          TEXT NOT NULL,
                email         TEXT,
                empresa       TEXT,
                chave         TEXT UNIQUE NOT NULL,
                ativo         BOOLEAN DEFAULT TRUE,
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

        migracoes = [
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS empresa TEXT",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS expira DATE",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_acesso TIMESTAMP",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS nome TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS empresa TEXT",
            "ALTER TABLE logs ADD COLUMN IF NOT EXISTS acao TEXT",
        ]
        for sql in migracoes:
            try:
                cur.execute(sql)
                conn.commit()
            except Exception:
                conn.rollback()

        try:
            cur.execute("""
                SELECT data_type FROM information_schema.columns
                WHERE table_name = 'usuarios' AND column_name = 'ativo'
            """)
            row = cur.fetchone()
            if row is None:
                cur.execute("ALTER TABLE usuarios ADD COLUMN ativo BOOLEAN DEFAULT TRUE")
                conn.commit()
            elif row['data_type'] in ('integer', 'smallint', 'bigint'):
                cur.execute("ALTER TABLE usuarios ALTER COLUMN ativo TYPE BOOLEAN USING ativo::boolean")
                conn.commit()
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
#  HTML — PAINEL REDESENHADO
# ══════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lucs Tech — Painel</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet"/>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:      #04080f;
  --surf:    #080f1a;
  --card:    #0b1520;
  --card2:   #0e1b2b;
  --bord:    rgba(56,189,248,.1);
  --bord2:   rgba(56,189,248,.2);
  --c1:      #f97316;
  --c2:      #38bdf8;
  --c3:      #818cf8;
  --text:    #e2f0fb;
  --muted:   #4a7a99;
  --green:   #34d399;
  --red:     #f87171;
  --gold:    #fbbf24;
  --shadow:  0 8px 32px rgba(0,0,0,.5);
  --radius:  14px;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Syne', sans-serif;
  min-height: 100vh;
  overflow-x: hidden;
}

/* ── GRID BG ── */
body::before {
  content: '';
  position: fixed; inset: 0;
  background-image:
    linear-gradient(rgba(56,189,248,.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(56,189,248,.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
}
body::after {
  content: '';
  position: fixed;
  top: -200px; left: 50%;
  transform: translateX(-50%);
  width: 800px; height: 400px;
  background: radial-gradient(ellipse, rgba(249,115,22,.08) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.wrap { max-width: 1280px; margin: 0 auto; padding: 24px 20px; position: relative; z-index: 1; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(56,189,248,.2); border-radius: 4px; }

/* ── HEADER ── */
.hdr {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 24px;
  background: rgba(8,15,26,.8);
  border: 1px solid var(--bord);
  border-radius: var(--radius);
  margin-bottom: 20px;
  backdrop-filter: blur(20px);
  box-shadow: var(--shadow), inset 0 1px 0 rgba(255,255,255,.04);
}
.logo-wrap { display: flex; align-items: center; gap: 14px; }
.logo-icon {
  width: 38px; height: 38px;
  background: linear-gradient(135deg, var(--c1), #ea580c);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  box-shadow: 0 0 20px rgba(249,115,22,.4);
}
.logo {
  font-family: 'Space Mono', monospace;
  font-size: 15px; font-weight: 700; letter-spacing: 3px;
  color: var(--text);
}
.logo span { color: var(--c1); }
.hdr-right { display: flex; align-items: center; gap: 12px; }
.mode-tabs { display: flex; gap: 6px; }
.tab {
  padding: 7px 16px; border-radius: 8px;
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  cursor: pointer; text-decoration: none; transition: all .2s;
  border: 1px solid var(--bord); color: var(--muted); background: transparent;
  font-family: 'Space Mono', monospace;
}
.tab.active { background: rgba(249,115,22,.12); border-color: rgba(249,115,22,.4); color: var(--c1); }
.tab:hover:not(.active) { border-color: var(--bord2); color: var(--c2); }

/* ── STATS ── */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.stat {
  background: var(--card);
  border: 1px solid var(--bord);
  border-radius: var(--radius);
  padding: 22px 20px;
  position: relative; overflow: hidden;
  transition: transform .2s, border-color .2s, box-shadow .2s;
  box-shadow: var(--shadow);
  animation: fadeup .35s ease both;
}
.stat:hover { transform: translateY(-3px); border-color: var(--bord2); box-shadow: var(--shadow), 0 0 30px rgba(56,189,248,.05); }
.stat-accent {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  border-radius: 14px 14px 0 0;
}
.stat:nth-child(1) .stat-accent { background: linear-gradient(90deg, var(--c2), var(--c3)); }
.stat:nth-child(2) .stat-accent { background: linear-gradient(90deg, var(--green), #059669); }
.stat:nth-child(3) .stat-accent { background: linear-gradient(90deg, var(--red), #dc2626); }
.stat:nth-child(4) .stat-accent { background: linear-gradient(90deg, var(--gold), #d97706); }
.stat-icon { font-size: 22px; margin-bottom: 10px; display: block; }
.stat-n {
  font-family: 'Space Mono', monospace; font-size: 36px; font-weight: 700;
  color: var(--text); display: block; line-height: 1; letter-spacing: -1px;
}
.stat-n.blue  { color: var(--c2); }
.stat-n.green { color: var(--green); }
.stat-n.red   { color: var(--red); }
.stat-n.gold  { color: var(--gold); }
.stat-l { font-size: 9px; color: var(--muted); letter-spacing: 3px; margin-top: 6px; display: block; font-weight: 600; }

/* ── CARD ── */
.card {
  background: var(--card);
  border: 1px solid var(--bord);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 18px;
  box-shadow: var(--shadow);
  animation: fadeup .35s ease both;
  position: relative; overflow: hidden;
}
.card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(56,189,248,.1), transparent);
}
.card-title {
  font-family: 'Space Mono', monospace;
  font-size: 9px; letter-spacing: 4px; color: var(--muted);
  margin-bottom: 20px; display: flex; align-items: center; gap: 10px;
}
.card-title::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--bord), transparent);
}
.card-head {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
}

/* ── FORM ── */
.form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 90px auto; gap: 12px; align-items: end; }
.field { display: flex; flex-direction: column; gap: 7px; }
.field label {
  font-size: 9px; letter-spacing: 2.5px; color: var(--muted);
  font-weight: 700; font-family: 'Space Mono', monospace;
}
input[type=text], input[type=email], input[type=number], select {
  background: rgba(0,0,0,.4);
  border: 1px solid var(--bord);
  padding: 11px 14px; border-radius: 10px; color: var(--text);
  font-family: 'Syne', sans-serif; font-size: 14px;
  outline: none; transition: border-color .2s, box-shadow .2s, background .2s;
  width: 100%;
}
input:focus, select:focus {
  border-color: rgba(249,115,22,.5);
  box-shadow: 0 0 0 3px rgba(249,115,22,.08);
  background: rgba(0,0,0,.6);
}
select option { background: #0b1520; }

/* ── BOTÕES ── */
.btn-primary {
  background: linear-gradient(135deg, var(--c1), #ea580c);
  color: #fff; border: none; border-radius: 10px;
  font-family: 'Space Mono', monospace; font-size: 10px; font-weight: 700; letter-spacing: 1px;
  padding: 12px 20px; cursor: pointer; white-space: nowrap;
  transition: opacity .2s, transform .1s, box-shadow .2s;
  box-shadow: 0 4px 20px rgba(249,115,22,.3);
  display: inline-flex; align-items: center; gap: 8px;
}
.btn-primary:hover { opacity: .9; box-shadow: 0 4px 30px rgba(249,115,22,.5); }
.btn-primary:active { transform: scale(.97); }

.btn-ghost {
  background: transparent;
  color: var(--muted); border: 1px solid var(--bord); border-radius: 10px;
  font-family: 'Space Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 1px;
  padding: 10px 16px; cursor: pointer; transition: all .2s;
  display: inline-flex; align-items: center; gap: 7px;
  white-space: nowrap;
}
.btn-ghost:hover { border-color: var(--bord2); color: var(--c2); background: rgba(56,189,248,.05); }

.btn-danger {
  background: rgba(248,113,113,.08); color: var(--red);
  border: 1px solid rgba(248,113,113,.2); border-radius: 10px;
  font-family: 'Space Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 1px;
  padding: 10px 16px; cursor: pointer; transition: all .2s;
  display: inline-flex; align-items: center; gap: 7px;
}
.btn-danger:hover { background: rgba(248,113,113,.15); border-color: rgba(248,113,113,.35); }

.btn-export {
  background: rgba(129,140,248,.08); color: var(--c3);
  border: 1px solid rgba(129,140,248,.2); border-radius: 10px;
  font-family: 'Space Mono', monospace; font-size: 9px; font-weight: 700; letter-spacing: 1px;
  padding: 10px 16px; cursor: pointer; transition: all .2s;
  display: inline-flex; align-items: center; gap: 7px;
  text-decoration: none;
}
.btn-export:hover { background: rgba(129,140,248,.15); border-color: rgba(129,140,248,.35); }

.hdr-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

/* ── SEARCH ── */
.search-bar {
  position: relative; margin-bottom: 18px;
}
.search-bar input {
  padding-left: 40px;
  background: rgba(0,0,0,.5);
}
.search-icon {
  position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
  color: var(--muted); font-size: 14px; pointer-events: none;
}

/* ── FILTERS ── */
.filters { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-btn {
  padding: 5px 14px; border-radius: 20px;
  font-size: 9px; font-weight: 700; letter-spacing: 2px;
  cursor: pointer; border: 1px solid var(--bord);
  color: var(--muted); background: transparent;
  font-family: 'Space Mono', monospace;
  transition: all .2s;
}
.filter-btn.active { background: rgba(56,189,248,.1); border-color: rgba(56,189,248,.3); color: var(--c2); }
.filter-btn:hover:not(.active) { border-color: var(--bord2); color: var(--text); }

/* ── TABELA ── */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th {
  color: var(--muted); font-size: 9px; letter-spacing: 2.5px; font-weight: 700;
  padding: 10px 14px; border-bottom: 1px solid var(--bord); text-align: left;
  font-family: 'Space Mono', monospace; white-space: nowrap;
}
td { padding: 13px 14px; border-bottom: 1px solid rgba(255,255,255,.03); vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tbody tr { transition: background .15s; }
tbody tr:hover td { background: rgba(56,189,248,.025); }

.nome-cell b { font-size: 14px; font-weight: 700; }
.nome-cell small { color: var(--muted); font-size: 11px; display: block; margin-top: 2px; }

.empresa-tag {
  display: inline-block;
  background: rgba(129,140,248,.1); color: var(--c3);
  border: 1px solid rgba(129,140,248,.2); border-radius: 6px;
  padding: 3px 10px; font-size: 11px; font-weight: 600;
  max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.chave-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(251,191,36,.06); color: var(--gold);
  border: 1px solid rgba(251,191,36,.18); border-radius: 8px;
  padding: 5px 11px; cursor: pointer;
  font-family: 'Space Mono', monospace; font-size: 10px; letter-spacing: 1px;
  transition: background .2s, transform .1s;
}
.chave-badge:hover { background: rgba(251,191,36,.12); }
.chave-badge:active { transform: scale(.97); }
.copy-icon { font-size: 11px; opacity: .5; }

.expira-cell { font-size: 13px; }
.expira-cell.expired { color: var(--red); }
.expira-cell.warning { color: var(--gold); }
.expira-cell.ok { color: var(--muted); }

.status-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 13px; border-radius: 20px;
  font-size: 9px; font-weight: 700; letter-spacing: 1.5px;
  border: none; cursor: pointer; transition: all .2s;
  font-family: 'Space Mono', monospace;
}
.status-btn.on  { background: rgba(52,211,153,.1); color: var(--green); border: 1px solid rgba(52,211,153,.2); }
.status-btn.off { background: rgba(248,113,113,.1); color: var(--red);   border: 1px solid rgba(248,113,113,.2); }
.status-btn.on:hover  { background: rgba(52,211,153,.18); transform: scale(1.03); }
.status-btn.off:hover { background: rgba(248,113,113,.18); transform: scale(1.03); }

.pulse { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.pulse.on  { background: var(--green); box-shadow: 0 0 0 0 rgba(52,211,153,.5); animation: pulse-green 2s infinite; }
.pulse.off { background: var(--red); }

@keyframes pulse-green {
  0%   { box-shadow: 0 0 0 0 rgba(52,211,153,.5); }
  70%  { box-shadow: 0 0 0 5px rgba(52,211,153,0); }
  100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
}

.action-cell { display: flex; gap: 6px; justify-content: flex-end; }
.del-btn {
  background: rgba(248,113,113,.07); border: 1px solid rgba(248,113,113,.15);
  color: var(--red); cursor: pointer; font-size: 13px;
  opacity: .5; transition: opacity .2s, background .2s;
  border-radius: 8px; padding: 6px 8px; line-height: 1;
}
.del-btn:hover { opacity: 1; background: rgba(248,113,113,.15); }

/* ── LAST ACCESS ── */
.last-access { font-size: 12px; color: var(--muted); }
.last-access.recent { color: var(--green); }

/* ── LOGS ── */
.log-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.log-box {
  background: rgba(0,0,0,.6); border-radius: 10px; padding: 16px;
  max-height: 220px; overflow-y: auto;
  font-family: 'Space Mono', monospace; font-size: 11px; line-height: 2;
  color: var(--muted); border: 1px solid rgba(255,255,255,.04);
}
.log-row { display: flex; gap: 10px; align-items: baseline; }
.log-time { color: rgba(74,122,153,.6); font-size: 10px; flex-shrink: 0; }
.log-box .ok   { color: var(--green); }
.log-box .fail { color: var(--red); }
.log-box .info { color: var(--c1); }
.log-box .sys  { color: var(--c3); }

/* ── TOAST ── */
.toast {
  position: fixed; bottom: 28px; right: 28px;
  background: var(--card2); border: 1px solid var(--bord2); color: var(--text);
  padding: 13px 22px 13px 16px; border-radius: 12px;
  font-family: 'Space Mono', monospace; font-size: 11px;
  opacity: 0; transform: translateY(12px) scale(.97);
  transition: all .3s cubic-bezier(.34,1.56,.64,1);
  pointer-events: none; z-index: 9999;
  display: flex; align-items: center; gap: 10px;
  box-shadow: var(--shadow), 0 0 0 1px rgba(255,255,255,.04);
  max-width: 340px;
}
.toast.show { opacity: 1; transform: translateY(0) scale(1); }
.toast-icon { font-size: 16px; flex-shrink: 0; }

/* ── BADGE CONTADOR ── */
.count-badge {
  background: rgba(56,189,248,.1); color: var(--c2);
  border-radius: 20px; padding: 2px 10px; font-size: 11px;
  font-family: 'Space Mono', monospace; letter-spacing: 1px;
}

/* ── EMPTY ── */
.empty { text-align: center; padding: 50px; color: var(--muted); font-size: 13px; }
.empty-icon { font-size: 32px; display: block; margin-bottom: 12px; opacity: .4; }

/* ── SKELETON ── */
.skeleton {
  background: linear-gradient(90deg, var(--card) 25%, var(--card2) 50%, var(--card) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px; height: 14px;
}
@keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }

/* ── ANIMAÇÕES ── */
@keyframes fadeup {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: none; }
}
.stats .stat:nth-child(1) { animation-delay: .05s; }
.stats .stat:nth-child(2) { animation-delay: .10s; }
.stats .stat:nth-child(3) { animation-delay: .15s; }
.stats .stat:nth-child(4) { animation-delay: .20s; }

/* ── DM THEME ── */
body.dm {
  --c1:   #a78bfa;
  --c2:   #7c3aed;
  --bord: rgba(167,139,250,.1);
  --bord2: rgba(167,139,250,.22);
}
body.dm::after {
  background: radial-gradient(ellipse, rgba(124,58,237,.1) 0%, transparent 70%);
}
body.dm .stat:nth-child(1) .stat-accent { background: linear-gradient(90deg, var(--c1), #7c3aed); }
body.dm .btn-primary { background: linear-gradient(135deg, #a78bfa, #7c3aed); box-shadow: 0 4px 20px rgba(167,139,250,.3); }
body.dm .btn-primary:hover { box-shadow: 0 4px 30px rgba(167,139,250,.5); }
body.dm .chave-badge { background: rgba(167,139,250,.08); color: var(--c1); border-color: rgba(167,139,250,.2); }
body.dm .empresa-tag { background: rgba(167,139,250,.1); color: var(--c1); border-color: rgba(167,139,250,.2); }

@media (max-width: 900px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .form-grid { grid-template-columns: 1fr 1fr; }
  .hdr-actions { gap: 6px; }
}
@media (max-width: 600px) {
  .stats { grid-template-columns: 1fr 1fr; }
  .form-grid { grid-template-columns: 1fr; }
  .hdr { flex-wrap: wrap; gap: 12px; }
}
</style>
</head>
<body id="body">
<div class="wrap">

  <!-- HEADER -->
  <div class="hdr">
    <div class="logo-wrap">
      <div class="logo-icon">⚡</div>
      <div>
        <div class="logo"><span>LUCS</span> TECH</div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px;letter-spacing:2px">SISTEMA DE LICENÇAS</div>
      </div>
    </div>
    <div class="hdr-right">
      <div class="mode-tabs">
        <a href="/app" class="tab" id="tab-app">APP</a>
        <a href="/dm"  class="tab" id="tab-dm">DM</a>
      </div>
    </div>
  </div>

  <!-- STATS -->
  <div class="stats">
    <div class="stat">
      <div class="stat-accent"></div>
      <span class="stat-icon">🏢</span>
      <span class="stat-n blue" id="s-total">—</span>
      <span class="stat-l">TOTAL DE CLIENTES</span>
    </div>
    <div class="stat">
      <div class="stat-accent"></div>
      <span class="stat-icon">✅</span>
      <span class="stat-n green" id="s-ativos">—</span>
      <span class="stat-l">LICENÇAS ATIVAS</span>
    </div>
    <div class="stat">
      <div class="stat-accent"></div>
      <span class="stat-icon">🔒</span>
      <span class="stat-n red" id="s-bloq">—</span>
      <span class="stat-l">BLOQUEADOS</span>
    </div>
    <div class="stat">
      <div class="stat-accent"></div>
      <span class="stat-icon">📊</span>
      <span class="stat-n gold" id="s-hoje">—</span>
      <span class="stat-l">LOGINS HOJE</span>
    </div>
  </div>

  <!-- GERAR -->
  <div class="card">
    <div class="card-title">NOVA LICENÇA</div>
    <div class="form-grid">
      <div class="field">
        <label>NOME DO CLIENTE</label>
        <input type="text" id="inp-nome" placeholder="Ex: João Silva"/>
      </div>
      <div class="field">
        <label>EMPRESA</label>
        <input type="text" id="inp-empresa" placeholder="Ex: Empresa LTDA"/>
      </div>
      <div class="field">
        <label>E-MAIL</label>
        <input type="email" id="inp-email" placeholder="cliente@email.com"/>
      </div>
      <div class="field">
        <label>DIAS</label>
        <input type="number" id="inp-dias" value="30" min="1"/>
      </div>
      <button class="btn-primary" id="btn-gerar">
        <span>⚡</span> GERAR
      </button>
    </div>
  </div>

  <!-- TABELA -->
  <div class="card">
    <div class="card-head">
      <div style="display:flex;align-items:center;gap:12px">
        <div class="card-title" style="margin:0">CLIENTES</div>
        <span class="count-badge" id="count-badge">0</span>
      </div>
      <div class="hdr-actions">
        <a href="/admin/exportar-csv" class="btn-export" id="btn-csv" download>
          <span>📥</span> CSV
        </a>
        <button class="btn-ghost" id="btn-exportar-pdf">
          <span>📄</span> RELATÓRIO
        </button>
        <button class="btn-danger" id="btn-bloquear-todos">
          <span>🔒</span> BLOQUEAR TODOS
        </button>
      </div>
    </div>

    <!-- SEARCH + FILTERS -->
    <div class="search-bar">
      <span class="search-icon">🔍</span>
      <input type="text" id="inp-busca" placeholder="Buscar por nome, empresa, chave ou e-mail..."/>
    </div>
    <div class="filters">
      <button class="filter-btn active" data-f="todos">TODOS</button>
      <button class="filter-btn" data-f="ativo">ATIVOS</button>
      <button class="filter-btn" data-f="bloqueado">BLOQUEADOS</button>
      <button class="filter-btn" data-f="vencido">VENCIDOS</button>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>CLIENTE</th>
            <th>EMPRESA</th>
            <th>CHAVE</th>
            <th>VENCIMENTO</th>
            <th>ÚLTIMO ACESSO</th>
            <th>STATUS</th>
            <th style="text-align:right">AÇÕES</th>
          </tr>
        </thead>
        <tbody id="tabela">
          <tr><td colspan="7" class="empty"><span class="empty-icon">⏳</span>Carregando...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- LOGS -->
  <div class="card">
    <div class="log-header">
      <div class="card-title" style="margin:0">LOG DE ATIVIDADE</div>
      <button class="btn-ghost" id="btn-limpar-logs" style="font-size:9px">🗑 LIMPAR LOGS</button>
    </div>
    <div class="log-box" id="logs">Carregando...</div>
  </div>

</div>
<div class="toast" id="toast"><span class="toast-icon" id="toast-icon"></span><span id="toast-msg"></span></div>

<script>
const MODO = document.body.dataset.modo || 'app';
if (MODO === 'dm') document.getElementById('body').classList.add('dm');
document.getElementById('tab-' + MODO).classList.add('active');

let todosUsuarios = [];
let filtroAtual   = 'todos';
let buscaAtual    = '';

// ── TOAST ──────────────────────────────────────────────
function toast(msg, tipo = 'ok', dur = 2800) {
  const icons = { ok: '✓', err: '✗', warn: '⚠', info: '◆' };
  document.getElementById('toast-icon').textContent = icons[tipo] || '◆';
  document.getElementById('toast-msg').textContent  = msg;
  const el = document.getElementById('toast');
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), dur);
}

// ── FORMATAÇÃO ─────────────────────────────────────────
function fData(s) {
  if (!s) return '<span style="color:var(--muted)">Sem limite</span>';
  return new Date(s + 'T00:00:00').toLocaleDateString('pt-BR');
}
function fDT(s) {
  if (!s) return '<span style="color:var(--muted)">Nunca</span>';
  const d = new Date(s);
  const ago = Date.now() - d.getTime();
  const hrs = ago / 3600000;
  if (hrs < 1) return '<span class="last-access recent">Agora há pouco</span>';
  if (hrs < 24) return `<span class="last-access recent">${Math.floor(hrs)}h atrás</span>`;
  return `<span class="last-access">${d.toLocaleString('pt-BR')}</span>`;
}

function expiraClass(s) {
  if (!s) return 'ok';
  const d = new Date(s + 'T00:00:00');
  const now = new Date(); now.setHours(0,0,0,0);
  const diff = (d - now) / 86400000;
  if (diff < 0)  return 'expired';
  if (diff <= 7) return 'warning';
  return 'ok';
}

function isVencido(s) {
  return s && new Date(s + 'T00:00:00') < new Date(new Date().toDateString());
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── CARREGAR ────────────────────────────────────────────
async function carregar() {
  try {
    const res = await fetch('/admin/dados');
    if (!res.ok) throw new Error();
    const d = await res.json();
    if (!d.usuarios) return;
    todosUsuarios = d.usuarios;

    document.getElementById('s-total').textContent  = d.usuarios.length;
    document.getElementById('s-ativos').textContent = d.usuarios.filter(u => u.ativo).length;
    document.getElementById('s-bloq').textContent   = d.usuarios.filter(u => !u.ativo).length;
    document.getElementById('s-hoje').textContent   = d.logs_hoje;

    renderTabela();

    // logs
    const logBox = document.getElementById('logs');
    if (d.logs.length === 0) {
      logBox.innerHTML = '<span style="color:var(--muted)">Nenhuma atividade ainda.</span>';
    } else {
      logBox.innerHTML = d.logs.map(l => {
        let cls, icon, label;
        if (l.acao === 'login') {
          cls = l.sucesso ? 'ok' : 'fail';
          icon = l.sucesso ? '✓' : '✗';
          label = l.sucesso ? 'LOGIN OK' : 'LOGIN NEGADO';
        } else if (l.acao === 'bloqueio_geral') {
          cls = 'sys'; icon = '⚡'; label = 'BLOQUEIO GERAL';
        } else {
          cls = 'info'; icon = '◆';
          label = (l.acao || 'AÇÃO').toUpperCase();
        }
        const nome    = l.nome    ? ` <b>${esc(l.nome)}</b>` : '';
        const empresa = l.empresa ? ` [${esc(l.empresa)}]` : '';
        return `<div class="log-row"><span class="log-time">${fDTshort(l.momento)}</span><span class="${cls}">${icon} ${label}</span>${nome}${empresa} — <span style="opacity:.5">${esc(l.chave||'')}</span></div>`;
      }).join('');
      logBox.scrollTop = 0;
    }
  } catch(e) { console.error(e); }
}

function fDTshort(s) {
  if (!s) return '';
  return new Date(s).toLocaleString('pt-BR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' });
}

// ── RENDER TABELA ────────────────────────────────────────
function renderTabela() {
  let lista = todosUsuarios.filter(u => {
    if (filtroAtual === 'ativo')     return u.ativo && !isVencido(u.expira);
    if (filtroAtual === 'bloqueado') return !u.ativo;
    if (filtroAtual === 'vencido')   return isVencido(u.expira);
    return true;
  });

  if (buscaAtual) {
    const q = buscaAtual.toLowerCase();
    lista = lista.filter(u =>
      (u.nome    || '').toLowerCase().includes(q) ||
      (u.empresa || '').toLowerCase().includes(q) ||
      (u.email   || '').toLowerCase().includes(q) ||
      (u.chave   || '').toLowerCase().includes(q)
    );
  }

  document.getElementById('count-badge').textContent = lista.length;

  const tbody = document.getElementById('tabela');
  if (lista.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty"><span class="empty-icon">🔍</span>Nenhum resultado encontrado.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(u => {
    const ec  = expiraClass(u.expira);
    const exp = u.expira
      ? `<span class="expira-cell ${ec}">${fData(u.expira)}${ec==='warning'?' ⚠':''}${ec==='expired'?' ✗':''}</span>`
      : `<span class="expira-cell ok">Sem limite</span>`;

    return `
      <tr>
        <td class="nome-cell">
          <b>${esc(u.nome)}</b>
          <small>${esc(u.email || '')}</small>
        </td>
        <td>
          ${u.empresa ? `<span class="empresa-tag" title="${esc(u.empresa)}">${esc(u.empresa)}</span>` : '<span style="color:var(--muted)">—</span>'}
        </td>
        <td>
          <span class="chave-badge" data-chave="${esc(u.chave)}">
            ${esc(u.chave)} <span class="copy-icon">⧉</span>
          </span>
        </td>
        <td>${exp}</td>
        <td>${fDT(u.ultimo_acesso)}</td>
        <td>
          <button class="status-btn ${u.ativo ? 'on' : 'off'}" data-chave="${esc(u.chave)}">
            <span class="pulse ${u.ativo ? 'on' : 'off'}"></span>
            ${u.ativo ? 'ATIVO' : 'BLOQUEADO'}
          </button>
        </td>
        <td>
          <div class="action-cell">
            <button class="del-btn" data-chave="${esc(u.chave)}" title="Remover">✕</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // eventos
  tbody.querySelectorAll('.chave-badge').forEach(el =>
    el.onclick = () => { navigator.clipboard.writeText(el.dataset.chave); toast('Chave copiada!', 'ok'); }
  );
  tbody.querySelectorAll('.status-btn').forEach(el =>
    el.onclick = () => toggleStatus(el.dataset.chave)
  );
  tbody.querySelectorAll('.del-btn').forEach(el =>
    el.onclick = () => remover(el.dataset.chave)
  );
}

// ── FILTROS E BUSCA ──────────────────────────────────────
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    filtroAtual = btn.dataset.f;
    renderTabela();
  };
});

document.getElementById('inp-busca').oninput = e => {
  buscaAtual = e.target.value.trim();
  renderTabela();
};

// ── GERAR ────────────────────────────────────────────────
document.getElementById('btn-gerar').onclick = async () => {
  const nome    = document.getElementById('inp-nome').value.trim();
  const empresa = document.getElementById('inp-empresa').value.trim();
  const email   = document.getElementById('inp-email').value.trim();
  const dias    = document.getElementById('inp-dias').value;
  if (!nome) { toast('Nome é obrigatório', 'warn'); return; }

  const btn = document.getElementById('btn-gerar');
  btn.disabled = true; btn.innerHTML = '<span>⏳</span> GERANDO...';

  try {
    const res  = await fetch('/admin/criar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, empresa, email, dias })
    });
    const data = await res.json();
    if (data.ok) {
      toast(`Chave gerada: ${data.chave}`, 'ok');
      document.getElementById('inp-nome').value    = '';
      document.getElementById('inp-empresa').value = '';
      document.getElementById('inp-email').value   = '';
      carregar();
    } else {
      toast(data.msg || 'Erro ao criar', 'err');
    }
  } catch(e) { toast('Erro de conexão', 'err'); }
  finally { btn.disabled = false; btn.innerHTML = '<span>⚡</span> GERAR'; }
};

// ── TOGGLE ────────────────────────────────────────────────
async function toggleStatus(chave) {
  try {
    const res  = await fetch('/admin/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chave })
    });
    const data = await res.json();
    if (data.ok) {
      toast(data.ativo ? 'Cliente ativado ✓' : 'Cliente bloqueado 🔒', data.ativo ? 'ok' : 'warn');
      carregar();
    } else { toast(data.msg || 'Erro', 'err'); }
  } catch(e) { toast('Erro de conexão', 'err'); }
}

// ── REMOVER ───────────────────────────────────────────────
async function remover(chave) {
  if (!confirm('Remover este cliente permanentemente?\n\nEssa ação não pode ser desfeita.')) return;
  try {
    const res  = await fetch('/admin/deletar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chave })
    });
    const data = await res.json();
    if (data.ok) { toast('Cliente removido', 'info'); carregar(); }
    else toast(data.msg || 'Erro', 'err');
  } catch(e) { toast('Erro de conexão', 'err'); }
}

// ── BLOQUEAR TODOS ────────────────────────────────────────
document.getElementById('btn-bloquear-todos').onclick = async () => {
  const ativos = todosUsuarios.filter(u => u.ativo).length;
  if (!ativos) { toast('Nenhum cliente ativo', 'warn'); return; }
  if (!confirm(`Bloquear TODOS os ${ativos} clientes ativos?`)) return;
  try {
    await fetch('/admin/bloquear-todos', { method: 'POST' });
    toast(`${ativos} clientes bloqueados 🔒`, 'warn');
    carregar();
  } catch(e) { toast('Erro', 'err'); }
};

// ── EXPORTAR RELATÓRIO TXT ────────────────────────────────
document.getElementById('btn-exportar-pdf').onclick = () => {
  const lista = todosUsuarios;
  if (!lista.length) { toast('Sem dados para exportar', 'warn'); return; }

  const now = new Date().toLocaleString('pt-BR');
  const ativos  = lista.filter(u => u.ativo).length;
  const bloq    = lista.filter(u => !u.ativo).length;

  let txt = `LUCS TECH — RELATÓRIO DE LICENÇAS\n`;
  txt += `Gerado em: ${now}\n`;
  txt += `${'═'.repeat(60)}\n\n`;
  txt += `RESUMO\n`;
  txt += `  Total de clientes : ${lista.length}\n`;
  txt += `  Licenças ativas   : ${ativos}\n`;
  txt += `  Bloqueados        : ${bloq}\n\n`;
  txt += `${'═'.repeat(60)}\n`;
  txt += `CLIENTES\n\n`;

  lista.forEach((u, i) => {
    txt += `${String(i+1).padStart(3,'0')}. ${u.nome}\n`;
    if (u.empresa) txt += `     Empresa    : ${u.empresa}\n`;
    if (u.email)   txt += `     E-mail     : ${u.email}\n`;
    txt += `     Chave      : ${u.chave}\n`;
    txt += `     Status     : ${u.ativo ? 'ATIVO' : 'BLOQUEADO'}\n`;
    txt += `     Vencimento : ${u.expira ? new Date(u.expira+'T00:00:00').toLocaleDateString('pt-BR') : 'Sem limite'}\n`;
    txt += `     Últ.acesso : ${u.ultimo_acesso ? new Date(u.ultimo_acesso).toLocaleString('pt-BR') : 'Nunca'}\n\n`;
  });

  const blob = new Blob([txt], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `lucs-relatorio-${Date.now()}.txt`;
  a.click(); URL.revokeObjectURL(url);
  toast('Relatório exportado ✓', 'ok');
};

// ── LIMPAR LOGS ───────────────────────────────────────────
document.getElementById('btn-limpar-logs').onclick = async () => {
  if (!confirm('Limpar todos os logs de atividade?')) return;
  try {
    await fetch('/admin/limpar-logs', { method: 'POST' });
    toast('Logs limpos', 'info');
    carregar();
  } catch(e) { toast('Erro', 'err'); }
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
#  API — VALIDAR CHAVE
# ══════════════════════════════════════════
@app.route("/api/validar", methods=["POST"])
def validar():
    try:
        dados = request.json or {}
        chave = dados.get("chave", "").strip()
        conn  = get_db(); cur = conn.cursor()

        cur.execute("SELECT id, nome, empresa, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
        user = cur.fetchone()

        sucesso  = 0
        nome_user    = ""
        empresa_user = ""

        if user:
            nome_user    = user['nome']
            empresa_user = user['empresa'] or ""
            exp = user['expira']
            if isinstance(exp, str):
                try: exp = date.fromisoformat(exp)
                except: exp = None
            vencido = exp and exp < datetime.now().date()
            if user['ativo'] and not vencido:
                sucesso = 1
                cur.execute("UPDATE usuarios SET ultimo_acesso = %s WHERE chave = %s", (datetime.now(), chave))

        cur.execute(
            "INSERT INTO logs (nome, empresa, chave, acao, sucesso, momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (nome_user or None, empresa_user or None, chave, 'login', sucesso, datetime.now())
        )
        conn.commit(); cur.close(); conn.close()

        if sucesso:
            return jsonify({"ok": True, "nome": nome_user, "empresa": empresa_user})
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
            SELECT nome, email, empresa, chave, ativo, expira, ultimo_acesso
            FROM usuarios ORDER BY id DESC
        """)
        usuarios = [row_to_dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT nome, empresa, chave, acao, sucesso, momento
            FROM logs ORDER BY id DESC LIMIT 100
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
        d       = request.json or {}
        nome    = d.get('nome', '').strip()
        empresa = (d.get('empresa') or '').strip() or None
        email   = (d.get('email')   or '').strip() or None
        dias    = int(d.get('dias') or 30)

        if not nome:
            return jsonify({"ok": False, "msg": "Nome obrigatório"}), 400

        exp   = datetime.now().date() + timedelta(days=dias)
        chave = nova_chave()

        conn = get_db(); cur = conn.cursor()

        for _ in range(10):
            try:
                cur.execute(
                    "INSERT INTO usuarios (nome, empresa, email, chave, expira, ativo, criado_em) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING chave",
                    (nome, empresa, email, chave, exp, True, datetime.now())
                )
                chave = cur.fetchone()['chave']
                conn.commit()
                break
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                chave = nova_chave()

        cur.execute(
            "INSERT INTO logs (nome, empresa, chave, acao, sucesso, momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (nome, empresa, chave, 'criacao', 1, datetime.now())
        )
        conn.commit()
        cur.close(); conn.close()

        return jsonify({"ok": True, "chave": chave})

    except Exception as e:
        print(f"[admin_criar] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — ADMIN: TOGGLE  ← CORRIGIDO
# ══════════════════════════════════════════
@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    try:
        chave = (request.json or {}).get('chave', '')
        conn = get_db(); cur = conn.cursor()

        # Busca o estado atual primeiro
        cur.execute("SELECT nome, empresa, ativo FROM usuarios WHERE chave = %s", (chave,))
        row = cur.fetchone()

        if not row:
            cur.close(); conn.close()
            return jsonify({"ok": False, "msg": "Chave não encontrada"}), 404

        novo_estado = not row['ativo']

        # Atualiza explicitamente para o novo estado
        cur.execute(
            "UPDATE usuarios SET ativo = %s WHERE chave = %s",
            (novo_estado, chave)
        )
        conn.commit()

        acao = 'ativacao' if novo_estado else 'bloqueio'
        cur.execute(
            "INSERT INTO logs (nome, empresa, chave, acao, sucesso, momento) VALUES (%s,%s,%s,%s,%s,%s)",
            (row['nome'], row.get('empresa'), chave, acao, 1, datetime.now())
        )
        conn.commit()
        cur.close(); conn.close()

        return jsonify({"ok": True, "ativo": novo_estado})

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

        cur.execute("SELECT nome, empresa FROM usuarios WHERE chave = %s", (chave,))
        row = cur.fetchone()
        nome    = row['nome']    if row else None
        empresa = row['empresa'] if row else None

        cur.execute("DELETE FROM logs WHERE chave = %s AND acao = 'login'", (chave,))
        cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))

        if nome:
            cur.execute(
                "INSERT INTO logs (nome, empresa, chave, acao, sucesso, momento) VALUES (%s,%s,%s,%s,%s,%s)",
                (nome, empresa, chave, 'remocao', 1, datetime.now())
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
            "INSERT INTO logs (nome, chave, acao, sucesso, momento) VALUES (%s,%s,%s,%s,%s)",
            ('SISTEMA', 'TODOS', 'bloqueio_geral', 1, datetime.now())
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
        cur.execute("""
            SELECT nome, empresa, email, chave, ativo, expira, criado_em, ultimo_acesso
            FROM usuarios ORDER BY id DESC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()

        si = io.StringIO()
        writer = csv.writer(si, delimiter=';')
        writer.writerow(['Nome', 'Empresa', 'E-mail', 'Chave', 'Ativo', 'Vencimento', 'Criado em', 'Último acesso'])
        for r in rows:
            writer.writerow([
                r['nome'] or '',
                r['empresa'] or '',
                r['email'] or '',
                r['chave'] or '',
                'Sim' if r['ativo'] else 'Não',
                r['expira'].isoformat() if r['expira'] else '',
                r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else '',
                r['ultimo_acesso'].strftime('%d/%m/%Y %H:%M') if r['ultimo_acesso'] else '',
            ])

        output   = make_response(si.getvalue())
        filename = f"lucs-licencas-{datetime.now().strftime('%Y%m%d')}.csv"
        output.headers["Content-Disposition"] = f"attachment; filename={filename}"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output

    except Exception as e:
        print(f"[exportar_csv] {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

# ══════════════════════════════════════════
#  API — LIMPAR LOGS
# ══════════════════════════════════════════
@app.route("/admin/limpar-logs", methods=["POST"])
def limpar_logs():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM logs WHERE acao = 'login'")
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
