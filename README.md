# Coleta Automática de Estoque - Big Mais

Automação periódica com Python, Selenium Headless e GitHub Actions para consulta e persistência de dados de estoque e indicadores comerciais do sistema Dext em um banco de dados SQLite (`estoque_bigmais.db`).

## ⚙️ Como Funciona
- **Agendamento Inteligente:** O GitHub Actions executa periodicamente entre **04:59 AM e 22:00 PM** (Horário de Brasília). A automação para após as 22:00 e retorna às 04:59.
- **Navegação Headless:** Login automatizado consumindo credenciais criptografadas via GitHub Secrets.
- **Varredura Multi-loja:** Varre todas as lojas cadastradas e pesquisa a lista com 278 códigos de produtos.
- **Extração Completa:** Coleta posição de estoque e indicadores detalhados:
  - `preco_venda` (UN 1)
  - `custo_liquido` (Custo Líquido)
  - `margem_pdv` (Val. Margem PDV)
  - `dias_estoque` (Dias de Estoque)
  - `data_ult_compra` (Data Última Compra)
  - `data_ult_venda` (Data Última Venda)
  - `idade_estoque` (Idade Estoque)
- **Persistência Estruturada:** Atualiza ou insere na tabela `estoque_atual` do SQLite.
- **Auto-commit:** O GitHub Actions faz commit automático do arquivo `estoque_bigmais.db` atualizado de volta no repositório.

## 🗄️ Estrutura da Tabela `estoque_atual`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER | Identificador auto-incremental |
| `loja` | TEXT | Nome da unidade/loja |
| `codigo` | TEXT | Código do produto |
| `descricao` | TEXT | Descrição do item |
| `estoque` | INTEGER | Quantidade física atual |
| `preco_venda` | REAL | Preço unitário de venda (UN 1) |
| `custo_liquido` | REAL | Custo líquido do item (R$) |
| `margem_pdv` | REAL | Percentual de Margem PDV (%) |
| `dias_estoque` | REAL | Giro / Dias de cobertura de estoque |
| `data_ult_compra` | TEXT | Data e intervalo da última compra |
| `data_ult_venda` | TEXT | Data da última venda |
| `idade_estoque` | TEXT | Tempo de permanência do estoque |
| `data_coleta` | TEXT | Data da última sincronização (`YYYY-MM-DD`) |

## 🔒 Variáveis Secretas (GitHub Secrets)
Configuradas em **Settings > Secrets and variables > Actions > New repository secret**:
- `SISTEMA_LOGIN`: Usuário de acesso ao sistema.
- `SISTEMA_SENHA`: Senha de acesso ao sistema.
