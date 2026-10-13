# Coleta Automática de Estoque - Big Mais

Automação que consulta periodicamente o estoque dos produtos no sistema Dext e persiste os dados em um banco de dados SQLite (`estoque_bigmais.db`).

## ⚙️ Como Funciona
- O GitHub Actions executa o script a cada 30 minutos via **cron**.
- O script loga no sistema com Google Chrome Headless.
- Varre todas as lojas cadastradas e pesquisa a lista de códigos de produtos.
- Salva os dados na tabela `estoque_atual` do SQLite.
- O GitHub Actions faz commit automático do arquivo `estoque_bigmais.db` atualizado de volta no repositório.

## 🔒 Variáveis Secretas (GitHub Secrets)
Para não expor usuário e senha no código, configure em:
**Settings > Secrets and variables > Actions > New repository secret**:
- `SISTEMA_LOGIN`: seu usuário de acesso.
- `SISTEMA_SENHA`: sua senha de acesso.
