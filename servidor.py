from flask import Flask, request, jsonify, render_template_string, redirect
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import os
import random
import string

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def gerar_chave_automatica():
    caracteres = string.ascii_uppercase + string.digits
    p1 = ''.join(random.choices(caracteres, k=4))
    p2 = ''.join(random.choices(caracteres, k=4))
    p3 = ''.join(random.choices(caracteres, k=4))
    return f"LUCS-{p1}-{p2}-{p3}"

# ─────────────────────────────────────────────
#  PÁGINA APP (acesso via /app)
# ─────────────────────────────────────────────
APP_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>Lucs Tech — App</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;600&display=swap');
  :root{--bg:#03080f;--c1:#00ffe0;--c2:#0066ff;--card:rgba(5,15,30,0.95);--text:#ddf4ff;--muted:#4a7a99;--red:#ff2d55;--green:#00ffe0;--gold:#ffd700;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;
    background-image:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(0,100,255,0.15),transparent),
    repeating-linear-gradient(0deg,transparent,transparent 40px,rgba(0,210,255,0.02) 40px,rgba(0,210,255,0.02) 41px),
    repeating-linear-gradient(90deg,transparent,transparent 40px,rgba(0,210,255,0.02) 40px,rgba(0,210,255,0.02) 41px);}
  .wrap{max-width:1100px;margin:auto;padding:30px 20px;}
  /* HEADER */
  .hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:35px;padding-bottom:20px;border-bottom:1px solid rgba(0,255,224,0.1);}
  .logo{font-family:'Orbitron',monospace;font-size:22px;font-weight:900;letter-spacing:3px;
    background:linear-gradient(90deg,var(--c1),var(--c2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
  .badge-app{background:rgba(0,255,224,0.1);border:1px solid var(--c1);color:var(--c1);
    padding:5px 14px;border-radius:20px;font-size:11px;font-weight:600;letter-spacing:2px;}
  /* STATS */
  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px;}
  .sc{background:var(--card);border:1px solid rgba(0,255,224,0.08);border-radius:14px;padding:20px 15px;text-align:center;
    position:relative;overflow:hidden;transition:border-color .3s;}
  .sc:hover{border-color:rgba(0,255,224,0.3);}
  .sc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--c2),var(--c1));}
  .sc-num{font-family:'Orbitron',monospace;font-size:30px;font-weight:700;color:var(--c1);display:block;line-height:1;}
  .sc-lbl{font-size:10px;color:var(--muted);letter-spacing:2px;margin-top:6px;display:block;}
  .sc-num.red{color:var(--red);}
  .sc-num.gold{color:var(--gold);}
  /* PANEL */
  .panel{background:var(--card);border:1px solid rgba(0,255,224,0.1);border-radius:16px;padding:24px;margin-bottom:22px;}
  .panel-title{font-family:'Orbitron',monospace;font-size:11px;letter-spacing:3px;color:var(--c1);margin-bottom:18px;opacity:.7;}
  /* FORM */
  .form-row{display:grid;grid-template-columns:1fr 1fr 90px auto;gap:10px;align-items:end;}
  .field{display:flex;flex-direction:column;gap:6px;}
  .field label{font-size:10px;letter-spacing:2px;color:var(--muted);}
  input[type=text],input[type=email],input[type=number]{
    background:rgba(0,0,0,0.5);border:1px solid rgba(0,255,224,0.15);
    padding:11px 14px;border-radius:10px;color:#fff;font-family:'Rajdhani',sans-serif;
    font-size:14px;outline:none;transition:border-color .3s;width:100%;}
  input:focus{border-color:var(--c1);}
  .btn{background:linear-gradient(135deg,#0066ff,#00ffe0);color:#000;border:none;
    border-radius:10px;font-family:'Orbitron',monospace;font-size:11px;font-weight:700;
    letter-spacing:1px;padding:12px 20px;cursor:pointer;white-space:nowrap;
    transition:opacity .2s,transform .1s;}
  .btn:hover{opacity:.85;}
  .btn:active{transform:scale(.97);}
  /* TABLE */
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th{color:var(--muted);font-size:10px;letter-spacing:2px;padding:10px 12px;border-bottom:1px solid rgba(0,255,224,0.08);text-align:left;}
  td{padding:13px 12px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:middle;}
  tr:hover td{background:rgba(0,255,224,0.02);}
  .chave{color:var(--gold);background:rgba(255,215,0,0.07);padding:5px 10px;border-radius:6px;
    cursor:pointer;font-family:'Orbitron',monospace;font-size:11px;letter-spacing:1px;
    border:1px solid rgba(255,215,0,0.2);transition:background .2s;}
  .chave:hover{background:rgba(255,215,0,0.15);}
  .pill{padding:4px 12px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:1px;border:none;cursor:pointer;transition:all .2s;}
  .on{background:rgba(0,255,224,0.15);color:var(--green);border:1px solid rgba(0,255,224,0.3);}
  .on:hover{background:rgba(0,255,224,0.25);}
  .off{background:rgba(255,45,85,0.15);color:var(--red);border:1px solid rgba(255,45,85,0.3);}
  .off:hover{background:rgba(255,45,85,0.25);}
  .del-btn{background:none;border:none;color:var(--red);cursor:pointer;font-size:18px;opacity:.5;transition:opacity .2s;padding:0 4px;}
  .del-btn:hover{opacity:1;}
  /* BLOQUEAR TODOS */
  .btn-danger{background:rgba(255,45,85,0.15);color:var(--red);border:1px solid rgba(255,45,85,0.3);
    border-radius:8px;font-family:'Orbitron',monospace;font-size:10px;font-weight:700;letter-spacing:1px;
    padding:8px 16px;cursor:pointer;transition:all .2s;}
  .btn-danger:hover{background:rgba(255,45,85,0.3);}
  /* LOGS */
  .logs{background:rgba(0,0,0,0.6);border-radius:10px;padding:14px;max-height:180px;
    overflow-y:auto;font-family:'Courier New',monospace;font-size:11px;color:#558ba0;line-height:1.8;}
  .logs::-webkit-scrollbar{width:4px;}
  .logs::-webkit-scrollbar-thumb{background:rgba(0,255,224,0.2);border-radius:4px;}
  .log-ok{color:#00ffe0;}
  .log-fail{color:#ff2d55;}
  /* TOAST */
  .toast{position:fixed;bottom:25px;right:25px;background:rgba(0,255,224,0.1);border:1px solid var(--c1);
    color:var(--c1);padding:12px 20px;border-radius:10px;font-family:'Orbitron',monospace;font-size:12px;
    opacity:0;transform:translateY(10px);transition:all .3s;pointer-events:none;z-index:999;}
  .toast.show{opacity:1;transform:translateY(0);}
  .tbl-actions{display:flex;gap:8px;align-items:center;justify-content:flex-end;}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">⚡ LUCS TECH</div>
    <div style="display:flex;gap:12px;align-items:center;">
      <span class="badge-app">APP MODE</span>
      <a href="/dm" style="color:var(--muted);font-size:11px;letter-spacing:1px;text-decoration:none;
        border:1px solid rgba(255,255,255,0.1);padding:5px 12px;border-radius:20px;">DM MODE →</a>
    </div>
  </div>

  <div class="stats">
    <div class="sc"><span class="sc-num" id="s-total">—</span><span class="sc-lbl">TOTAL</span></div>
    <div class="sc"><span class="sc-num" id="s-ativos">—</span><span class="sc-lbl">ATIVOS</span></div>
    <div class="sc"><span class="sc-num red" id="s-bloq">—</span><span class="sc-lbl">BLOQUEADOS</span></div>
    <div class="sc"><span class="sc-num gold" id="s-hoje">—</span><span class="sc-lbl">LOGINS HOJE</span></div>
  </div>

  <div class="panel">
    <div class="panel-title">GERAR NOVO ACESSO</div>
    <div class="form-row">
      <div class="field"><label>NOME DO CLIENTE</label><input type="text" id="nome" placeholder="Ex: João Silva"></div>
      <div class="field"><label>E-MAIL</label><input type="email" id="email" placeholder="cliente@email.com"></div>
      <div class="field"><label>DIAS</label><input type="number" id="dias" value="30" min="1"></div>
      <button class="btn" onclick="criar()">⚡ GERAR CHAVE</button>
    </div>
  </div>

  <div class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
      <div class="panel-title" style="margin:0;">CLIENTES CADASTRADOS</div>
      <div style="display:flex;gap:10px;">
        <button class="btn-danger" onclick="bloquearTodos()">🔒 BLOQUEAR TODOS</button>
      </div>
    </div>
    <table>
      <thead><tr><th>CLIENTE</th><th>CHAVE</th><th>VENCIMENTO</th><th>STATUS</th><th style="text-align:right">AÇÕES</th></tr></thead>
      <tbody id="tabela"></tbody>
    </table>
  </div>

  <div class="panel">
    <div class="panel-title">HISTÓRICO DE ACESSOS</div>
    <div class="logs" id="logs">Carregando...</div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
function toast(msg){
  const t=document.getElementById('toast');
  t.innerText=msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2500);
}
async function carregar(){
  const res=await fetch('/admin/dados'); const d=await res.json();
  document.getElementById('s-total').innerText=d.usuarios.length;
  document.getElementById('s-ativos').innerText=d.usuarios.filter(u=>u.ativo).length;
  document.getElementById('s-bloq').innerText=d.usuarios.filter(u=>!u.ativo).length;
  document.getElementById('s-hoje').innerText=d.logs_hoje;
  document.getElementById('tabela').innerHTML=d.usuarios.map(u=>`
    <tr>
      <td><b>${u.nome}</b><br><small style="color:var(--muted);font-size:11px">${u.email||''}</small></td>
      <td><span class="chave" onclick="copiar('${u.chave}')" title="Clique para copiar">${u.chave}</span></td>
      <td style="color:var(--muted)">${u.expira?new Date(u.expira).toLocaleDateString('pt-BR'):'Sem limite'}</td>
      <td><button class="pill ${u.ativo?'on':'off'}" onclick="toggle('${u.chave}')">${u.ativo?'● ATIVO':'● BLOQUEADO'}</button></td>
      <td><div class="tbl-actions"><button class="del-btn" onclick="deletar('${u.chave}')" title="Remover">✕</button></div></td>
    </tr>
  `).join('');
  document.getElementById('logs').innerHTML=d.logs.map(l=>`
    <div>[${new Date(l.momento).toLocaleString('pt-BR')}]
      <span class="${l.sucesso?'log-ok':'log-fail'}">${l.sucesso?'✓ OK':'✗ NEGADO'}</span>
      — ${l.chave}
    </div>`).join('');
}
function copiar(c){navigator.clipboard.writeText(c);toast('✓ Chave copiada!');}
async function criar(){
  const nome=document.getElementById('nome').value.trim();
  const email=document.getElementById('email').value.trim();
  const dias=document.getElementById('dias').value;
  if(!nome){toast('⚠ Nome obrigatório');return;}
  const res=await fetch('/admin/criar-auto',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome,email,dias})});
  if(res.ok){const data=await res.json();toast('✓ Chave: '+data.chave);document.getElementById('nome').value='';document.getElementById('email').value='';carregar();}
  else toast('✗ Erro ao criar');
}
async function toggle(chave){await fetch('/admin/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});carregar();}
async function deletar(chave){if(!confirm('Remover este cliente?'))return;await fetch('/admin/deletar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});carregar();}
async function bloquearTodos(){
  if(!confirm('Bloquear TODOS os clientes ativos?'))return;
  await fetch('/admin/bloquear-todos',{method:'POST'});
  toast('🔒 Todos bloqueados');carregar();
}
carregar(); setInterval(carregar,15000);
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
#  PÁGINA DM (acesso via /dm)
# ─────────────────────────────────────────────
DM_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>Lucs Tech — DM</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;600&display=swap');
  :root{--bg:#080510;--c1:#bf5fff;--c2:#6020c0;--card:rgba(15,8,30,0.95);--text:#ede0ff;--muted:#7a5a99;--red:#ff2d55;--green:#00ffe0;--gold:#ffd700;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;
    background-image:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(120,40,220,0.2),transparent),
    repeating-linear-gradient(0deg,transparent,transparent 40px,rgba(160,80,255,0.02) 40px,rgba(160,80,255,0.02) 41px),
    repeating-linear-gradient(90deg,transparent,transparent 40px,rgba(160,80,255,0.02) 40px,rgba(160,80,255,0.02) 41px);}
  .wrap{max-width:1100px;margin:auto;padding:30px 20px;}
  .hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:35px;padding-bottom:20px;border-bottom:1px solid rgba(160,80,255,0.15);}
  .logo{font-family:'Orbitron',monospace;font-size:22px;font-weight:900;letter-spacing:3px;
    background:linear-gradient(90deg,var(--c1),var(--c2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
  .badge-dm{background:rgba(160,80,255,0.15);border:1px solid var(--c1);color:var(--c1);
    padding:5px 14px;border-radius:20px;font-size:11px;font-weight:600;letter-spacing:2px;}
  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px;}
  .sc{background:var(--card);border:1px solid rgba(160,80,255,0.1);border-radius:14px;padding:20px 15px;text-align:center;
    position:relative;overflow:hidden;transition:border-color .3s;}
  .sc:hover{border-color:rgba(160,80,255,0.35);}
  .sc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--c2),var(--c1));}
  .sc-num{font-family:'Orbitron',monospace;font-size:30px;font-weight:700;color:var(--c1);display:block;line-height:1;}
  .sc-lbl{font-size:10px;color:var(--muted);letter-spacing:2px;margin-top:6px;display:block;}
  .sc-num.red{color:var(--red);}  .sc-num.gold{color:var(--gold);}
  .panel{background:var(--card);border:1px solid rgba(160,80,255,0.12);border-radius:16px;padding:24px;margin-bottom:22px;}
  .panel-title{font-family:'Orbitron',monospace;font-size:11px;letter-spacing:3px;color:var(--c1);margin-bottom:18px;opacity:.8;}
  .form-row{display:grid;grid-template-columns:1fr 1fr 90px auto;gap:10px;align-items:end;}
  .field{display:flex;flex-direction:column;gap:6px;}
  .field label{font-size:10px;letter-spacing:2px;color:var(--muted);}
  input[type=text],input[type=email],input[type=number]{
    background:rgba(0,0,0,0.5);border:1px solid rgba(160,80,255,0.2);
    padding:11px 14px;border-radius:10px;color:#fff;font-family:'Rajdhani',sans-serif;
    font-size:14px;outline:none;transition:border-color .3s;width:100%;}
  input:focus{border-color:var(--c1);}
  .btn{background:linear-gradient(135deg,var(--c2),var(--c1));color:#fff;border:none;
    border-radius:10px;font-family:'Orbitron',monospace;font-size:11px;font-weight:700;
    letter-spacing:1px;padding:12px 20px;cursor:pointer;white-space:nowrap;transition:opacity .2s,transform .1s;}
  .btn:hover{opacity:.85;}  .btn:active{transform:scale(.97);}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th{color:var(--muted);font-size:10px;letter-spacing:2px;padding:10px 12px;border-bottom:1px solid rgba(160,80,255,0.1);text-align:left;}
  td{padding:13px 12px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:middle;}
  tr:hover td{background:rgba(160,80,255,0.03);}
  .chave{color:var(--gold);background:rgba(255,215,0,0.07);padding:5px 10px;border-radius:6px;
    cursor:pointer;font-family:'Orbitron',monospace;font-size:11px;letter-spacing:1px;
    border:1px solid rgba(255,215,0,0.2);transition:background .2s;}
  .chave:hover{background:rgba(255,215,0,0.15);}
  .pill{padding:4px 12px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:1px;border:none;cursor:pointer;transition:all .2s;}
  .on{background:rgba(0,255,224,0.1);color:var(--green);border:1px solid rgba(0,255,224,0.25);}
  .on:hover{background:rgba(0,255,224,0.2);}
  .off{background:rgba(255,45,85,0.12);color:var(--red);border:1px solid rgba(255,45,85,0.25);}
  .off:hover{background:rgba(255,45,85,0.22);}
  .del-btn{background:none;border:none;color:var(--red);cursor:pointer;font-size:18px;opacity:.4;transition:opacity .2s;padding:0 4px;}
  .del-btn:hover{opacity:1;}
  .btn-danger{background:rgba(255,45,85,0.12);color:var(--red);border:1px solid rgba(255,45,85,0.25);
    border-radius:8px;font-family:'Orbitron',monospace;font-size:10px;font-weight:700;letter-spacing:1px;
    padding:8px 16px;cursor:pointer;transition:all .2s;}
  .btn-danger:hover{background:rgba(255,45,85,0.25);}
  .logs{background:rgba(0,0,0,0.6);border-radius:10px;padding:14px;max-height:180px;
    overflow-y:auto;font-family:'Courier New',monospace;font-size:11px;color:#8858aa;line-height:1.8;}
  .logs::-webkit-scrollbar{width:4px;}
  .logs::-webkit-scrollbar-thumb{background:rgba(160,80,255,0.3);border-radius:4px;}
  .log-ok{color:#bf5fff;}  .log-fail{color:#ff2d55;}
  .toast{position:fixed;bottom:25px;right:25px;background:rgba(160,80,255,0.15);border:1px solid var(--c1);
    color:var(--c1);padding:12px 20px;border-radius:10px;font-family:'Orbitron',monospace;font-size:12px;
    opacity:0;transform:translateY(10px);transition:all .3s;pointer-events:none;z-index:999;}
  .toast.show{opacity:1;transform:translateY(0);}
  .tbl-actions{display:flex;gap:8px;align-items:center;justify-content:flex-end;}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">✦ LUCS TECH</div>
    <div style="display:flex;gap:12px;align-items:center;">
      <span class="badge-dm">DM MODE</span>
      <a href="/app" style="color:var(--muted);font-size:11px;letter-spacing:1px;text-decoration:none;
        border:1px solid rgba(255,255,255,0.1);padding:5px 12px;border-radius:20px;">APP MODE →</a>
    </div>
  </div>

  <div class="stats">
    <div class="sc"><span class="sc-num" id="s-total">—</span><span class="sc-lbl">TOTAL</span></div>
    <div class="sc"><span class="sc-num" id="s-ativos">—</span><span class="sc-lbl">ATIVOS</span></div>
    <div class="sc"><span class="sc-num red" id="s-bloq">—</span><span class="sc-lbl">BLOQUEADOS</span></div>
    <div class="sc"><span class="sc-num gold" id="s-hoje">—</span><span class="sc-lbl">LOGINS HOJE</span></div>
  </div>

  <div class="panel">
    <div class="panel-title">GERAR NOVO ACESSO</div>
    <div class="form-row">
      <div class="field"><label>NOME DO CLIENTE</label><input type="text" id="nome" placeholder="Ex: João Silva"></div>
      <div class="field"><label>E-MAIL</label><input type="email" id="email" placeholder="cliente@email.com"></div>
      <div class="field"><label>DIAS</label><input type="number" id="dias" value="30" min="1"></div>
      <button class="btn" onclick="criar()">✦ GERAR CHAVE</button>
    </div>
  </div>

  <div class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
      <div class="panel-title" style="margin:0;">CLIENTES CADASTRADOS</div>
      <button class="btn-danger" onclick="bloquearTodos()">🔒 BLOQUEAR TODOS</button>
    </div>
    <table>
      <thead><tr><th>CLIENTE</th><th>CHAVE</th><th>VENCIMENTO</th><th>STATUS</th><th style="text-align:right">AÇÕES</th></tr></thead>
      <tbody id="tabela"></tbody>
    </table>
  </div>

  <div class="panel">
    <div class="panel-title">HISTÓRICO DE ACESSOS</div>
    <div class="logs" id="logs">Carregando...</div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
function toast(msg){const t=document.getElementById('toast');t.innerText=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2500);}
async function carregar(){
  const res=await fetch('/admin/dados');const d=await res.json();
  document.getElementById('s-total').innerText=d.usuarios.length;
  document.getElementById('s-ativos').innerText=d.usuarios.filter(u=>u.ativo).length;
  document.getElementById('s-bloq').innerText=d.usuarios.filter(u=>!u.ativo).length;
  document.getElementById('s-hoje').innerText=d.logs_hoje;
  document.getElementById('tabela').innerHTML=d.usuarios.map(u=>`
    <tr>
      <td><b>${u.nome}</b><br><small style="color:var(--muted);font-size:11px">${u.email||''}</small></td>
      <td><span class="chave" onclick="copiar('${u.chave}')" title="Copiar">${u.chave}</span></td>
      <td style="color:var(--muted)">${u.expira?new Date(u.expira).toLocaleDateString('pt-BR'):'Sem limite'}</td>
      <td><button class="pill ${u.ativo?'on':'off'}" onclick="toggle('${u.chave}')">${u.ativo?'● ATIVO':'● BLOQUEADO'}</button></td>
      <td><div class="tbl-actions"><button class="del-btn" onclick="deletar('${u.chave}')" title="Remover">✕</button></div></td>
    </tr>
  `).join('');
  document.getElementById('logs').innerHTML=d.logs.map(l=>`
    <div>[${new Date(l.momento).toLocaleString('pt-BR')}]
      <span class="${l.sucesso?'log-ok':'log-fail'}">${l.sucesso?'✓ OK':'✗ NEGADO'}</span>
      — ${l.chave}
    </div>`).join('');
}
function copiar(c){navigator.clipboard.writeText(c);toast('✓ Chave copiada!');}
async function criar(){
  const nome=document.getElementById('nome').value.trim();
  const email=document.getElementById('email').value.trim();
  const dias=document.getElementById('dias').value;
  if(!nome){toast('⚠ Nome obrigatório');return;}
  const res=await fetch('/admin/criar-auto',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome,email,dias})});
  if(res.ok){const data=await res.json();toast('✓ Chave: '+data.chave);document.getElementById('nome').value='';document.getElementById('email').value='';carregar();}
  else toast('✗ Erro ao criar');
}
async function toggle(chave){await fetch('/admin/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});carregar();}
async function deletar(chave){if(!confirm('Remover este cliente?'))return;await fetch('/admin/deletar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chave})});carregar();}
async function bloquearTodos(){
  if(!confirm('Bloquear TODOS os clientes ativos?'))return;
  await fetch('/admin/bloquear-todos',{method:'POST'});
  toast('🔒 Todos bloqueados');carregar();
}
carregar();setInterval(carregar,15000);
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
#  ROTAS
# ─────────────────────────────────────────────
@app.route("/")
def root():
    return redirect("/app")

@app.route("/app")
def pagina_app():
    return render_template_string(APP_HTML)

@app.route("/dm")
def pagina_dm():
    return render_template_string(DM_HTML)

# Rota legada — mantida por compatibilidade
@app.route("/admin-sistema")
def admin_sistema():
    return redirect("/app")

@app.route("/api/validar", methods=["POST"])
def validar():
    dados = request.json or {}
    chave = dados.get("chave", "").strip()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
    user = cur.fetchone()
    sucesso = 0
    if user:
        vencido = user['expira'] and user['expira'] < datetime.now().date()
        if user['ativo'] and not vencido:
            sucesso = 1
    cur.execute("INSERT INTO logs (chave, sucesso, momento) VALUES (%s, %s, %s)", (chave, sucesso, datetime.now()))
    conn.commit(); cur.close(); conn.close()
    if sucesso:
        return jsonify({"ok": True, "nome": user['nome']})
    return jsonify({"ok": False, "msg": "Negado"}), 403

@app.route("/admin/dados")
def admin_dados():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios ORDER BY id DESC")
    u = cur.fetchall()
    cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 30")
    l = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM logs WHERE momento::date = CURRENT_DATE AND sucesso = 1")
    h = cur.fetchone()['count']
    cur.close(); conn.close()
    # Converter dates para string para evitar erro de serialização JSON
    usuarios = []
    for row in u:
        r = dict(row)
        if r.get('expira'):
            r['expira'] = r['expira'].isoformat()
        usuarios.append(r)
    logs = [dict(row) for row in l]
    for log in logs:
        if log.get('momento'):
            log['momento'] = log['momento'].isoformat()
    return jsonify({"usuarios": usuarios, "logs": logs, "logs_hoje": h})

@app.route("/admin/criar-auto", methods=["POST"])
def criar_auto():
    d = request.json
    nome = d.get('nome', '').strip()
    if not nome:
        return jsonify({"ok": False, "msg": "Nome obrigatório"}), 400
    chave = gerar_chave_automatica()
    dias = int(d.get('dias', 30))
    exp = datetime.now().date() + timedelta(days=dias)
    conn = get_db(); cur = conn.cursor()
    # Evita chave duplicada (tenta até 5 vezes)
    for _ in range(5):
        try:
            cur.execute(
                "INSERT INTO usuarios (nome, email, chave, expira, ativo) VALUES (%s, %s, %s, %s, True)",
                (nome, d.get('email'), chave, exp)
            )
            conn.commit()
            break
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            chave = gerar_chave_automatica()
    cur.close(); conn.close()
    return jsonify({"ok": True, "chave": chave})

@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    chave = request.json.get('chave')
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE usuarios SET ativo = NOT ativo WHERE chave = %s", (chave,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True})

@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    chave = request.json.get('chave')
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True})

@app.route("/admin/bloquear-todos", methods=["POST"])
def bloquear_todos():
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE usuarios SET ativo = False WHERE ativo = True")
    conn.commit(); cur.close(); conn.close()
    return jsonify({"ok": True})

@app.before_request
def setup():
    if not hasattr(app, 'init_done'):
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                email TEXT,
                chave TEXT UNIQUE NOT NULL,
                ativo BOOLEAN DEFAULT TRUE,
                expira DATE
            );
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                chave TEXT,
                sucesso INTEGER,
                momento TIMESTAMP
            );
        """)
        conn.commit(); cur.close(); conn.close()
        app.init_done = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
