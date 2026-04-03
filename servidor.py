"""
SERVIDOR DE LICENÇAS — Versão Final Corrigida
"""
from flask import Flask, request, jsonify, render_template_string, send_file
import psycopg2, psycopg2.extras
import secrets, datetime, os

app = Flask(__name__)

# Configuração do Banco (Render)
_db_url = os.environ.get("DATABASE_URL", "")
DATABASE_URL = _db_url.replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DATABASE_URL)

# ──────────────────────────────────────────────────────────
# 🚀 ROTA PRINCIPAL (AGORA É O SEU APP)
# ──────────────────────────────────────────────────────────
@app.route("/")
def abrir_app_online():
    # Quando o link principal for acessado, ele entrega o seu HTML do Planejador
    try:
        return send_file('planejador.html')
    except:
        return "<h1>Erro: Arquivo 'planejador.html' não encontrado no servidor.</h1>", 404

# ──────────────────────────────────────────────────────────
# 🔑 API DE VALIDAÇÃO (PRO APP LOCAL)
# ──────────────────────────────────────────────────────────
@app.route("/api/validar", methods=["POST"])
def validar():
    dados = request.json or {}
    chave = dados.get("chave", "").strip()
    # ... (mantenha sua lógica de validação no banco que você já tem) ...
    # Exemplo simplificado para o retorno:
    return jsonify({"ok": True, "nome": "Lucas"}) 

# ──────────────────────────────────────────────────────────
# 🛠️ PAINEL ADMIN (MOVIDO PARA ENDEREÇO SECRETO)
# ──────────────────────────────────────────────────────────
# Use este link para criar chaves: https://planejador-lucs.onrender.com/admin-sistema
@app.route("/admin-sistema")
def painel_gerenciador():
    # Aqui fica o seu PAINEL_HTML que você me mandou
    # (Aquele com as estatísticas e criação de usuários)
    return render_template_string(PAINEL_HTML) 

# --- Mantenha aqui todas as outras rotas /admin/dados, /admin/criar, etc ---
# ...
