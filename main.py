import os
import re
import sys
import sqlite3
import time
from datetime import datetime, timezone, timedelta, time as dtime, date

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ==========================================
# ⏰ Controle de Janela de Horário (Horário de Brasília - UTC-3)
# ==========================================
FUSO_BR = timezone(timedelta(hours=-3))
HORA_INICIO = dtime(4, 59)
HORA_FIM = dtime(22, 0)

# ==========================================
# Configurações e Credenciais Seguras
# ==========================================
USUARIO = (os.getenv("SISTEMA_LOGIN") or "").strip() or "samuel.silva"
SENHA = (os.getenv("SISTEMA_SENHA") or "").strip() or "9888"
URL = "https://bigmais.dext.com.br/dxt_com/dxt_con_prd/index.php?menu_ativo=6&aplic_ativa=3"
CAMINHO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estoque_bigmais.db")

try:
    from produtos_catalogo import PRODUTOS_CANONICOS, CODIGOS_PRODUTOS, classificar_curva_produto, CODIGOS_CURVA_A
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from produtos_catalogo import PRODUTOS_CANONICOS, CODIGOS_PRODUTOS, classificar_curva_produto, CODIGOS_CURVA_A


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


def exportar_json(caminho_db, caminho_json="estoque_bigmais.json"):
    import json
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
                elif 100 <= abs(raw_est) < 1000 and int(raw_est) == raw_est:
                    raw_est = raw_est / 100.0
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

# ==========================================
# Configuração Headless para o Servidor Linux
# ==========================================
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

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
                elif dias_venda > 7:
                    score += 500 # Auditoria de veracidade: revisa com urgência dados antigos/equivocados!

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


def executar_automacao():
    agora_br = datetime.now(FUSO_BR)
    hora_atual = agora_br.time()

    if hora_atual > HORA_FIM or hora_atual < HORA_INICIO:
        print(f"⏸️ Horário atual ({agora_br.strftime('%H:%M:%S')} BRT) fora da janela permitida.")
        print("A automação fica pausada entre 22:00 e 04:59 AM. Retornará automaticamente às 04:59.")
        return

    DATA_HOJE = agora_br.strftime("%Y-%m-%d")

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

                    produtos_ordenados = ordenar_produtos_por_prioridade(conn, nome_loja, CODIGOS_PRODUTOS)
                    for codigo_produto in produtos_ordenados:
                        barra.set_postfix_str(f"Loja: {nome_loja} | Cód: {codigo_produto}")
                        try:
                            # 1. Dispara busca Jaxon do produto
                            driver.execute_script(f"jaxon_fn_buscaprodutolist('{codigo_produto}', 'idcod_produto', 'PRD');")

                            # 2. Aguarda a linha correspondente ao código aparecer na tabela (máx 3s)
                            achou_linha = False
                            ondbl = None
                            desc_tabela = ""
                            est_tabela = ""
                            for _ in range(15):
                                time.sleep(0.2)
                                res_linha = driver.execute_script("""
                                    const cod = arguments[0];
                                    const trs = Array.from(document.querySelectorAll('table.displayRelatorios tbody tr'));
                                    for (let r of trs) {
                                        const celulas = r.querySelectorAll('td, th');
                                        if (celulas.length >= 5) {
                                            const codLinha = (celulas[1].innerText || '').trim();
                                            if (codLinha === cod || r.innerText.includes(cod)) {
                                                return {
                                                    ondbl: r.getAttribute('ondblclick') || '',
                                                    desc: celulas[3].innerText.trim(),
                                                    estoque: celulas[4].innerText.trim()
                                                };
                                            }
                                        }
                                    }
                                    return null;
                                """, codigo_produto)
                                if res_linha and res_linha.get('ondbl'):
                                    achou_linha = True
                                    ondbl = res_linha['ondbl']
                                    desc_tabela = res_linha['desc']
                                    est_tabela = res_linha['estoque']
                                    break

                            if achou_linha and ondbl:
                                # 3. Dispara a requisição Jaxon de montagem dos dados comerciais
                                driver.execute_script(ondbl)

                                # 4. Aguarda o painel ser atualizado para o código deste produto específico
                                for _ in range(15):
                                    time.sleep(0.2)
                                    carregou = driver.execute_script("""
                                        const cod = arguments[0];
                                        const p = document.getElementById('idclearpainel');
                                        if (!p) return false;
                                        const txt = p.innerText || '';
                                        return txt.includes(cod + ' - ') && (txt.includes('Data Ult Venda') || txt.includes('Custo'));
                                    """, codigo_produto)
                                    if carregou:
                                        break

                                # 5. Extrai dados comerciais reais diretamente de #idclearpainel
                                dados = driver.execute_script("""
                                    const p = document.getElementById('idclearpainel');
                                    function normalizar(t) {
                                        return (t || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').trim().replace(/\\s+/g, ' ');
                                    }
                                    const todos = Array.from(p.querySelectorAll('th, td, strong, label, b, div, span, p'));
                                    function extrair(rotulo) {
                                        const rNorm = normalizar(rotulo);
                                        for (let el of todos) {
                                            if (normalizar(el.innerText) === rNorm) {
                                                if (el.nextElementSibling && el.nextElementSibling.innerText.trim()) {
                                                    return el.nextElementSibling.innerText.trim();
                                                }
                                            }
                                        }
                                        return '';
                                    }
                                    let precoVenda = '';
                                    for (let el of todos) {
                                        const t = el.innerText.trim();
                                        if (/^(UN|KG|BDJ|CX|PCT|MC|DZ)\\s*1$/i.test(t)) {
                                            if (el.nextElementSibling && el.nextElementSibling.innerText) {
                                                precoVenda = el.nextElementSibling.innerText.trim();
                                                break;
                                            }
                                        }
                                    }
                                    return {
                                        custo_liquido: extrair('Custo Líquido') || extrair('Custo Liquido') || extrair('Custo Bruto'),
                                        preco_venda: precoVenda,
                                        data_ult_venda: extrair('Data Ult Venda'),
                                        data_ult_compra: extrair('Data Ult Compra'),
                                        dias_estoque: extrair('Dias de Estoque'),
                                        idade_estoque: extrair('Idade Estoque'),
                                        margem_pdv: extrair('Val. Margem PDV')
                                    };
                                """)

                                # Normaliza estoque
                                tEst = est_tabela
                                if ',' in tEst and '.' in tEst:
                                    if tEst.rfind(',') > tEst.rfind('.'):
                                        tEst = tEst.replace('.', '').replace(',', '.')
                                    else:
                                        tEst = tEst.replace(',', '')
                                elif ',' in tEst:
                                    tEst = tEst.replace(',', '.')

                                try:
                                    estoque_num = float(tEst)
                                except Exception:
                                    estoque_num = 0.0

                                if re.search(r'\b(KG|QUILO|KILO)\b', desc_tabela, re.I) and not re.search(r'\b\d+\s*KG\b', desc_tabela, re.I):
                                    if (abs(estoque_num) >= 1000 and int(estoque_num) == estoque_num) or abs(estoque_num) >= 10000:
                                        estoque_num = estoque_num / 1000.0
                                    elif 100 <= abs(estoque_num) < 1000 and int(estoque_num) == estoque_num:
                                        estoque_num = estoque_num / 100.0

                                descricao = limpar_texto(desc_tabela) or PRODUTOS_CANONICOS.get(codigo_produto, f"PRODUTO {codigo_produto}")
                                estoque = round(float(estoque_num), 3)
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
                                estoque = 0.0
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
                            if barra.n % 5 == 0:
                                exportar_json(CAMINHO_DB, "estoque_bigmais.json")
                        except Exception:
                            pass

                        barra.update(1)

                    exportar_json(CAMINHO_DB, "estoque_bigmais.json")
                except Exception:
                    pass

        conn.close()
        exportar_json(CAMINHO_DB, "estoque_bigmais.json")
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

if __name__ == '__main__':
    executar_automacao()

