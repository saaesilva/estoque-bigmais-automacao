import os
import sqlite3
import time
from datetime import date
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# Configurações e Credenciais Seguras
# ==========================================
USUARIO = os.getenv("SISTEMA_LOGIN", "samuel.silva")
SENHA = os.getenv("SISTEMA_SENHA", "9888")
URL = "https://bigmais.dext.com.br/dxt_com/dxt_con_prd/index.php?menu_ativo=6&aplic_ativa=3"
CAMINHO_DB = "estoque_bigmais.db"
DATA_HOJE = date.today().strftime("%Y-%m-%d")

CODIGOS_PRODUTOS = [
    "9658", "9764", "9832", "9809", "9823", "9825", "9884", "41003",
    "9904", "9971", "10560", "10570", "10871", "11018", "11190", "11765",
    "10088", "9781", "10517", "11518", "11084", "10825", "10827", "11601", "11666"
]

# ==========================================
# Configuração Headless para o Servidor Linux
# ==========================================
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

try:
    print("🔐 Realizando login no sistema...")
    driver.get(URL)
    wait.until(EC.presence_of_element_located((By.ID, "login"))).send_keys(USUARIO)
    driver.find_element(By.ID, "password").send_keys(SENHA)

    try:
        driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']").click()
    except Exception:
        driver.find_element(By.ID, "password").send_keys(Keys.RETURN)

    time.sleep(2)
    print("✅ Login efetuado com sucesso!\n")

    # ==========================================
    # Banco de Dados Local
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
            data_coleta TEXT,
            UNIQUE(loja, codigo)
        )
    """)
    conn.commit()

    # ==========================================
    # Captura de Lojas
    # ==========================================
    driver.get(URL)
    time.sleep(1.5)
    driver.find_element(By.CSS_SELECTOR, "button.dropdown-toggle, div.dropdown button").click()

    elementos_lojas = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.dropdown-menu.inner span.text"))
    )
    lista_lojas = [el.text.strip() for el in elementos_lojas if el.text.strip() and el.text.strip() != "Selecione"]
    print(f"🏢 Lojas encontradas: {len(lista_lojas)} unidades\n")

    # ==========================================
    # Varredura de Estoque
    # ==========================================
    total_etapas = len(lista_lojas) * len(CODIGOS_PRODUTOS)
    print("🚀 Iniciando varredura acelerada de estoque...")

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
                        campo = wait.until(EC.presence_of_element_located((By.ID, "idfiltrolistaproduto")))
                        campo.clear()
                        campo.send_keys(codigo_produto)
                        driver.find_element(By.XPATH, "//button[contains(@onclick, 'jaxon_fn_buscaprodutolist') and contains(text(), 'Cod. Produto')]").click()

                        time.sleep(1.2)

                        dados = driver.execute_script("""
                            const linhas = document.querySelectorAll('table.displayRelatorios tbody tr, tr[ondblclick*="jaxon_fn_setbuscaproduto"]');
                            for (let linha of linhas) {
                                const celulas = linha.querySelectorAll('td, th');
                                if (celulas.length >= 5) {
                                    return {
                                        descricao: celulas[3].innerText.trim(),
                                        estoque: Number(celulas[4].innerText.trim().replace('.', '').replace(',', '.')) || 0
                                    };
                                }
                            }
                            return { descricao: "PRODUTO " + arguments[0], estoque: 0 };
                        """, codigo_produto)

                        cursor.execute("""
                            INSERT OR REPLACE INTO estoque_atual (loja, codigo, descricao, estoque, data_coleta)
                            VALUES (?, ?, ?, ?, ?)
                        """, (nome_loja, codigo_produto, dados["descricao"], dados["estoque"], DATA_HOJE))
                        conn.commit()
                    except Exception:
                        pass

                    barra.update(1)
            except Exception:
                pass

    conn.close()
    print("\n✨ Atualização de estoque concluída com sucesso!")

except Exception as e:
    print(f"\n❌ Erro durante a execução: {e}")
    raise e

finally:
    driver.quit()
