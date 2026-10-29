# doccheck

[![CI](https://github.com/TiagoR85/doccheck/actions/workflows/ci.yml/badge.svg)](https://github.com/TiagoR85/doccheck/actions/workflows/ci.yml)

Verifica se a **documentação e o código dizem a mesma coisa**.

Existe porque dois problemas diferentes passam despercebidos:

| Problema | Quem pega |
|---|---|
| doc **ausente** (página/versão desatualizada) | checagem estrutural |
| doc **presente e errada** (cita endpoint que não existe, versão que não é a do CHANGELOG) | checagem de fato |
| doc **certa mas incompleta** (não descreve o comportamento novo) | ninguém — é revisão |

## Instalação

```bash
pipx install git+https://github.com/TiagoR85/doccheck.git   # ou: pip install -e .
doccheck init      # cria .doccheck.json com a stack detectada
doccheck check     # roda as regras
doccheck install   # vendoriza em .githooks/ e ativa core.hooksPath
doccheck status    # painel de deriva: quais repos têm o vendor e em que versão
```

`install` copia o pacote para `.githooks/doccheck/` e escreve `.githooks/pre-commit`.
O repo fica **self-contained** (funciona offline, sem depender da ferramenta instalada);
para atualizar, rode `doccheck install` de novo. O hook é ~0,3 s.

`status` aponte para a pasta que guarda os repositórios e ele lê
`.githooks/doccheck/__init__.py` de cada um — sem rede, sem confiar em memória:

```bash
$ doccheck status D:\Projetos
   my-opencode-hub     0.3.1    em dia
!! repo-antigo         0.1.0    atrasado
-- repo-sem-vendor     -        ausente

instalada: 0.4.0 · em dia 31 · atrasado 1 · ausente 3 (de 35)
```

Sai 1 quando há `atrasado` ou `ausente` (serve de gate de release); `--json` para automação.

## Regras

| Regra | Falha quando |
|---|---|
| `readme` | sem `README.md` ou vazio |
| `secoes` | seção (`##`/`###`) sem conteúdo em qualquer `.md` |
| `versao` | versão/data do `STATUS.md` != topo do `CHANGELOG.md` (aceita changelog por data) |
| `segredos` | valor de `.env` (`*KEY*`, `*TOKEN*`, `*SECRET*`, `*PASS*`) ou padrão de token (`ghp_`, `github_pat_`, `sk-`, `AKIA`, `AIza`, `PRIVATE KEY`) em `.md` |
| `endpoints` | a **seção de API** cita `` `/rota` `` que não existe no código |

Princípio: **regra que não dá para avaliar é *pulada*, nunca falha.** Sem rotas no código,
sem seção de API, sem CHANGELOG+STATUS → `skipped`, saída 0. Falso positivo crônico ensina
a usar `--no-verify`, o que mata o mecanismo.

### Endpoints: só as rotas do próprio repo

A doc pode citar APIs de terceiros (OpenCode, GitHub...). Só cobramos rotas cujo prefixo
o código também define, e só dentro de seções cujo título contém `api`
(`"secao_api"` no `.doccheck.json`).

## Adaptadores

| Stack | Como detecta | O que lê |
|---|---|---|
| ASP.NET | `*.csproj` | `[Route]` + `[HttpGet/Post/...]`, minimal APIs `MapGet("...")` |
| Python web | `*.py` | Flask `Blueprint(url_prefix)` + `@route`; FastAPI `APIRouter(prefix)` + `@get` |
| Node | `package.json` com express/fastify/koa | `router.get(...)` + prefixos de `app.use(...)` |
| Astro | `src/pages/` | rotas de arquivo, `[slug]` → parâmetro |

Sem adaptador → a regra `endpoints` é pulada.

## Configuração (`.doccheck.json`)

```json
{
  "stack": null,
  "secao_api": "api",
  "status": null,
  "changelog": null,
  "regras": {"readme": true, "secoes": true, "versao": true,
             "segredos": true, "endpoints": true},
  "ignore": ["docs/plans/**", "docs/specs/**", "**/node_modules/**"]
}
```

Por padrão, `docs/plans/**` e `docs/specs/**` ficam de fora: são **snapshots congelados** —
um plano de 2026 pode citar arquivo que ainda não existia.

## Saída

```
$ doccheck check
- pulada: endpoints: nenhuma seção de API citando endpoints
[x] versao: STATUS.md: STATUS v1.2.2 != CHANGELOG.md v1.2.3
2 problema(s) de documentação (meu-projeto)
```

`--json` para uso em CI, `--nao-falhar` para relatório sem bloquear.

## Revisão semântica (`doccheck review`)

Fora do hook, opt-in. **Sem** `--ia`, monta o contexto determinístico e imprime: diff
desde `--ref`, os `.md` afetados, recortes de código e os achados do check. Com `--ia`,
envia esse contexto a um endpoint **OpenAI-compatível** e devolve **perguntas com
`arquivo:linha`** — nunca um patch, nunca um bloqueio.

```bash
export DOCCHECK_IA_URL=https://api.openai.com/v1   # também Groq, DeepSeek, Ollama, OpenRouter
export DOCCHECK_IA_KEY=...
export DOCCHECK_IA_MODEL=gpt-4o-mini               # default
export DOCCHECK_IA_PRECO_IN=0.15  DOCCHECK_IA_PRECO_OUT=0.60   # US$/1M (opcional)

doccheck review --ia --ref HEAD~3 --max-usd 0.20
doccheck review --json | jq -r .contexto          # levar o contexto a outro modelo
```

- **Não é o gate.** O hook continua determinístico e offline; `review` roda quando você quer.
- `--max-usd` aborta **antes** de enviar quando a estimativa passa o teto.
- Sem `DOCCHECK_IA_URL` sai 0 e diz que pulou — o contexto continua em `--json`.
- Saída `--json`: `contexto`, `resposta`, `uso` (tokens), `custo_usd` e `codigo`.
- **O contexto inclui código**, não só o diff: até 6 recortes de 4000 caracteres —
  caminhos que a doc **cita**, **pontos de entrada** (`docker-compose.yml`, `Program.cs`,
  `index.html`, `app.py`, `Dockerfile`, `package.json`...) e arquivos **alterados
  recentemente**. Foi isso que fechou o cenário B (doc mentindo sozinha).
- **Limite medido em 3 repos reais**, cada um no estado *pré-auditoria* e com diff vazio:
  vendas-desapego **3/3** dos achados manuais, interview-assistant **1/1** (parcial),
  youtube-gemini-pipeline **0/2** — contagem de testes e mensagem de erro específica no
  meio de um arquivo grande não são verificáveis com recorte de 4000 caracteres. Números e
  amostras em [docs/engenharia.md](docs/engenharia.md).
- **DeepSeek**: `DOCCHECK_IA_URL=https://api.deepseek.com` e `DOCCHECK_IA_MODEL=deepseek-flash`.
  Com contexto grande o provedor pode passar de 60s — o timeout é de 180s.

## Limites (honestos)

- Não julga **semântica**: um texto pode estar errado e o endpoint existir.
- Chamada de endpoint existe ≠ contrato igual (payload, status).
- `.env` de produção não é lido; só o do repo.

O registro de engenharia — o experimento que falhou, os bugs de parsing que só apareceram
em repositórios reais e por que o gate pula em vez de falhar — está em
[docs/engenharia.md](docs/engenharia.md).
