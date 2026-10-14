# 🤖 Coleta Automática de Estoque — Big Mais

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-Headless-green?style=flat-square&logo=selenium)](https://www.selenium.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-07405E?style=flat-square&logo=sqlite)](https://www.sqlite.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated_Cron-2088FF?style=flat-square&logo=github-actions)](https://github.com/features/actions)

> Automação em Python desenvolvida para monitorar e extrair periodicamente posições de estoque de produtos em sistemas legados (Dext), persistindo o histórico em um banco SQLite de forma 100% autônoma via GitHub Actions.

---

## ⚙️ Arquitetura e Funcionamento

1. **Agendamento em Nuvem (CI/CD)**: O GitHub Actions dispara o fluxo a cada 30 minutos via **cron** sem necessidade de servidor local dedicado.
2. **Navegação Headless**: Inicialização automatizada do Google Chrome em modo headless com Selenium.
3. **Autenticação Segura**: Login automatizado consumindo credenciais criptografadas via GitHub Secrets.
4. **Varredura Multi-loja**: Itera por todas as lojas cadastradas, consultando códigos de produtos pré-definidos.
5. **Persistência**: Gravação estruturada dos dados na tabela `estoque_atual` do banco `estoque_bigmais.db`.
6. **Auto-commit**: O workflow do GitHub Actions comita o banco atualizado de volta no repositório com as novas coletas.

---

## 🔐 Configuração de Variáveis de Ambiente (GitHub Secrets)

Para execução segura sem expor senhas no código-fonte, configure em seu repositório:
**Settings > Secrets and variables > Actions > New repository secret**:

- `SISTEMA_LOGIN`: Usuário de acesso ao sistema
- `SISTEMA_SENHA`: Senha de acesso ao sistema

---

## 🛠️ Execução Local

### Pré-requisitos
- Python 3.10+
- Google Chrome instalado

### Passo a Passo

```bash
# Clone o repositório
git clone https://github.com/saaesilva/estoque-bigmais-automacao.git
cd estoque-bigmais-automacao

# Crie e ative um ambiente virtual
python -m venv venv
# No Windows:
.\venv\Scripts\activate

# Instale os requisitos
pip install -r requirements.txt

# Defina as variáveis de ambiente e execute
$env:SISTEMA_LOGIN="seu_usuario"
$env:SISTEMA_SENHA="sua_senha"
python main.py
```

---

## 👤 Autor

Desenvolvido por **[Samuel Silva](https://github.com/saaesilva)**.
