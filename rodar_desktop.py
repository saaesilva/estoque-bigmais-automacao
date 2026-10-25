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

def exportar_json(caminho_db, caminho_json):
    try:
        conn = sqlite3.connect(caminho_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM estoque_atual ORDER BY loja, codigo").fetchall()
        lista = []
        for r in rows:
            data_venda = r['data_ult_venda'] or ""
            idade = r['idade_estoque'] or ""
            dias_sem_venda = None
            if data_venda:
                m = re.search(r'\(?\s*(\d+)\s*Dias?\s*\)?', data_venda, re.I)
                if m:
                    dias_sem_venda = int(m.group(1))
            if dias_sem_venda is None and idade:
                m = re.search(r'(\d+)\s*Dias?', idade, re.I)
                if m:
                    dias_sem_venda = int(m.group(1))
            
            dias_str = "S/ Venda" if dias_sem_venda is None else ("Hoje (0 dias)" if dias_sem_venda == 0 else f"{dias_sem_venda} dias")
            data_compra = r['data_ult_compra'] or ""
            m_compra = re.search(r'(\d{2}/\d{2}/\d{4})', data_compra)
            m_compra_dias = re.search(r'\(?\s*(\d+)\s*Dias?\s*\)?', data_compra, re.I)
            ult_compra_str = "-"
            if m_compra:
                ult_compra_str = f"{m_compra.group(1)} ({m_compra_dias.group(1)}d)" if m_compra_dias else m_compra.group(1)

            margem_val = r['margem_pdv']
            margem_str = f"{float(margem_val):.1f}%" if margem_val is not None else "-"

            lista.append({
                "loja": r['loja'] or "",
                "codigo": str(r['codigo'] or "").strip(),
                "descricao": (r['descricao'] or "").strip(),
                "nome": (r['descricao'] or "").strip(),
                "estoque": int(r['estoque'] or 0),
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

# Lista oficial de 278 produtos
CODIGOS_PRODUTOS = [
    "9542", "9546", "9552", "9566", "14160", "9573", "9578", "24098", "19906", "9658",
    "9760", "9764", "7925", "1937", "9832", "9809", "9812", "9823", "9825", "40980",
    "9861", "9867", "26122", "26123", "9872", "9876", "9879", "7888", "9884", "9887",
    "9892", "41003", "9904", "9922", "37494", "14177", "9927", "42070", "22830", "9960",
    "9964", "9971", "10097", "10102", "10105", "31131", "10107", "10110", "39323", "37495",
    "604", "10177", "10222", "10266", "10225", "10244", "10251", "25933", "10397", "10409",
    "43752", "602", "10474", "25858", "37253", "10560", "10570", "40828", "10610", "35044",
    "43666", "10638", "41544", "41543", "10781", "10786", "10797", "14892", "10803", "10871",
    "10932", "10878", "43753", "601", "966", "10985", "11013", "16204", "11018", "11030",
    "11045", "11050", "36667", "11209", "920", "11190", "11646", "11639", "35033", "11715",
    "11765", "36866", "40171", "41550", "41553", "41552", "41554", "9926", "9930", "9935",
    "9942", "10088", "10104", "603", "24456", "10937", "11025", "11036", "11043", "11065",
    "22", "11093", "11346", "11350", "30611", "11638", "39769", "11741", "11746", "25694",
    "11752", "11756", "610", "11789", "3256", "11794", "39107", "34808", "11816", "9743",
    "9986", "664", "26602", "38509", "10216", "10194", "10199", "3013", "24845", "43844",
    "10233", "10239", "10247", "10262", "10270", "10305", "36569", "10320", "33509", "28113",
    "32549", "24951", "10347", "10351", "10363", "10517", "15482", "14256", "10894", "42180",
    "10910", "14979", "14261", "10917", "10927", "26262", "36577", "28611", "36642", "36643",
    "38496", "19956", "11000", "11021", "26874", "11087", "25650", "33488", "43039", "11395",
    "27348", "11400", "11406", "11502", "11505", "926", "11516", "11524", "11537", "11612",
    "15483", "38604", "11690", "11822", "11823", "11826", "11829", "37981", "11838", "11867",
    "11894", "11315", "11518", "27347", "11550", "11553", "10869", "919", "589", "10873",
    "11048", "14978", "35041", "11080", "11084", "931", "27431", "26113", "17684", "609",
    "30587", "1930", "4626", "10825", "10827", "25855", "10840", "1137", "5990", "1139",
    "7892", "4728", "1045", "7130", "3116", "35302", "38741", "20459", "1144", "1147",
    "11562", "11601", "15030", "18265", "18266", "18269", "18267", "21226", "43014", "41549",
    "41548", "27533", "11644", "11650", "43754", "11427", "27534", "24105", "11444", "11666",
    "41060", "11772", "11776", "11791", "924", "11805", "34487", "11916"
]

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

                    for codigo_produto in produtos_para_coletar:
                        barra.set_postfix_str(f"{nome_loja[:12]} | Cód: {codigo_produto}")
                        try:
                            # Fecha eventuais modais
                            driver.execute_script("""
                                const modais = document.querySelectorAll('.modal.in, .modal.show');
                                for (let m of modais) {
                                    const btnClose = m.querySelector('[data-dismiss="modal"], .close');
                                    if (btnClose) btnClose.click();
                                }
                            """)
                            time.sleep(0.2)

                            campo = wait.until(EC.element_to_be_clickable((By.ID, "idfiltrolistaproduto")))
                            campo.clear()
                            campo.send_keys(codigo_produto)
                            driver.find_element(By.XPATH, "//button[contains(@onclick, 'jaxon_fn_buscaprodutolist') and contains(text(), 'Cod. Produto')]").click()

                            time.sleep(1.2)

                            # Abre os painéis do produto com duplo clique
                            driver.execute_script("""
                                const linha = document.querySelector('tr[ondblclick*="jaxon_fn_setbuscaproduto"], table.displayRelatorios tbody tr');
                                if (linha && linha.getAttribute('ondblclick')) eval(linha.getAttribute('ondblclick'));
                            """)
                            time.sleep(1.5)

                            # Extrai dados do DOM
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

                                const linha = document.querySelector('tr[ondblclick*="jaxon_fn_setbuscaproduto"], table.displayRelatorios tbody tr');
                                if (linha) {
                                    const celulas = linha.querySelectorAll('td, th');
                                    if (celulas.length >= 5) {
                                        descricao = celulas[3].innerText.trim();
                                        estoque = Number(celulas[4].innerText.trim().replace(/\\./g, '').replace(',', '.')) || 0;
                                    }
                                }

                                function extrairValor(rotulo) {
                                    const rotuloNorm = normalizar(rotulo);
                                    const elementos = Array.from(document.querySelectorAll('th, td'));
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
                                const ths = Array.from(document.querySelectorAll('th'));
                                for (let th of ths) {
                                    if (th.innerText && th.innerText.trim() === 'UN 1') {
                                        if (th.nextElementSibling && th.nextElementSibling.innerText) {
                                            precoVenda = th.nextElementSibling.innerText.trim();
                                            break;
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
                            """)

                            preco_venda = limpar_valor_numerico(dados.get("preco_venda"))
                            custo_liquido = limpar_valor_numerico(dados.get("custo_liquido"))
                            margem_pdv = limpar_valor_numerico(dados.get("margem_pdv"))
                            dias_estoque = limpar_valor_numerico(dados.get("dias_estoque"))
                            data_ult_compra = limpar_texto(dados.get("data_ult_compra"))
                            data_ult_venda = limpar_texto(dados.get("data_ult_venda"))
                            idade_estoque = limpar_texto(dados.get("idade_estoque"))
                            descricao = limpar_texto(dados.get("descricao")) or f"PRODUTO {codigo_produto}"
                            estoque = int(dados.get("estoque") or 0)

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
                        except Exception:
                            pass

                        barra.update(1)
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
