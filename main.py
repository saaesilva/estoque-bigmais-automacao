import os
import re
import sys
import sqlite3
import time
from datetime import datetime, timezone, timedelta, time as dtime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ==========================================
# ⏰ Controle de Janela de Horário (Horário de Brasília - UTC-3)
# ==========================================
# A automação pausa após as 22:00 e só retorna às 04:59 AM
FUSO_BR = timezone(timedelta(hours=-3))
agora_br = datetime.now(FUSO_BR)
hora_atual = agora_br.time()

HORA_INICIO = dtime(4, 59)
HORA_FIM = dtime(22, 0)

if hora_atual > HORA_FIM or hora_atual < HORA_INICIO:
    print(f"⏸️ Horário atual ({agora_br.strftime('%H:%M:%S')} BRT) fora da janela permitida.")
    print("A automação fica pausada entre 22:00 e 04:59 AM. Retornará automaticamente às 04:59.")
    exit(0)

# ==========================================
# Configurações e Credenciais Seguras
# ==========================================
USUARIO = (os.getenv("SISTEMA_LOGIN") or "").strip() or "samuel.silva"
SENHA = (os.getenv("SISTEMA_SENHA") or "").strip() or "9888"
URL = "https://bigmais.dext.com.br/dxt_com/dxt_con_prd/index.php?menu_ativo=6&aplic_ativa=3"
CAMINHO_DB = "estoque_bigmais.db"
DATA_HOJE = agora_br.strftime("%Y-%m-%d")

# Lista completa de produtos atualizada (278 produtos)
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

# Funções utilitárias de limpeza
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

# ==========================================
# Configuração Headless para o Servidor Linux
# ==========================================
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = webdriver.ChromeOptions()
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
    print(f"📍 URL carregada: {driver.current_url} | Título: {driver.title}", flush=True)

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
    print(f"✅ Login efetuado! Página atual: {driver.current_url} | Título: {driver.title}\n", flush=True)

    # ==========================================
    # Banco de Dados Local & Migração de Colunas
    # ==========================================
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

    # Garante compatibilidade adicionando colunas caso a tabela já exista
    colunas_novas = [
        ("preco_venda", "REAL"),
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

    # ==========================================
    # Captura de Lojas
    # ==========================================
    driver.get(URL)
    time.sleep(2)
    print(f"🏢 Acessando consulta de produtos: {driver.current_url}", flush=True)

    botao_dropdown = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.dropdown-toggle, div.dropdown button")))
    botao_dropdown.click()

    elementos_lojas = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.dropdown-menu.inner span.text"))
    )
    lista_lojas = [el.text.strip() for el in elementos_lojas if el.text.strip() and el.text.strip() != "Selecione"]
    print(f"🏢 Lojas encontradas: {len(lista_lojas)} unidades: {lista_lojas}\n", flush=True)

    # ==========================================
    # Varredura de Estoque e Indicadores
    # ==========================================
    total_etapas = len(lista_lojas) * len(CODIGOS_PRODUTOS)
    print("🚀 Iniciando varredura acelerada de estoque e indicadores comerciais...", flush=True)

    with tqdm(total=total_etapas, desc="Progresso", unit="prod") as barra:
        for nome_loja in lista_lojas:
            try:
                driver.get(URL)
                time.sleep(1)
                driver.find_element(By.CSS_SELECTOR, "button.dropdown-toggle, div.dropdown button").click()
                time.sleep(0.3)
                driver.find_element(By.XPATH, f"//ul[contains(@class, 'dropdown-menu')]//span[@class='text' and text()='{nome_loja}']").click()
                time.sleep(1)

                for codigo_produto in CODIGOS_PRODUTOS:
                    barra.set_postfix_str(f"Loja: {nome_loja} | Cód: {codigo_produto}")
                    try:
                        # Fecha eventuais modais anteriores
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

                        # Dispara o duplo-clique para abrir os painéis completos do produto
                        driver.execute_script("""
                            const linha = document.querySelector('tr[ondblclick*="jaxon_fn_setbuscaproduto"], table.displayRelatorios tbody tr');
                            if (linha && linha.getAttribute('ondblclick')) eval(linha.getAttribute('ondblclick'));
                        """)
                        time.sleep(1.5)

                        # Extrai todos os dados estruturados do DOM
                        dados = driver.execute_script("""
                            function normalizar(t) {
                                return (t || '').toLowerCase().trim().replace(/\\s+/g, ' ');
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
                                margem_pdv: extrairValor('Val. Margem PDV'),
                                dias_estoque: extrairValor('Dias de Estoque'),
                                data_ult_compra: extrairValor('Data Ult Compra'),
                                data_ult_venda: extrairValor('Data Ult Venda'),
                                idade_estoque: extrairValor('Idade Estoque')
                            };
                        """)

                        preco_venda = limpar_valor_numerico(dados.get("preco_venda"))
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
                                preco_venda, margem_pdv, dias_estoque,
                                data_ult_compra, data_ult_venda, idade_estoque,
                                data_coleta
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            nome_loja, codigo_produto, descricao, estoque,
                            preco_venda, margem_pdv, dias_estoque,
                            data_ult_compra, data_ult_venda, idade_estoque,
                            DATA_HOJE
                        ))
                        conn.commit()
                    except Exception:
                        pass

                    barra.update(1)
            except Exception:
                pass

    conn.close()
    print("\n✨ Atualização de estoque e indicadores concluída com sucesso!", flush=True)

except Exception as e:
    print(f"\n❌ Erro durante a execução: {type(e).__name__} - {e}", flush=True)
    try:
        print(f"📍 URL final: {driver.current_url}", flush=True)
        print(f"📄 Título: {driver.title}", flush=True)
    except Exception:
        pass
    raise e

finally:
    driver.quit()
