"""Testes: cada regra e cada adaptador com um mini-repo montado no tmp_path."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from doccheck import config
from doccheck.adapters import rotas as rotas_de
from doccheck.rules import rodar


def montar(tmp_path: Path, arquivos: dict[str, str]) -> Path:
    for nome, texto in arquivos.items():
        alvo = tmp_path / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8", newline="\n")
    return tmp_path


def verificar(tmp_path: Path) -> tuple[bool, str]:
    rel = rodar(tmp_path, config.carregar(tmp_path))
    return rel.ok, "\n".join(str(a) for a in rel.achados)


README = "# Projeto\n\nUm texto qualquer com tamanho suficiente para passar do mínimo.\n"


# --------------------------------------------------------------- estrutura
def test_readme_ausente_falha(tmp_path):
    ok, saida = verificar(tmp_path)
    assert not ok and "sem README.md" in saida


def test_readme_vazio_falha(tmp_path):
    montar(tmp_path, {"README.md": "# x\n"})
    ok, saida = verificar(tmp_path)
    assert not ok and "vazio" in saida


def test_projeto_minimo_passa(tmp_path):
    montar(tmp_path, {"README.md": README})
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_secao_vazia_falha(tmp_path):
    montar(tmp_path, {"README.md": README + "\n## Vazia\n\n## Outra\n\ntexto\n"})
    ok, saida = verificar(tmp_path)
    assert not ok and "seção vazia 'Vazia'" in saida


def test_changelog_com_subsecoes_nao_e_secao_vazia(tmp_path):
    """`## [1.2.3]` seguido de `### Adicionado` tem conteúdo, não é vazio."""
    montar(tmp_path, {
        "README.md": README,
        "CHANGELOG.md": ("# Changelog\n\n## [1.2.3] - 2026-10-29\n\n"
                         "### Adicionado\n\n- algo novo\n"),
        "STATUS.md": "# Status — v1.2.3 (2026-10-29)\n\ntexto\n",
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_versao_igual_passa(tmp_path):
    montar(tmp_path, {
        "README.md": README,
        "CHANGELOG.md": "# Changelog\n\n## [1.2.3] - 2026-10-29\n\n- algo\n",
        "STATUS.md": "# Status — v1.2.3 (2026-10-29)\n\ntexto\n",
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_versao_divergente_falha(tmp_path):
    montar(tmp_path, {
        "README.md": README,
        "CHANGELOG.md": "# Changelog\n\n## [1.2.3] - 2026-10-29\n\n- algo\n",
        "STATUS.md": "# Status — v1.2.2 (2026-10-29)\n\ntexto\n",
    })
    ok, saida = verificar(tmp_path)
    assert not ok and "v1.2.2" in saida and "v1.2.3" in saida


def test_versao_por_data_quando_changelog_nao_versiona(tmp_path):
    montar(tmp_path, {
        "README.md": README,
        "CHANGELOG.md": "# Changelog\n\n## [2026-10-24] - algo\n\n- x\n",
        "STATUS.md": "# Status — 2026-10-09\n\ntexto\n",
    })
    ok, saida = verificar(tmp_path)
    assert not ok and "2026-10-09" in saida and "2026-10-24" in saida


def test_sem_status_nao_opina_sobre_versao(tmp_path):
    montar(tmp_path, {"README.md": README})
    rel = rodar(tmp_path, config.carregar(tmp_path))
    assert rel.ok and any("versao" in p for p in rel.puladas)


# ---------------------------------------------------------------- segredos
def test_segredo_no_doc_falha(tmp_path):
    montar(tmp_path, {
        "README.md": README + "\ntoken: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345\n",
    })
    ok, saida = verificar(tmp_path)
    assert not ok and "token" in saida


def test_valor_do_env_no_doc_falha(tmp_path):
    montar(tmp_path, {
        "README.md": README + "\nsenha: SuperSegredo123\n",
        ".env": "HUB_PASS=SuperSegredo123\n",
    })
    ok, saida = verificar(tmp_path)
    assert not ok and "HUB_PASS" in saida


def test_plano_ignorado_por_padrao(tmp_path):
    montar(tmp_path, {
        "README.md": README,
        "docs/plans/antigo.md": "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345\n",
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_superpowers_plans_na_raiz_ignorado_por_padrao(tmp_path):
    montar(tmp_path, {
        "README.md": README,
        "docs/superpowers/plans/x.md": "## Vazia\n\n",
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


# --------------------------------------------------------------- endpoints
FLASK_MANUAL = README + """
## API

| Endpoint | Uso |
|---|---|
| `/api/tasks` | lista |
| `/api/tasks/<id>` | uma |
"""


def test_endpoint_inexistente_falha(tmp_path):
    montar(tmp_path, {
        "README.md": FLASK_MANUAL + "\n| `/api/inventado` | nada |\n",
        "app/routes/tasks.py": (
            'from flask import Blueprint\n'
            'bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")\n'
            '@bp.route("")\ndef lista(): ...\n'
            '@bp.route("/<int:id>")\ndef uma(): ...\n'),
    })
    ok, saida = verificar(tmp_path)
    assert not ok and "api/inventado" in saida


def test_endpoint_existente_passa(tmp_path):
    montar(tmp_path, {
        "README.md": FLASK_MANUAL,
        "app/routes/tasks.py": (
            'from flask import Blueprint\n'
            'bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")\n'
            '@bp.route("")\ndef lista(): ...\n'
            '@bp.route("/<int:id>")\ndef uma(): ...\n'),
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_api_de_fora_nao_e_cobrada(tmp_path):
    """MANUAL pode citar a API do OpenCode; não é rota deste repo."""
    montar(tmp_path, {
        "README.md": FLASK_MANUAL + "\n## Integrações\n\nUsa `/api/session` do OpenCode.\n",
        "app/routes/tasks.py": (
            'from flask import Blueprint\n'
            'bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")\n'
            '@bp.route("")\ndef lista(): ...\n'
            '@bp.route("/<int:id>")\ndef uma(): ...\n'),
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


# -------------------------------------------------------------- adaptadores
def test_aspnet_controller_e_minimal_api(tmp_path):
    montar(tmp_path, {
        "App.csproj": "<Project />",
        "Controllers/ClientesController.cs": (
            '[Route("api/[controller]")]\n'
            'public class ClientesController : ControllerBase\n'
            '{\n'
            '    [HttpGet("{id:int}")]\n'
            '    public IActionResult Get(int id) => Ok();\n'
            '    [HttpPost]\n'
            '    public IActionResult Post() => Ok();\n'
            '}\n'),
        "Program.cs": 'app.MapGet("/api/health", () => "ok");\n',
    })
    achadas = rotas_de(tmp_path)
    assert "/api/Clientes" in achadas
    assert "/api/Clientes/<var>" in achadas
    assert "/api/health" in achadas


def test_aspnet_rota_herdada_da_base(tmp_path):
    """`ClientesController : BaseApiController<T>` herda `api/[controller]`."""
    montar(tmp_path, {
        "App.csproj": "<Project />",
        "Controllers/BaseApiController.cs": (
            '[ApiController]\n'
            '[Route("api/[controller]")]\n'
            'public abstract class BaseApiController<T> : ControllerBase\n'
            '{\n'
            '    [HttpGet("{id}")]\n'
            '    public IActionResult Get(T id) => Ok();\n'
            '}\n'),
        "Controllers/ClientesController.cs": (
            'public class ClientesController : BaseApiController<string>\n'
            '{\n'
            '    [HttpGet("relatorio")]\n'
            '    public IActionResult Relatorio() => Ok();\n'
            '}\n'),
    })
    achadas = rotas_de(tmp_path)
    assert "/api/Clientes" in achadas
    assert "/api/Clientes/relatorio" in achadas
    assert not any("BaseApi" in r for r in achadas), achadas


def test_aspnet_classe_aninhada_nao_engole_metodos(tmp_path):
    """Classe aninhada (ex.: DTO de request) não encerra o controller."""
    montar(tmp_path, {
        "App.csproj": "<Project />",
        "Controllers/InternosController.cs": (
            '[Route("internal")]\n'
            'public class InternosController : ControllerBase\n'
            '{\n'
            '    public class SalvarTokenRequest\n'
            '    {\n'
            '        public string AccessToken { get; set; } = "";\n'
            '    }\n'
            '\n'
            '    [HttpPost("salvar-token")]\n'
            '    public IActionResult SalvarToken() => Ok();\n'
            '}\n'),
    })
    achadas = rotas_de(tmp_path)
    assert "/internal/salvar-token" in achadas, achadas


def test_express_com_prefixo(tmp_path):
    montar(tmp_path, {
        "package.json": '{"dependencies": {"express": "^4"}}',
        "src/routes.js": (
            "router.get('/users', h);\n"
            "router.get('/users/:id', h);\n"
            "app.use('/api', router);\n"),
    })
    achadas = rotas_de(tmp_path)
    assert "/api/users" in achadas
    assert "/api/users/<var>" in achadas


def test_astro_rotas_de_arquivo(tmp_path):
    montar(tmp_path, {
        "src/pages/index.astro": "<h1>home</h1>",
        "src/pages/contato.astro": "<h1>contato</h1>",
        "src/pages/blog/[slug].astro": "<h1>post</h1>",
    })
    achadas = rotas_de(tmp_path)
    assert "/" in achadas and "/contato" in achadas and "/blog/<var>" in achadas


def test_stack_desconhecida_e_pulada(tmp_path):
    montar(tmp_path, {"README.md": README})
    rel = rodar(tmp_path, config.carregar(tmp_path))
    assert rel.ok and any("stack não reconhecida" in p for p in rel.puladas)


# ------------------------------------------------------------------- stack
def test_stack_dotnet_divergente_falha(tmp_path):
    """README diz .NET 8, csproj está em net10.0 — README desatualizado."""
    montar(tmp_path, {
        "README.md": README + "\nStack: .NET 8 + Redis\n",
        "src/App.csproj": "<Project><PropertyGroup>"
                          "<TargetFramework>net10.0</TargetFramework>"
                          "</PropertyGroup></Project>",
    })
    ok, saida = verificar(tmp_path)
    assert not ok and ".NET 8" in saida and "net10.0" in saida


def test_stack_dotnet_igual_passa(tmp_path):
    montar(tmp_path, {
        "README.md": README + "\nStack: .NET 10 + Redis\n",
        "src/App.csproj": "<Project><PropertyGroup>"
                          "<TargetFramework>net10.0</TargetFramework>"
                          "</PropertyGroup></Project>",
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_stack_ignora_nome_de_pacote_akka_net(tmp_path):
    """'Akka.NET 1.5' / 'Grpc.Net 2.19' não são a versão do framework."""
    montar(tmp_path, {
        "README.md": README + "\nAkka.NET 1.5 + Grpc.Net 2.19\n",
        "src/App.csproj": "<Project><PropertyGroup>"
                          "<TargetFramework>net10.0</TargetFramework>"
                          "</PropertyGroup></Project>",
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_stack_sem_csproj_e_pulada(tmp_path):
    montar(tmp_path, {"README.md": README + "\nStack: .NET 8\n"})
    rel = rodar(tmp_path, config.carregar(tmp_path))
    assert rel.ok and any("stack" in p for p in rel.puladas)


# ------------------------------------------------------------------ config
def test_wildcard_e_query_string_nao_sao_rotas(tmp_path):
    """`/api/*` é padrão e `?x=1` é query — nenhum dos dois é rota."""
    montar(tmp_path, {
        "README.md": FLASK_MANUAL + "\n| `/api/*` | curinga |\n| `/api/tasks?x=1` | query |\n",
        "app/routes/tasks.py": (
            'from flask import Blueprint\n'
            'bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")\n'
            '@bp.route("")\ndef lista(): ...\n'
            '@bp.route("/<int:id>")\ndef uma(): ...\n'),
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_endpoint_aspnet_casa_sem_maiuscula(tmp_path):
    """ASP.NET roteia sem diferenciar caixa: /api/clientes == /api/Clientes."""
    montar(tmp_path, {
        "README.md": README + "\n## API\n\n| `/api/clientes` | lista |\n",
        "App.csproj": "<Project />",
        "Controllers/ClientesController.cs": (
            '[Route("api/[controller]")]\n'
            'public class ClientesController : ControllerBase\n'
            '{\n'
            '    [HttpGet]\n'
            '    public IActionResult Get() => Ok();\n'
            '}\n'),
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_unreleased_vazio_e_convencao(tmp_path):
    montar(tmp_path, {
        "README.md": README,
        "CHANGELOG.md": ("# Changelog\n\n## [Unreleased]\n\n---\n\n"
                         "## [1.2.3] - 2026-10-29\n\n- algo\n"),
        "STATUS.md": "# Status — v1.2.3 (2026-10-29)\n\ntexto\n",
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_config_ignore_e_aditivo(tmp_path):
    """`ignore` no .doccheck.json soma aos padrões, não os substitui."""
    montar(tmp_path, {
        "README.md": README,
        "docs/superpowers/plans/x.md": "## Vazia\n\n",
        "NOTAS-EXTERNAS.md": "## Vazia\n\n",
        ".doccheck.json": json.dumps({"ignore": ["NOTAS-EXTERNAS.md"]}),
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida


def test_config_desliga_regra(tmp_path):
    montar(tmp_path, {
        "README.md": README + "\n## Vazia\n\n",
        ".doccheck.json": json.dumps({"regras": {"secoes": False}}),
    })
    ok, saida = verificar(tmp_path)
    assert ok, saida
