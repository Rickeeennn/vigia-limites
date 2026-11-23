# Vigia de limites — OneDrive → validação → JSON → GitHub (100% na nuvem)

```
 PO salva tanques.dw no OneDrive
              │
   a cada 5 min (GitHub Actions)
              │
   transpilador.py ── lê pelo Microsoft Graph
              │
   dw.jar --json ── validador oficial da linguagem .dw
              │
     ┌────────┴────────┐
  inválido           válido
     │                 │
 RELATORIO_ERRO_*.txt  config/limites.json (versao N)
 na mesma pasta        commit + tag limites-vN
 do OneDrive           no repositório de dados
```

## Por que dois repositórios?
O GitHub Actions é **ilimitado e gratuito só em repositório público**. No privado, o plano Free
tem 2.000 min/mês, e rodar a cada 5 minutos consome cerca de 8.600 min/mês.

| Repositório | Visibilidade | Conteúdo |
|---|---|---|
| `vigia-limites` | **público** | este código + workflow (nenhum dado) |
| `limites-dados` | privado ou público | só o `config/limites.json` versionado |

Os segredos ficam nos *Secrets* do repositório público, que não aparecem nos logs nem em forks.
O script nunca imprime o conteúdo do arquivo do PO no log.
Se os limites puderem ser públicos, use um único repositório público e aponte `DESTINO_REPO` para ele mesmo.

---

## Passo a passo (uma vez só, uns 20 minutos)

### 0. Ter um diretório (tenant) do Microsoft Entra — pré-requisito
Desde junho de 2024, uma conta pessoal da Microsoft sozinha não consegue mais registrar apps:
o app precisa ficar dentro de um diretório. O jeito gratuito de ganhar um:
- **Azure for Students** (https://azure.microsoft.com/free/students): sem cartão de crédito,
  só com verificação pelo e-mail da faculdade. Entre com a sua **conta pessoal da Microsoft**
  e use o e-mail acadêmico apenas para a verificação. Se entrar com a conta institucional,
  o app fica no diretório da faculdade, que pode bloquear o registro.
- Alternativa: a conta gratuita padrão do Azure, que pede cartão só para verificação de identidade.

Registrar o app não consome créditos: o Microsoft Entra ID Free já vem com o diretório.

### 1. Registrar o app na Microsoft (gratuito)
1. Acesse https://entra.microsoft.com (no diretório criado no passo 0) → **Aplicativos** →
   **Registros de aplicativo** → **Novo registro**.
2. Nome: `vigia-limites`. Tipos de conta: **Somente contas pessoais da Microsoft**.
   É essa opção que permite o login com a conta do seu OneDrive pessoal.
3. Depois de criar: **Autenticação** → **Permitir fluxos de clientes públicos = Sim** → Salvar.
4. **Permissões de API** → Microsoft Graph → *Delegadas* → `Files.ReadWrite` e `offline_access`.
5. Copie o **ID do aplicativo (cliente)**. <-  ->

### 2. Gerar o refresh token
Em um GitHub Codespace, no Google Colab ou em qualquer Python:
```
python autorizar.py SEU_CLIENT_ID
```
Abra o link, digite o código e entre com a conta **dona da pasta** do OneDrive. Copie o token impresso.

### 3. Criar os repositórios no GitHub
- `limites-dados` (privado): crie com um README para ele não ficar vazio.
- `vigia-limites` (público): suba todos os arquivos desta pasta.

### 4. Criar o token do GitHub (`GH_PAT`)
GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token:
- Repository access: `vigia-limites` e `limites-dados`
- Permissões: **Contents: Read and write** e **Secrets: Read and write**
- Validade: a maior permitida. Anote quando vence.

### 5. Configurar o `vigia-limites` → Settings → Secrets and variables → Actions
**Secrets**

| Nome | Valor |
|---|---|
| `MS_CLIENT_ID` | ID do app (passo 1) |
| `MS_REFRESH_TOKEN` | token gerado no passo 2 |
| `GH_PAT` | token do passo 4 |

**Variables**

| Nome | Exemplo |
|---|---|
| `DESTINO_REPO` | `seu-usuario/limites-dados` |
| `ONEDRIVE_PASTA` | `Limites` (caminho a partir da raiz do OneDrive) |
| `ONEDRIVE_ARQUIVO` | `tanques.dw` |
| `DESTINO_ARQUIVO` | `config/limites.json` |
| `MS_TENANT` | `consumers` (pessoal) ou `organizations` (corporativo) |

### 6. Testar
Aba **Actions** → *Vigia de limites* → **Run workflow**. Confira o log e o repositório `limites-dados`.

### 7. (Recomendado) Pontualidade com o cron-job.org
O `schedule` do GitHub costuma atrasar de 5 a 30 minutos em horários de pico e é desativado
depois de 60 dias sem commits no repositório. Para garantir os 5 minutos:
1. Crie uma conta gratuita em https://cron-job.org
2. Novo job a cada 5 min: `POST https://api.github.com/repos/SEU_USUARIO/vigia-limites/actions/workflows/vigia.yml/dispatches`
   - Headers: `Authorization: Bearer <token só com Actions: write no vigia-limites>`,
     `Accept: application/vnd.github+json`
   - Body: `{"ref":"main"}`
3. Depois de confirmar que funciona, pode remover o bloco `schedule:` do `vigia.yml`.

---

## Linguagem `.dw` (o que o PO edita)
O PO edita `tanques.dw` no OneDrive, pelo navegador, pelo Bloco de Notas ou por qualquer outro editor:
```
Todos os tanques:
VazaoMin: 200
NivelMax: 90

Tanque 2        # vence o "Todos"
NivelMax: 100
```
A especificação completa está em `dw/README.md`.

**As regras da linguagem ficam só no Java** (`dw/src`). O workflow compila o `dw.jar` a cada
execução e o vigia chama `java -jar dw.jar arquivo.dw --json`:
- código de saída `0`: o JSON gerado pelo jar vai para o campo `limites` do `limites.json`;
- código de saída `1`: as mensagens do jar (com o número da linha) vão para o relatório no OneDrive.

Para criar um limite novo, basta uma linha em `dw/src/dw/Parametro.java`; o vigia não muda.
Arquivos salvos em ANSI (Bloco de Notas antigo) são convertidos para UTF-8 antes da validação.

### JSON publicado (`config/limites.json`)
```json
{
  "versao": 2,
  "gerado_em": "2026-11-16T21:23:05-03:00",
  "origem": "OneDrive:/Limites/tanques.dw",
  "hash_origem": "e74f…",
  "limites": {
    "todos":   {"VazaoMin": 150},
    "tanques": {"3": {"VazaoMin": 150, "NivelMax": 80.5}}
  }
}
```
Em `tanques`, cada tanque já vem com a regra "tanque vence Todos" aplicada.

## Comportamento
- **Sem mudança**: não faz nada. A comparação é pelo hash com o último JSON publicado; não há estado guardado.
- **Inválido**: grava um relatório e não repete o mesmo relatório a cada 5 minutos.
- **Válido**: publica `versao` N+1 e a tag `limites-vN`, e apaga os relatórios de erro antigos.
- **Token da Microsoft**: renovado automaticamente a cada execução (validade de 90 dias contada do último uso).

## Teste local (sem OneDrive nem GitHub; precisa de Python 3.9+ e Java 17+)
```
python tests/teste_fluxo.py
```

## Estrutura
```
transpilador.py              vigia: OneDrive <-> dw.jar <-> GitHub
autorizar.py                 gera o refresh token da Microsoft (uma vez)
dw/                          linguagem .dw (código Java, exemplos e README)
.github/workflows/vigia.yml  agenda a cada 5 min, compila o dw.jar e roda o vigia
tests/teste_fluxo.py         teste ponta a ponta com OneDrive simulado
```
