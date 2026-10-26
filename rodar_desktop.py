import os
import re
import sys
import time
import json
import base64
import sqlite3
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ==========================================
# Configurações Gerais e Credenciais
# ==========================================
def carregar_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    if k not in os.environ:
                        os.environ[k] = v.strip().strip('"').strip("'")

carregar_env()

REPO = "saaesilva/estoque-bigmais-automacao"
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
USUARIO = (os.getenv("SISTEMA_LOGIN") or "").strip() or "samuel.silva"
SENHA = (os.getenv("SISTEMA_SENHA") or "").strip() or "9888"
URL = "https://bigmais.dext.com.br/dxt_com/dxt_con_prd/index.php?menu_ativo=6&aplic_ativa=3"
CAMINHO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estoque_bigmais.db")
CAMINHO_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estoque_bigmais.json")

def extrair_unidade(descricao):
    d = (descricao or "").upper().strip()
    if re.search(r'\b(KG|QUILO|KILO)\b', d) and not re.search(r'\b\d+\s*KG\b', d):
        return "KG", "kg", "Quilo"
    elif re.search(r'\b(BDJ|BANDEJA|BANDEJAS|BJA)\b', d):
        return "BDJ", "bdj", "Bandeja"
    elif re.search(r'\b(PCT|PACOTE|PACOTES|FITO|SACO)\b', d):
        return "PCT", "pct", "Pacote"
    elif re.search(r'\b(CX|CAIXA|CAIXAS)\b', d):
        return "CX", "cx", "Caixa"
    elif re.search(r'\b(MC|MACO|MAÇO|MAÇOS|MOLHO|MOLHOS)\b', d):
        return "MC", "mc", "Maço"
    elif re.search(r'\b(DZ|DUZIA|DÚZIA)\b', d):
        return "DZ", "dz", "Dúzia"
    elif re.search(r'\b(UN|UND|UNIDADE|UNIDADES)\b', d):
        return "UN", "un", "Unidade"
    elif "FITO" in d:
        return "PCT", "pct", "Pacote"
    elif re.search(r'\b\d+\s*G\b', d):
        return "BDJ", "bdj", "Bandeja"
    return "UN", "un", "Unidade"

def calcular_dias_sem_venda(data_venda_str, data_referencia=None):
    if not data_venda_str:
        return None, "Sem Venda"
    
    texto = str(data_venda_str).strip()
    if texto in ('( Dias )', '-', '', 'None', 'null'):
        return None, "Sem Venda"

    if data_referencia is None:
        try:
            data_referencia = datetime.now(timezone(timedelta(hours=-3))).date()
        except Exception:
            data_referencia = date.today()

    # 1. Tenta extrair a data real DD/MM/YYYY
    m_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto)
    if m_data:
        try:
            dia, mes, ano = int(m_data.group(1)), int(m_data.group(2)), int(m_data.group(3))
            dt_venda = date(ano, mes, dia)
            diff = (data_referencia - dt_venda).days
            if diff >= 0:
                dias_str = "Hoje (0 dias)" if diff == 0 else ("1 dia" if diff == 1 else f"{diff} dias")
                return diff, dias_str
        except Exception:
            pass

    # 2. Se tem número explícito em ( X Dias )
    m_dias = re.search(r'\(?\s*(\d+)\s*Dias?\s*\)?', texto, re.I)
    if m_dias:
        d = int(m_dias.group(1))
        dias_str = "Hoje (0 dias)" if d == 0 else ("1 dia" if d == 1 else f"{d} dias")
        return d, dias_str

    return None, "Sem Venda"


def exportar_json(caminho_db, caminho_json):
    try:
        conn = sqlite3.connect(caminho_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM estoque_atual ORDER BY loja, codigo").fetchall()
        hoje_ref = datetime.now(timezone(timedelta(hours=-3))).date()
        lista = []
        for r in rows:
            data_venda = r['data_ult_venda'] or ""
            idade = r['idade_estoque'] or ""
            dias_sem_venda, dias_str = calcular_dias_sem_venda(data_venda, hoje_ref)
            
            data_compra = r['data_ult_compra'] or ""
            m_compra = re.search(r'(\d{2}/\d{2}/\d{4})', data_compra)
            m_compra_dias = re.search(r'\(?\s*(\d+)\s*Dias?\s*\)?', data_compra, re.I)
            ult_compra_str = "-"
            if m_compra:
                ult_compra_str = f"{m_compra.group(1)} ({m_compra_dias.group(1)}d)" if m_compra_dias else m_compra.group(1)

            margem_val = r['margem_pdv']
            margem_str = f"{float(margem_val):.1f}%" if margem_val is not None else "-"

            desc = (r['descricao'] or "").strip()
            u_tipo, u_sigla, u_rotulo = extrair_unidade(desc)
            raw_est = float(r['estoque'] or 0.0)
            if u_tipo == 'KG':
                if (abs(raw_est) >= 1000 and int(raw_est) == raw_est) or abs(raw_est) >= 10000:
                    raw_est = raw_est / 1000.0
                estoque_num = round(raw_est, 3)
                is_neg = estoque_num < 0
                abs_val = abs(estoque_num)
                formatted = f"{abs_val:.3f}"
                p_int, p_dec = formatted.split('.')
                int_fmt = f"{int(p_int):,}".replace(',', '.')
                sinal = "-" if is_neg else ""
                estoque_str = f"{sinal}{int_fmt},{p_dec} {u_sigla}"
            else:
                estoque_num = int(round(raw_est))
                is_neg = estoque_num < 0
                abs_val = abs(estoque_num)
                int_fmt = f"{abs_val:,}".replace(',', '.')
                sinal = "-" if is_neg else ""
                estoque_str = f"{sinal}{int_fmt} {u_sigla}"

            curva, giro = classificar_curva_produto(str(r['codigo'] or "").strip(), desc)

            lista.append({
                "loja": r['loja'] or "",
                "codigo": str(r['codigo'] or "").strip(),
                "descricao": desc,
                "nome": desc,
                "unidade": u_tipo,
                "unidade_sigla": u_sigla,
                "unidade_rotulo": u_rotulo,
                "curva": curva,
                "giro": giro,
                "estoque": estoque_num,
                "estoque_raw": estoque_num,
                "estoque_formatado": estoque_str,
                "preco_venda": float(r['preco_venda'] or 0.0),
                "custo_liquido": float(r['custo_liquido'] or 0.0),
                "margem_pdv": margem_str,
                "data_ult_compra": data_compra,
                "data_ult_venda": data_venda,
                "ult_compra_str": ult_compra_str,
                "dias_sem_venda": dias_sem_venda,
                "dias_sem_venda_str": dias_str,
                "idade_estoque": idade,
                "dias_estoque": float(r['dias_estoque'] or 0.0) if r['dias_estoque'] else 0.0,
                "data_coleta": r['data_coleta'] or ""
            })
        conn.close()
        with open(caminho_json, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
        print(f"📦 Catálogo JSON exportado com sucesso: {caminho_json} ({len(lista)} registros)", flush=True)
    except Exception as e:
        print(f"⚠️ Erro ao exportar JSON de estoque: {e}", flush=True)

FUSO_BR = timezone(timedelta(hours=-3))
agora_br = datetime.now(FUSO_BR)
DATA_HOJE = agora_br.strftime("%Y-%m-%d")

try:
    from produtos_catalogo import PRODUTOS_CANONICOS, CODIGOS_PRODUTOS, classificar_curva_produto, CODIGOS_CURVA_A
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from produtos_catalogo import PRODUTOS_CANONICOS, CODIGOS_PRODUTOS, classificar_curva_produto, CODIGOS_CURVA_A


def limpar_valor_numerico(texto):
    if not texto:
        return 0.0
    try:
        t = str(texto).replace("R$", "").replace("%", "").strip()
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        match = re.search(r"[-+]?\d*\.?\d+", t)
        return float(match.group(0)) if match else 0.0
    except Exception:
        return 0.0

def limpar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()

def upload_db_to_github(token, repo, local_file_path, target_repo_path="estoque_bigmais.db"):
    if not os.path.exists(local_file_path):
        print(f"[-] Arquivo local não encontrado: {local_file_path}")
        return False

    file_size_kb = os.path.getsize(local_file_path) / 1024
    print(f"\n☁️ Preparando upload do banco ({file_size_kb:.1f} KB) para o GitHub...")

    with open(local_file_path, "rb") as f:
        content_bytes = f.read()

    b64_content = base64.b64encode(content_bytes).decode("utf-8")
    api_url = f"https://api.github.com/repos/{repo}/contents/{target_repo_path}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Agent",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha = data.get("sha")
            print(f"[*] Localizado arquivo existente no GitHub (SHA: {sha[:7] if sha else ''})")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("[*] Arquivo ainda não existe no repositório. Criando novo...")
        else:
            print(f"[!] Erro ao checar arquivo no GitHub: {e.code}")

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    payload = {
        "message": f"Atualização manual de estoque via Desktop [{now_str}]",
        "content": b64_content
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            commit_sha = res_data.get("commit", {}).get("sha", "")[:7]
            print(f"✅ [GitHub] '{target_repo_path}' atualizado com sucesso! (Commit: {commit_sha})")
            print(f"🔗 Link: https://github.com/{repo}")
            return True
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print(f"❌ [GitHub] Falha ao enviar para o repositório: {e.code} - {err_msg}")
        return False

def baixar_db_do_github(token, repo, local_file_path, target_repo_path="estoque_bigmais.db"):
    if os.path.exists(local_file_path):
        return True
    try:
        print(f"📥 Baixando banco existente ({target_repo_path}) do GitHub...")
        api_url = f"https://api.github.com/repos/{repo}/contents/{target_repo_path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Antigravity-Agent",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = base64.b64decode(data["content"])
            with open(local_file_path, "wb") as f:
                f.write(content)
        print("✅ Banco existente sincronizado do GitHub com sucesso!")
        return True
    except Exception as e:
        print(f"[!] Não foi possível baixar banco anterior do GitHub (um novo será criado se necessário): {e}")
        return False

def ordenar_produtos_por_prioridade(conn, nome_loja, codigos_produtos):
    """
    Ordena produtos estrategicamente priorizando:
    1. Curva A (Alto Giro - FLV essencial) e Curva B (Médio Giro)
    2. Ruptura de Estoque (estoque <= 0 em itens de Alto Giro exige urgência máxima)
    3. Giro ativo no dia (venda confirmada hoje ou ontem no ERP)
    4. Produtos sem informações comerciais completas (preço, custo, última compra/venda)
    5. Produtos que ainda não foram coletados na data de hoje
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT codigo, descricao, estoque, preco_venda, custo_liquido,
               data_ult_compra, data_ult_venda, data_coleta
        FROM estoque_atual
        WHERE loja = ?
    """, (nome_loja,))
    dados_loja = {str(r[0]).strip(): r for r in cursor.fetchall()}
    data_hoje = datetime.now(FUSO_BR).strftime("%Y-%m-%d")

    def calcular_urgencia(cod):
        cod_str = str(cod).strip()
        desc_canonica = PRODUTOS_CANONICOS.get(cod_str, "")
        curva, giro = classificar_curva_produto(cod_str, desc_canonica)

        if cod_str not in dados_loja:
            # Nunca coletado na loja: máxima prioridade, especialmente se Curva A
            bonus_curva = 500 if curva == "A" else (200 if curva == "B" else 0)
            return 2000 + bonus_curva

        row = dados_loja[cod_str]
        desc = (row[1] or desc_canonica).strip()
        estoque = float(row[2] or 0.0)
        preco = float(row[3] or 0.0)
        custo = float(row[4] or 0.0)
        ult_compra = (row[5] or "").strip()
        ult_venda = (row[6] or "").strip()
        data_col = (row[7] or "").strip()

        score = 0

        # 1. Prioridade por Curva ABC / Giro (Alto Giro sempre na frente)
        if curva == "A":
            score += 600
        elif curva == "B":
            score += 250
        else: # C
            score += 50

        # 2. Ruptura de Estoque (Estoque zerado ou negativo)
        if estoque <= 0.0:
            if curva == "A":
                score += 400 # Ruptura em Curva A é emergencial!
            elif curva == "B":
                score += 150
            else:
                score += 50

        # 3. Giro ativo comprovado no PDV (venda diária recente)
        if ult_venda:
            m = re.search(r'\(?\s*(\d+)\s*Dias?\s*\)?', ult_venda, re.I)
            if m:
                dias_venda = int(m.group(1))
                if dias_venda == 0:
                    score += 250 # Vendeu hoje!
                elif dias_venda == 1:
                    score += 120 # Vendeu ontem
                elif dias_venda <= 3:
                    score += 60

        # 4. Dados comerciais ausentes ou incompletos
        if preco <= 0.0:
            score += 300
        if custo <= 0.0:
            score += 200
        if desc.startswith("PRODUTO "):
            score += 200
        if not ult_compra or ult_compra == "-":
            score += 100
        if not ult_venda or ult_venda == "-":
            score += 50

        # 5. Desatualizado no dia de hoje
        if data_col != data_hoje:
            score += 200

        return score

    return sorted(codigos_produtos, key=calcular_urgencia, reverse=True)


def executar_coleta(visivel=False, limite=None, loja_especifica=None, sem_upload=False):
    from tqdm import tqdm
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    baixar_db_do_github(GITHUB_TOKEN, REPO, CAMINHO_DB)

    print("========================================================")
    print("   COLETA DE ESTOQUE BIG MAIS - MODO DESKTOP")
    print("========================================================")
    print(f"📅 Data da coleta: {DATA_HOJE}")
    print(f"👤 Usuário: {USUARIO}")
    print(f"🌐 Modo de Navegador: {'🖥️ Visível (na tela)' if visivel else '🕶️ Headless (em segundo plano)'}")
    if limite:
        print(f"⚠️ Limite para teste: {limite} produtos")
    if loja_especifica:
        print(f"🏢 Loja específica: {loja_especifica}")
    print("========================================================\n")

    options = webdriver.ChromeOptions()
    if not visivel:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        print(f"🔐 Acessando o sistema com o usuário: {USUARIO}...", flush=True)
        driver.get(URL)
        time.sleep(2)

        campo_login = wait.until(EC.presence_of_element_located((By.ID, "login")))
        campo_login.clear()
        campo_login.send_keys(USUARIO)

        campo_senha = driver.find_element(By.ID, "password")
        campo_senha.clear()
        campo_senha.send_keys(SENHA)

        try:
            driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']").click()
        except Exception:
            campo_senha.send_keys(Keys.RETURN)

        time.sleep(3)
        print(f"✅ Login efetuado com sucesso!\n", flush=True)

        # Configura Banco SQLite Local
        conn = sqlite3.connect(CAMINHO_DB)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estoque_atual (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loja TEXT,
                codigo TEXT,
                descricao TEXT,
                estoque INTEGER,
                preco_venda REAL,
                custo_liquido REAL,
                margem_pdv REAL,
                dias_estoque REAL,
                data_ult_compra TEXT,
                data_ult_venda TEXT,
                idade_estoque TEXT,
                data_coleta TEXT,
                UNIQUE(loja, codigo)
            )
        """)
        conn.commit()

        # Migração automática de colunas
        colunas_novas = [
            ("preco_venda", "REAL"),
            ("custo_liquido", "REAL"),
            ("margem_pdv", "REAL"),
            ("dias_estoque", "REAL"),
            ("data_ult_compra", "TEXT"),
            ("data_ult_venda", "TEXT"),
            ("idade_estoque", "TEXT")
        ]
        for col, tipo in colunas_novas:
            try:
                cursor.execute(f"ALTER TABLE estoque_atual ADD COLUMN {col} {tipo}")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        # Captura de Lojas
        driver.get(URL)
        time.sleep(2)
        print("🏢 Carregando lista de unidades...", flush=True)

        botao_dropdown = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.dropdown-toggle, div.dropdown button")))
        botao_dropdown.click()

        elementos_lojas = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.dropdown-menu.inner span.text"))
        )
        lista_lojas = [el.text.strip() for el in elementos_lojas if el.text.strip() and el.text.strip() != "Selecione"]
        
        if loja_especifica:
            lista_lojas = [l for l in lista_lojas if loja_especifica.lower() in l.lower()]
            if not lista_lojas:
                print(f"❌ Nenhuma loja encontrada com o nome: '{loja_especifica}'")
                return

        print(f"🏢 Lojas selecionadas ({len(lista_lojas)}): {lista_lojas}\n", flush=True)

        produtos_para_coletar = CODIGOS_PRODUTOS[:limite] if limite else CODIGOS_PRODUTOS
        total_etapas = len(lista_lojas) * len(produtos_para_coletar)
        print(f"🚀 Iniciando coleta de {len(produtos_para_coletar)} produtos em {len(lista_lojas)} lojas...", flush=True)

        itens_coletados = 0
        with tqdm(total=total_etapas, desc="Progresso", unit="prod") as barra:
            for nome_loja in lista_lojas:
                try:
                    driver.get(URL)
                    time.sleep(1)
                    driver.find_element(By.CSS_SELECTOR, "button.dropdown-toggle, div.dropdown button").click()
                    time.sleep(0.3)
                    driver.find_element(By.XPATH, f"//ul[contains(@class, 'dropdown-menu')]//span[@class='text' and text()='{nome_loja}']").click()
                    time.sleep(1)

                    # Prioriza produtos sem informação para coletar primeiro
                    produtos_ordenados = ordenar_produtos_por_prioridade(conn, nome_loja, produtos_para_coletar)

                    for codigo_produto in produtos_ordenados:
                        barra.set_postfix_str(f"{nome_loja[:10]} | Cód: {codigo_produto}")
                        try:
                            # 1. Remove ativamente modais anteriores do DOM para não vazar dados
                            driver.execute_script("""
                                document.querySelectorAll('.modal, .modal-backdrop, [class*="modal"], [id*="modal"], [id*="Modal"]').forEach(el => {
                                    try { el.remove(); } catch(e) {}
                                });
                                const tbody = document.querySelector('table.displayRelatorios tbody');
                                if (tbody) tbody.innerHTML = '';
                            """)
                            time.sleep(0.2)

                            campo = wait.until(EC.element_to_be_clickable((By.ID, "idfiltrolistaproduto")))
                            campo.clear()
                            campo.send_keys(codigo_produto)
                            driver.find_element(By.XPATH, "//button[contains(@onclick, 'jaxon_fn_buscaprodutolist') and contains(text(), 'Cod. Produto')]").click()

                            # 2. Aguarda até a linha correspondente ao código_produto aparecer na tabela (máx 2.4s)
                            linha_encontrada = False
                            for _ in range(12):
                                time.sleep(0.2)
                                tem_linha = driver.execute_script("""
                                    const cod = arguments[0];
                                    const linhas = Array.from(document.querySelectorAll('table.displayRelatorios tbody tr'));
                                    for (let r of linhas) {
                                        const oc = r.getAttribute('ondblclick') || '';
                                        const celulas = r.querySelectorAll('td, th');
                                        let codLinha = '';
                                        if (celulas.length > 2) {
                                            codLinha = celulas[1].innerText.trim() || celulas[2].innerText.trim();
                                        }
                                        if (oc.includes("'" + cod + "'") || oc.includes('"' + cod + '"') || codLinha === cod || r.innerText.includes(cod)) {
                                            return true;
                                        }
                                    }
                                    return false;
                                """, codigo_produto)
                                if tem_linha:
                                    linha_encontrada = True
                                    break

                            if linha_encontrada:
                                # Dispara duplo-clique APENAS na linha que corresponde ao código do produto
                                driver.execute_script("""
                                    const cod = arguments[0];
                                    const linhas = Array.from(document.querySelectorAll('table.displayRelatorios tbody tr'));
                                    for (let r of linhas) {
                                        const oc = r.getAttribute('ondblclick') || '';
                                        const celulas = r.querySelectorAll('td, th');
                                        let codLinha = '';
                                        if (celulas.length > 2) {
                                            codLinha = celulas[1].innerText.trim() || celulas[2].innerText.trim();
                                        }
                                        if (oc.includes("'" + cod + "'") || oc.includes('"' + cod + '"') || codLinha === cod || r.innerText.includes(cod)) {
                                            if (oc) eval(oc);
                                            break;
                                        }
                                    }
                                """, codigo_produto)
                                time.sleep(1.2)

                                # Extrai dados estritamente do modal ativo visível
                                dados = driver.execute_script("""
                                    function normalizar(t) {
                                        return (t || '')
                                            .toLowerCase()
                                            .normalize('NFD')
                                            .replace(/[\\u0300-\\u036f]/g, '')
                                            .trim()
                                            .replace(/\\s+/g, ' ');
                                    }

                                    let descricao = '';
                                    let estoque = 0;

                                    const cod = arguments[0];
                                    const linhas = Array.from(document.querySelectorAll('table.displayRelatorios tbody tr'));
                                    for (let r of linhas) {
                                        const oc = r.getAttribute('ondblclick') || '';
                                        const celulas = r.querySelectorAll('td, th');
                                        let codLinha = '';
                                        if (celulas.length > 2) {
                                            codLinha = celulas[1].innerText.trim() || celulas[2].innerText.trim();
                                        }
                                        if (oc.includes("'" + cod + "'") || oc.includes('"' + cod + '"') || codLinha === cod || r.innerText.includes(cod)) {
                                            if (celulas.length >= 5) {
                                                descricao = celulas[3].innerText.trim();
                                                let tEst = celulas[4].innerText.trim();
                                                if (tEst.includes(',') && tEst.includes('.')) {
                                                    if (tEst.lastIndexOf(',') > tEst.lastIndexOf('.')) {
                                                        tEst = tEst.replace(/\\./g, '').replace(',', '.');
                                                    } else {
                                                        tEst = tEst.replace(/,/g, '');
                                                    }
                                                } else if (tEst.includes(',')) {
                                                    tEst = tEst.replace(',', '.');
                                                }
                                                estoque = parseFloat(tEst) || 0;
                                                if (/\\b(KG|QUILO|KILO)\\b/i.test(descricao) && !/\\b\\d+\\s*KG\\b/i.test(descricao)) {
                                                    if ((Math.abs(estoque) >= 1000 && Math.floor(estoque) === estoque) || Math.abs(estoque) >= 10000) {
                                                        estoque = estoque / 1000;
                                                    }
                                                }
                                            }
                                            break;
                                        }
                                    }

                                    function obterContainerModal() {
                                        const modais = Array.from(document.querySelectorAll('.modal, [id*="modal"], [id*="Modal"], [class*="modal"]')).filter(m => {
                                            try {
                                                const s = window.getComputedStyle(m);
                                                if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
                                                return m.offsetWidth > 0 || m.offsetHeight > 0;
                                            } catch(e) { return false; }
                                        });
                                        return modais.length > 0 ? modais[modais.length - 1] : null;
                                    }
                                    const modalAtivo = obterContainerModal();

                                    function extrairValor(rotulo) {
                                        if (!modalAtivo) return '';
                                        const rotuloNorm = normalizar(rotulo);
                                        const elementos = Array.from(modalAtivo.querySelectorAll('th, td'));
                                        for (let el of elementos) {
                                            if (normalizar(el.innerText) === rotuloNorm) {
                                                if (el.nextElementSibling && el.nextElementSibling.innerText) {
                                                    return el.nextElementSibling.innerText.trim();
                                                }
                                                if (el.parentElement && el.parentElement.nextElementSibling) {
                                                    const idx = Array.from(el.parentElement.children).indexOf(el);
                                                    const nextRowCell = el.parentElement.nextElementSibling.children[idx];
                                                    if (nextRowCell && nextRowCell.innerText) {
                                                        return nextRowCell.innerText.trim();
                                                    }
                                                }
                                            }
                                        }
                                        return '';
                                    }

                                    let precoVenda = '';
                                    if (modalAtivo) {
                                        const ths = Array.from(modalAtivo.querySelectorAll('th'));
                                        for (let th of ths) {
                                            if (th.innerText && th.innerText.trim() === 'UN 1') {
                                                if (th.nextElementSibling && th.nextElementSibling.innerText) {
                                                    precoVenda = th.nextElementSibling.innerText.trim();
                                                    break;
                                                }
                                            }
                                        }
                                    }

                                    return {
                                        descricao: descricao,
                                        estoque: estoque,
                                        preco_venda: precoVenda,
                                        custo_liquido: extrairValor('Custo Líquido') || extrairValor('Custo Liquido'),
                                        margem_pdv: extrairValor('Val. Margem PDV'),
                                        dias_estoque: extrairValor('Dias de Estoque'),
                                        data_ult_compra: extrairValor('Data Ult Compra'),
                                        data_ult_venda: extrairValor('Data Ult Venda'),
                                        idade_estoque: extrairValor('Idade Estoque')
                                    };
                                """, codigo_produto)

                                desc_extraida = limpar_texto(dados.get("descricao"))
                                descricao = desc_extraida or PRODUTOS_CANONICOS.get(codigo_produto, f"PRODUTO {codigo_produto}")
                                estoque = round(float(dados.get("estoque") or 0.0), 3)
                                preco_venda = limpar_valor_numerico(dados.get("preco_venda"))
                                custo_liquido = limpar_valor_numerico(dados.get("custo_liquido"))
                                margem_pdv = limpar_valor_numerico(dados.get("margem_pdv"))
                                dias_estoque = limpar_valor_numerico(dados.get("dias_estoque"))
                                data_ult_compra = limpar_texto(dados.get("data_ult_compra"))
                                data_ult_venda = limpar_texto(dados.get("data_ult_venda"))
                                idade_estoque = limpar_texto(dados.get("idade_estoque"))
                            else:
                                # O produto não foi retornado nesta loja: NUNCA herdar dados do produto anterior!
                                descricao = PRODUTOS_CANONICOS.get(codigo_produto, f"PRODUTO {codigo_produto}")
                                estoque = 0
                                preco_venda = 0.0
                                custo_liquido = 0.0
                                margem_pdv = 0.0
                                dias_estoque = 0.0
                                data_ult_compra = ""
                                data_ult_venda = ""
                                idade_estoque = ""

                            cursor.execute("""
                                INSERT OR REPLACE INTO estoque_atual (
                                    loja, codigo, descricao, estoque,
                                    preco_venda, custo_liquido, margem_pdv, dias_estoque,
                                    data_ult_compra, data_ult_venda, idade_estoque,
                                    data_coleta
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                nome_loja, codigo_produto, descricao, estoque,
                                preco_venda, custo_liquido, margem_pdv, dias_estoque,
                                data_ult_compra, data_ult_venda, idade_estoque,
                                DATA_HOJE
                            ))
                            conn.commit()
                            itens_coletados += 1

                            # Atualiza o catálogo JSON incrementalmente a cada 5 produtos
                            if itens_coletados % 5 == 0:
                                exportar_json(CAMINHO_DB, CAMINHO_JSON)
                        except Exception:
                            pass

                        barra.update(1)

                    # Ao finalizar a loja: exporta o JSON e sincroniza o progresso com o GitHub
                    exportar_json(CAMINHO_DB, CAMINHO_JSON)
                    if not sem_upload:
                        print(f"\n☁️ [Loja {nome_loja}] Sincronizando progresso intermediário com o GitHub...")
                        upload_db_to_github(GITHUB_TOKEN, REPO, CAMINHO_DB, "estoque_bigmais.db")
                        upload_db_to_github(GITHUB_TOKEN, REPO, CAMINHO_JSON, "estoque_bigmais.json")

                except Exception:
                    pass

        conn.close()
        exportar_json(CAMINHO_DB, CAMINHO_JSON)
        print(f"\n✨ Coleta concluída com sucesso! Total de registros gravados: {itens_coletados}")

        if not sem_upload:
            upload_db_to_github(GITHUB_TOKEN, REPO, CAMINHO_DB, "estoque_bigmais.db")
            upload_db_to_github(GITHUB_TOKEN, REPO, CAMINHO_JSON, "estoque_bigmais.json")
        else:
            print(f"ℹ️ Upload desativado via parâmetro (--sem-upload). Banco salvo em: {CAMINHO_DB}")

    except Exception as e:
        print(f"\n❌ Erro durante a execução: {type(e).__name__} - {e}", flush=True)
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coletor de Estoque Big Mais - Versão Desktop")
    parser.add_argument("--visivel", action="store_true", help="Executa o Chrome de forma visível na tela")
    parser.add_argument("--limite", type=int, default=None, help="Limita a quantidade de produtos para testar (ex: --limite 5)")
    parser.add_argument("--loja", type=str, default=None, help="Filtra por nome de uma loja específica")
    parser.add_argument("--sem-upload", action="store_true", help="Não faz o upload automático para o GitHub ao final")
    args = parser.parse_args()

    executar_coleta(
        visivel=args.visivel,
        limite=args.limite,
        loja_especifica=args.loja,
        sem_upload=args.sem_upload
    )
