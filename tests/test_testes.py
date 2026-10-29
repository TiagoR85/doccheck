"""Regra `testes`: contagem estática no código x número citado na doc viva."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from doccheck import config
from doccheck.rules import rodar


def montar(tmp_path: Path, arquivos: dict[str, str]) -> Path:
    for nome, texto in arquivos.items():
        alvo = tmp_path / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8", newline="\n")
    return tmp_path


def achados_de_testes(tmp_path: Path):
    rel = rodar(tmp_path, config.carregar(tmp_path))
    return [a for a in rel.achados if a.regra == "testes"], rel


README = "# Projeto\n\nUm texto qualquer com tamanho suficiente para passar do minimo.\n"


def _cs(metodos: int, datarows: int) -> str:
    corpo = "\n".join(f"    [TestMethod]\n    public void T{i}() {{ }}" for i in range(metodos))
    extras = "\n".join(f"    [DataRow({i})]" for i in range(datarows))
    return f"[TestClass]\npublic class Exemplo {{\n{corpo}\n{extras}\n}}\n"


def test_cs_soma_datadrow_e_bate_com_a_doc(tmp_path):
    """106 TestMethod + 23 DataRow = 129, exatamente como a auditoria contou."""
    montar(tmp_path, {
        "README.md": README + "\nA suite tem 129 testes.\n",
        "tests/App.Tests/Exemplo.cs": _cs(106, 23),
    })
    achados, _ = achados_de_testes(tmp_path)
    assert not achados, [str(a) for a in achados]


def test_contagem_muito_errada_vira_aviso_sem_bloquear(tmp_path):
    """Contagem estática é aproximada: avisa, mas nunca bloqueia commit."""
    testes = "\n".join(f"def test_{i}():\n    assert True\n" for i in range(20))
    montar(tmp_path, {
        "README.md": README + "\nA suite tem 74 testes.\n",
        "tests/test_x.py": testes,
    })
    achados, rel = achados_de_testes(tmp_path)
    assert achados and achados[0].severidade == "aviso"
    assert "74" in achados[0].mensagem and "20" in achados[0].mensagem
    assert rel.ok


def test_virtualenv_com_outro_nome_nao_infla_a_contagem(tmp_path):
    """`.venv-test/Lib/site-packages/numpy/tests/` já inflou 8164 no SmartCondominiumGuard."""
    importado = "\n".join(f"def test_{i}():\n    pass\n" for i in range(300))
    montar(tmp_path, {
        "README.md": README + "\nA suite tem 2 testes.\n",
        "tests/test_x.py": "def test_a():\n    pass\ndef test_b():\n    pass\n",
        "python_engine/.venv-test/Lib/site-packages/numpy/tests/test_multiarray.py": importado,
    })
    achados, _ = achados_de_testes(tmp_path)
    assert not achados, [str(a) for a in achados]


def test_bloco_de_codigo_e_checklist_nao_contam(tmp_path):
    """Comando em ``` e item de checklist `- [x]` são histórico, não afirmação."""
    testes = "\n".join(f"def test_{i}():\n    assert True\n" for i in range(20))
    montar(tmp_path, {
        "README.md": README,
        "STATUS.md": (
            "# Status v1.0.0\n\n"
            "- [x] 182 testes MSTest\n"
            "## Como rodar\n"
            "```powershell\n"
            "pytest -q   # 663 testes; 663 passam\n"
            "```\n"
        ),
        "tests/test_x.py": testes,
    })
    achados, _ = achados_de_testes(tmp_path)
    assert not achados, [str(a) for a in achados]


def test_diferenca_media_vira_aviso_sem_bloquear(tmp_path):
    testes = "\n".join(f"def test_{i}():\n    assert True\n" for i in range(100))
    montar(tmp_path, {
        "README.md": README + "\nA suite tem 120 testes.\n",
        "tests/test_x.py": testes,
    })
    achados, rel = achados_de_testes(tmp_path)
    assert achados and achados[0].severidade == "aviso"
    assert rel.ok, "aviso não pode bloquear commit"


def test_tolerancia_de_dez_por_cento_silencia(tmp_path):
    """Parametrização faz o número real variar: 5% de diferença não é mentira."""
    testes = "\n".join(f"def test_{i}():\n    assert True\n" for i in range(100))
    montar(tmp_path, {
        "README.md": README + "\nA suite tem 105 testes.\n",
        "tests/test_x.py": testes,
    })
    achados, _ = achados_de_testes(tmp_path)
    assert not achados


def test_changelog_com_contagem_antiga_e_ignorado(tmp_path):
    """CHANGELOG guarda história: 512 testes em v1.0.0 não é mentira em v2.0."""
    testes = "\n".join(f"def test_{i}():\n    assert True\n" for i in range(20))
    montar(tmp_path, {
        "README.md": README + "\nA suite tem 20 testes.\n",
        "CHANGELOG.md": "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n- 512 testes verdes\n",
        "tests/test_x.py": testes,
    })
    achados, _ = achados_de_testes(tmp_path)
    assert not achados, [str(a) for a in achados]


def test_sem_testes_no_codigo_pula(tmp_path):
    montar(tmp_path, {"README.md": README + "\nA suite tem 50 testes.\n"})
    _, rel = achados_de_testes(tmp_path)
    assert any(p.startswith("testes:") and "sem" in p for p in rel.puladas), rel.puladas


def test_doc_sem_contagem_citada_pula(tmp_path):
    testes = "\n".join(f"def test_{i}():\n    assert True\n" for i in range(20))
    montar(tmp_path, {"README.md": README, "tests/test_x.py": testes})
    _, rel = achados_de_testes(tmp_path)
    assert any(p.startswith("testes:") for p in rel.puladas), rel.puladas
