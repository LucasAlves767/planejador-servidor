from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import os
import random
import string

app = Flask(__name__)

# 1. CONEXÃO AO BANCO DE DADOS
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# Função para gerar chave automática única (Ex: LUCS-X7Y8-Z9W1)
def gerar_chave_automatica():
    caracteres = string.ascii_uppercase + string.digits
    p1 = ''.join(random.choices(caracteres, k=4))
    p2 = ''.join(random.choices(caracteres, k=4))
    return f"LUCS-{p1}-{p2}"

# 2. PAINEL AZUL FUTURISTA (FRONT-END)
PAINEL_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>CyberAdmin v5.0 | Gestão Lucs</title>
    <style>
        :root { 
            --bg: #050a14; --accent: #00d2ff; --accent-glow: #0084ff;
            --card: rgba(10, 20, 40, 0.7); --text: #e0f2ff; --muted: #6a89a7;
        }
        body { 
            background: radial-gradient(circle at top, #0a1931 0%, #050a14 100%); 
            color: var(--text); font-family: 'Segoe UI', sans-serif; 
            padding: 30px; margin: 0; min-height: 100vh;
        }
        .container { max-width: 1200px; margin: auto; }
        .panel { 
            background: var(--card); border: 1px solid rgba(0, 210, 255, 0.2); 
            border-radius: 20px; padding: 30px; backdrop-filter: blur(20px);
            box-shadow: 0 0 40px rgba(0, 132, 255, 0.08);
        }
        h1 { color: var(--accent); text-transform: uppercase; text-shadow: 0 0 15px var(--accent-glow); margin:0 0 5px 0;}
        p.subtitle { color: var(--muted); margin-top: 0; margin-bottom: 30px; }
        
        /* Formulário de Criação */
        .grid-inputs { 
            display: grid; grid-template-columns: 2fr 2fr 100px auto; 
            gap: 15px; margin-bottom: 30px; background: rgba(0,0,0,0.3);
            padding: 20px; border-radius: 15px; border: 1px solid rgba(0, 210, 255, 0.1);
        }
        input { 
            background: rgba(0, 0, 0, 0.6); border: 1px solid rgba(0, 210, 255, 0.3); 
            padding: 14px; border-radius: 10px; color: #fff; outline: none; font-size: 14px;
        }
        input:focus { border-color: var(--accent); box-shadow: 0 0 10px rgba(0, 210, 255, 0.3); }
        
        .btn-main { 
            background: linear-gradient(90deg, #00d2ff, #3a7bd5); 
            color: #fff; border-radius: 10px; font-weight: bold; 
            padding: 14px 25px; border: none; cursor: pointer; text-transform: uppercase;
            box-shadow: 0 0 15px rgba(0, 210, 255, 0.4); transition: 0.3s;
        }
        .btn-main:hover { transform: translateY(-2px); box-shadow: 0 0 25px var(--accent-glow); }
        
        /* Tabela */
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; color: var(--muted); font-size: 12px; padding: 15px; border-bottom: 2px solid rgba(0, 210, 255, 0.1); text-transform: uppercase; }
        td { padding: 18px 15px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); vertical-align: middle; }
        
        .cliente-info { line-height: 1.4; }
        .cliente-nome { font-weight: bold; font-size: 15px; }
        .cliente-email { color: var(--muted); font-size: 12px; }
        
        code.chave { color: #fff; background: rgba(0, 210, 255, 0.15); padding: 6px 12px; border-radius: 6px; font-weight: bold; letter-spacing: 1px; border: 1px solid rgba(0, 210, 255, 0.3); }
        
        /* Botões de Ação na Tabela */
        .status-badge { 
            padding: 8px 15px; border-radius: 25px; font-size: 11px; font-weight: bold; 
            cursor: pointer; border: 1px solid transparent; transition: 0.2s; text-transform: uppercase;
        }
        .on { background: rgba(0, 210, 255, 0.1); color: #00d2ff; border-color: #00d2ff; box-shadow: 0 0 10px rgba(0, 210, 255, 0.2); }
        .on:hover { background: rgba(0, 210, 255, 0.2); }
        .off { background: rgba(255, 60, 60, 0.1); color: #ff3c3c; border-color: #ff3c3c; box-shadow: 0 0 10px rgba(255, 60, 60, 0.2); }
        .off:hover { background: rgba(255, 60, 60, 0.2); }
        
        .btn-excluir { background: none; color: #ff3c3c; border: none; cursor: pointer; font-size: 12px; opacity: 0.7; transition: 0.2s; font-weight: bold; }
        .btn-excluir:hover { opacity: 1; text-shadow: 0 0 8px #ff3c3c; }
    </style>
</head>
<body>
    <div class="container">
        <h1>CyberAdmin Protocol</h1>
        <p class="subtitle">Monitoramento de Atividade e Geração de Acessos</p>
        
        <div class="panel">
            <div class="grid-inputs">
                <input type="text" id="nome" placeholder="Nome do Cliente">
                <input type="email" id="email" placeholder="E-mail (opcional)">
                <input type="number" id="dias" placeholder="Dias" value="30">
                <button class="btn-main" id="btnGerar">⚡ Gerar Acesso</button>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Cliente</th>
                        <th>Chave de Acesso</th>
                        <th>Vencimento</th>
                        <th>Último Login</th>
                        <th>Controle Manual</th>
                        <th>Excluir</th>
                    </tr>
                </thead>
                <tbody id="tabela"></tbody>
            </table>
        </div>
    </div>

    <script>
        // Função para formatar data e hora
        function formatarData(dataStr) {
            if (!dataStr) return '<span style="color:#6a89a7">Nunca acessou</span>';
            const d = new Date(dataStr);
            return d.toLocaleString('pt-BR');
        }

        async function carregar() {
            const r = await fetch('/admin/dados');
            const dados = await r.json();
            document.getElementById('tabela').innerHTML = dados.map(u => `
                <tr>
                    <td class="cliente-info">
                        <div class="cliente-nome">${u.nome}</div>
                        <div class="cliente-email">${u.email || 'Sem e-mail'}</div>
                    </td>
                    <td><code class="chave">${u.chave}</code></td>
                    <td style="color: ${new Date(u.expira) < new Date() ? '#ff3c3c' : '#e0f2ff'}">
                        ${u.expira ? new Date(u.expira).toLocaleDateString('pt-BR') : 'Vitalício'}
                    </td>
                    <td>${formatarData(u.ultimo_acesso)}</td>
                    <td>
                        <button class="status-badge ${u.ativo ? 'on' : 'off'}" onclick="toggle('${u.chave}')" title="Clique para bloquear/liberar">
                            ${u.ativo ? '🟢 ATIVO' : '🔴 BLOQUEADO'}
                        </button>
                    </td>
                    <td><button class="btn-excluir" onclick="deletar('${u.chave}')">Remover</button></td>
                </tr>
            `).join('');
        }

        // Evento de clique para gerar nova chave
        document.getElementById('btnGerar').onclick = async () => {
            const nome = document.getElementById('nome').value;
            const email = document.getElementById('email').value;
            const dias = document.getElementById('dias').value;
            
            if(!nome) return alert('⚠️ Por favor, digite o nome do cliente!');

            const res = await fetch('/admin/criar-auto', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({nome, email, dias})
            });
            
            const data = await res.json();
            if(data.ok) {
                // Mostra a chave para você copiar e mandar no WhatsApp do cliente
                prompt('✅ ACESSO GERADO COM SUCESSO!\\nCopie a chave abaixo e envie ao cliente:', data.chave);
                document.getElementById('nome').value = '';
                document.getElementById('email').value = '';
                carregar(); // Atualiza a tabela na hora
            }
        };

        // Função do botão de controle manual (Inverte entre Ativo/Bloqueado)
        async function toggle(chave) {
            await fetch('/admin/toggle', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({chave}) 
            });
            carregar(); // Atualiza a tabela na hora para mudar a cor do botão
        }

        // Função para apagar a chave de vez
        async function deletar(chave) {
            if(confirm('Tem certeza que deseja apagar essa chave permanentemente?')) {
                await fetch('/admin/deletar', { 
                    method:'POST', 
                    headers:{'Content-Type':'application/json'}, 
                    body:JSON.stringify({chave}) 
                });
                carregar();
            }
        }

        // Inicia carregando os dados e atualiza a cada 15 segundos
        carregar();
        setInterval(carregar, 15000); 
    </script>
</body>
</html>
"""

# 3. ROTAS DO SISTEMA (BACK-END)
@app.route("/")
def home():
    return send_file('planejador.html') if os.path.exists('planejador.html') else "Cyber Sistema Online"

@app.route("/admin-sistema")
def admin_page():
    return render_template_string(PAINEL_HTML)

# Rota para Criar Cliente e Gerar Chave
@app.route("/admin/criar-auto", methods=["POST"])
def criar_auto():
    d = request.json
    # Gera a chave garantindo formato seguro
    chave = gerar_chave_automatica()
    vencimento = datetime.now().date() + timedelta(days=int(d.get('dias', 30)))
    
    conn = get_db()
    cur = conn.cursor()
    try:
        # Salva no banco de dados
        cur.execute("INSERT INTO usuarios (nome, email, chave, expira, ativo) VALUES (%s, %s, %s, %s, True)", 
                    (d['nome'], d.get('email'), chave, vencimento))
        conn.commit()
        return jsonify({"ok": True, "chave": chave})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# A ROTA MAIS IMPORTANTE: A QUE O SEU .EXE ACESSA
@app.route("/api/validar", methods=["POST"])
def validar():
    dados = request.json or {}
    chave = dados.get("chave", "").strip()
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome, ativo, expira FROM usuarios WHERE chave = %s", (chave,))
    user = cur.fetchone()
    
    if user:
        # Verifica se passou dos dias
        vencido = user['expira'] and user['expira'] < datetime.now().date()
        
        # Se você bloqueou manualmente (ativo=False) OU se venceu:
        if not user['ativo'] or vencido:
            cur.close()
            conn.close()
            return jsonify({"ok": False, "msg": "Acesso Bloqueado ou Expirado"}), 403
        
        # Se tudo estiver OK, registra o log de acesso (hora exata do login)
        cur.execute("UPDATE usuarios SET ultimo_acesso = %s WHERE chave = %s", (datetime.now(), chave))
        conn.commit()
        
        cur.close()
        conn.close()
        return jsonify({"ok": True, "nome": user['nome']})
    
    cur.close()
    conn.close()
    return jsonify({"ok": False, "msg": "Chave Inválida"}), 401

# Rota para carregar a tabela
@app.route("/admin/dados")
def admin_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nome, email, chave, ativo, expira, ultimo_acesso FROM usuarios ORDER BY id DESC")
    res = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(res)

# Rota do botão de Bloquear/Liberar manual
@app.route("/admin/toggle", methods=["POST"])
def admin_toggle():
    chave = request.json.get('chave')
    conn = get_db()
    cur = conn.cursor()
    # Inverte de Verdadeiro para Falso (ou vice-versa)
    cur.execute("UPDATE usuarios SET ativo = NOT ativo WHERE chave = %s", (chave,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})

# Rota para excluir cliente
@app.route("/admin/deletar", methods=["POST"])
def admin_deletar():
    chave = request.json.get('chave')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE chave = %s", (chave,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})

# Cria a tabela no banco caso ela ainda não exista
@app.before_request
def setup():
    if not hasattr(app, 'init_done'):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT,
                email TEXT,
                chave TEXT UNIQUE,
                ativo BOOLEAN DEFAULT TRUE,
                expira DATE,
                ultimo_acesso TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        app.init_done = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
