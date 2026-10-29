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

## Próximo

`doccheck review --ia` saiu do papel com as decisões que importam: **fora do hook** (o gate
segue determinístico), **pergunta em vez de patch** (modelo que reescreve doc inventa fato)
e **custo explícito** (`--max-usd` aborta antes de enviar; a saída mostra tokens e US$).
Endpoint OpenAI-compatível por ambiente — serve OpenAI, Groq, DeepSeek, Ollama e qualquer
gateway, sem dependência nova no projeto.

O que ainda falta é coragem de rodar isso nos 31 repositórios e comparar com a auditoria
manual. A aposta é que ele pega os casos do `vendas-desapego` (rate limit, versão do CDN,
serviços do compose) — os que nenhuma regra estrutural alcança.
