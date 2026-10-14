# ðŸ¤– Coleta AutomÃ¡tica de Estoque â€” Big Mais

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-Headless-green?style=flat-square&logo=selenium)](https://www.selenium.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-07405E?style=flat-square&logo=sqlite)](https://www.sqlite.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated_Cron-2088FF?style=flat-square&logo=github-actions)](https://github.com/features/actions)

> AutomaÃ§Ã£o em Python desenvolvida para monitorar e extrair periodicamente posiÃ§Ãµes de estoque de produtos em sistemas legados (Dext), persistindo o histÃ³rico em um banco SQLite de forma 100% autÃ´noma via GitHub Actions.

---

## âš™ï¸ Arquitetura e Funcionamento

1. **Agendamento em Nuvem (CI/CD)**: O GitHub Actions dispara o fluxo a cada 30 minutos via **cron** sem necessidade de servidor local dedicado.
2. **NavegaÃ§Ã£o Headless**: InicializaÃ§Ã£o automatizada do Google Chrome em modo headless com Selenium.
3. **AutenticaÃ§Ã£o Segura**: Login automatizado consumindo credenciais criptografadas via GitHub Secrets.
4. **Varredura Multi-loja**: Itera por todas as lojas cadastradas, consultando cÃ³digos de produtos prÃ©-definidos.
5. **PersistÃªncia**: GravaÃ§Ã£o estruturada dos dados na tabela `estoque_atual` do banco `estoque_bigmais.db`.
6. **Auto-commit**: O workflow do GitHub Actions comita o banco atualizado de volta no repositÃ³rio com as novas coletas.

---

## ðŸ” ConfiguraÃ§Ã£o de VariÃ¡veis de Ambiente (GitHub Secrets)

Para execuÃ§Ã£o segura sem expor senhas no cÃ³digo-fonte, configure em seu repositÃ³rio:
**Settings > Secrets and variables > Actions > New repository secret**:

- `SISTEMA_LOGIN`: UsuÃ¡rio de acesso ao sistema
- `SISTEMA_SENHA`: Senha de acesso ao sistema

---

## ðŸ› ï¸ ExecuÃ§Ã£o Local

### PrÃ©-requisitos
- Python 3.10+
- Google Chrome instalado

### Passo a Passo

```bash
# Clone o repositÃ³rio
git clone https://github.com/saaesilva/estoque-bigmais-automacao.git
cd estoque-bigmais-automacao

# Crie e ative um ambiente virtual
python -m venv venv
# No Windows:
.\venv\Scripts\activate

# Instale os requisitos
pip install -r requirements.txt

# Defina as variÃ¡veis de ambiente e execute
$env:SISTEMA_LOGIN="seu_usuario"
$env:SISTEMA_SENHA="sua_senha"
python main.py
```

---

## ðŸ‘¤ Autor

Desenvolvido por **[Samuel Silva](https://github.com/saaesilva)**.