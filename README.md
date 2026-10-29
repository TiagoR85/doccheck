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
```

`install` copia o pacote para `.githooks/doccheck/` e escreve `.githooks/pre-commit`.
O repo fica **self-contained** (funciona offline, sem depender da ferramenta instalada);
para atualizar, rode `doccheck install` de novo. O hook é ~0,3 s.

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

## Limites (honestos)

- Não julga **semântica**: um texto pode estar errado e o endpoint existir.
- Chamada de endpoint existe ≠ contrato igual (payload, status).
- `.env` de produção não é lido; só o do repo.

O registro de engenharia — o experimento que falhou, os bugs de parsing que só apareceram
em repositórios reais e por que o gate pula em vez de falhar — está em
[docs/engenharia.md](docs/engenharia.md).
