# Notas de engenharia — doccheck

O que não cabe no README: o que foi tentado, o que falhou, e por que o código está do
jeito que está. Datas em UTC−3.

## 2026-10-29 — por que isto existe

Trinta e um repositórios na mesma máquina, cada um com README, MANUAL, CHANGELOG e STATUS.
O `my-opencode-hub` documentava 12 das 15 páginas que tinha. Um README dizia 74 testes
onde havia 129. Outro citava `POST /api/fase1/validar`, rota que não existe desde que
virou `POST /api/fase1`. Nada disso quebra build, gera 500 ou acorda alguém — a doc só
mente com confiança até alguém seguir o passo a passo.

A pergunta que virou projeto: **qual parte disso dá para verificar por máquina?**

## Decisão 1 — o que não dá para avaliar é *pulado*, nunca falha

Esta é a decisão que sustenta o resto. Antes dela, tentei a regra óbvia: "todo caminho
citado em `code span` existe no repositório". Resultado em 31 repos:

| Tipo de falso positivo | Exemplo | Ocorrências |
|---|---|---|
| placeholder | `data/fase4/pacotes/{video_id}/` | maioria |
| elipse proposital | `src/.../Services/ChargeService.cs` | várias |
| link relativo | `../plans/2026-10-06-...md` | várias |
| plano congelado | `docs/plans/2026-06-28-*.md` | maioria |
| arquivo de runtime | `data/energy_auto.json` | 2 |

**242 achados em 11 repositórios, praticamente todos falso positivo.** Um gate assim não
protege nada: ensina o time a digitar `--no-verify`, e a partir daí todo o mecanismo
— inclusive as regras boas — vira decoração. Daí o princípio no código:

```python
rel.pular("endpoints", "nenhuma rota encontrada no código")   # e sai 0
```

Regra que não consegue ser avaliada **diz por que pulou** e não bloqueia. O relatório
mostra as puladas, para ninguém confundir silêncio com aprovação.

## Decisão 2 — vendorizar em `.githooks/`

`doccheck install` copia o pacote para `.githooks/doccheck/` em vez de exigir
`pip install`. Motivo: o hook roda em todo commit. Não pode depender de rede, de
índice de pacote ou de a máquina ter a ferramenta instalada — muito menos quebrar o
commit porque o PyPI piscou. O repo fica self-contained; para atualizar, roda-se
`install` de novo.

Custo aceito: ~20 arquivos versionados por repositório. É o mesmo código, não um fork.

## Decisão 3 — nunca apagar hook que já existe

Aconteceu **duas vezes** no `my-opencode-hub`: o `install` trocou o hook que rodava
`tests/test_docs.py` (checagem de páginas do MANUAL) pelo hook genérico. A segunda vez
doeu o suficiente para virar código:

```python
if hook.is_file() and MARCA not in hook.read_text(...):
    shutil.copyfile(hook, githooks / "pre-commit.local")   # roda depois
```

Hook alheio vira `pre-commit.local` e é encadeado no fim. Instalar não pode remover
checagem que o repositório já tinha.

## Os seis defeitos que só os repositórios reais revelaram

Nenhum destes apareceu nos testes de exemplo; todos apareceram ao rodar contra os 31:

1. **`python -m doccheck` sem `__main__.py`.** O primeiro dry-run "não acusou nada" — e
   eu quase reportei tudo limpo. O filtro da minha própria saída escondeu o erro.
2. **`:id` do Express comia `<int:id>` do Flask**: a rota virava `<int<var>>`.
3. **Regex de atributo quebrando em `[Route("api/[controller]")]`**: o `]` de
   `[controller]` fechava o colchete cedo. Atributo pode conter `]` dentro de string.
4. **Rota herdada invisível**: `ClientesController : BaseApiController<T>` não declara
   `[Route]`; herda `api/[controller]` da classe abstrata. Perdia 24 rotas de 47.
5. **Classe aninhada cortando o controller**: um DTO dentro da classe encerrava o corpo
   e escondia os métodos seguintes (`/internal/salvar-token`).
6. **Hook sobrescrito** (Decisão 3).

Cada um com teste de regressão hoje. Nenhum deles teria sido pensado sem os repos reais.

## Limites conhecidos, medidos

- **Semântica não é verificável por conjunto.** No `vendas-desapego`, a auditoria por
  leitura achou: rate limit documentado como 5/min (o default do código é 30), Tailwind
  "v4" (o CDN carregado é o Play v3) e compose "nginx + api + umami" (os serviços são
  `front`, `api`, `umami`, `umami-db`). Nenhuma dessas três é detectável por regra
  estrutural — foi preciso alguém ler o código ao lado da frase.
- **Endpoint existente ≠ contrato igual.** Payload, status e semântica ficam de fora.
- **`.env` de produção não é lido.** Só o do repositório.

## O que eu deliberadamente não fiz

- **LLM no gate.** O hook precisa ser determinístico e offline. Um verificador que às
  vezes falha (ou às vezes passa) é pior que nenhum: ninguém confia. A camada semântica
  pertence a um comando separado, sob demanda, que produz **perguntas com `arquivo:linha`**
  — nunca um veredito que bloqueia commit.
- **Checar `.env.example` contra a doc.** Ruído alto: metade dos nomes citados é de
  serviço de terceiro, não do projeto.

## Teste de fogo do `review --ia` (2026-10-29, deepseek-flash)

Dois cenários controlados, com verdade conhecida:

| Cenário | O que muda | v0.3.1 (diff + docs) | v0.4.0 (diff + docs + recortes de código) |
|---|---|---|---|
| **A — código muda, doc fica** | default 5 → 30 no código, README dizendo 5 | achou `README.md:14` | achou `README.md:14` (383 in / 360 out) |
| **B — doc muda, código fica** | só o README muda; o código em 30 | **NADA ENCONTRADO** | **achou**: `README.md:3 — "a doc diz 5" \| "o código diz 30 (app.py:1)"` (401 in / 298 out) |

O que fechou o cenário B foi o contexto ganhar código: até 6 recortes de 4000 caracteres,
vindos de **(a)** caminhos citados na doc, **(b)** pontos de entrada conhecidos
(`docker-compose.yml`, `Program.cs`, `index.html`, `app.py`, `Dockerfile`, `package.json`…) e
**(c)** arquivos modificados recentemente (`git log --name-only -8`). Ficam de fora `.md`,
`.githooks`, `node_modules`, `bin/obj` — poluição cara sem sinal.

### Medição em 3 repositórios reais (estado pré-auditoria, diff vazio)

Mesmo desenho, agora contra a auditoria manual dos 31: clone no commit anterior à correção
da doc + `git commit --allow-empty`, para o diff ficar vazio e a única entrada ser
**doc × código em repouso**.

| Repo | Achados manuais | O que a IA achou | Acerto |
|---|---|---|---|
| vendas-desapego | rate limit 30/min, Tailwind v3 (Play CDN), compose sem nginx | os **três**, cada um com `README.md:linha` e o trecho do código | **3/3** |
| interview-assistant | 129 testes C# / 13 JS (doc dizia 74/6) | a frase "74 C# + 6 JS" apontando o STATUS inconsistente, não a contagem real | **1/1 parcial** |
| youtube-gemini-pipeline | 819 testes (doc: 789); mensagens de erro reais | nenhum dos dois | **0/2** |

Precisão dos extras (o que a auditoria manual não tinha): **2 de 2 verificados eram reais** —
`<title>Code & Drive</title>` no `index.html` do vendas e `URL = 5001` / `{video_id}.txt` no
youtube.

O padrão é claro: **número que exige contar ou executar** (suite de testes) e **string
específica no meio de arquivo grande** (mensagem de erro depois dos 4000 caracteres do
recorte) ficam de fora. O que a ferramenta entrega é o que está na superfície: valor de
configuração, serviço do compose, versão de CDN, porta, formato de arquivo.

Custo medido: 6,7k / 9,5k / 13,4k tokens de entrada e 5,7k / 17,7k / 29,3k de saída — fração
de centavo a poucos centavos no `deepseek-flash`. O youtube estourou o timeout de 60s, que
subiu para **180s** (contexto grande + reasoning longo).

## Próximo

- **Saída cara em repo grande** (29k tokens de saída no youtube): limitar `max_tokens` ou
  pedir só os N achados mais graves.
- **Contagem de testes não é trabalho de IA**: é do `check` — `pytest --collect-only` e
  comparar com o número citado na doc, determinístico e offline.
- `--max-usd` só protege com `DOCCHECK_IA_PRECO_IN/OUT` definidos.
