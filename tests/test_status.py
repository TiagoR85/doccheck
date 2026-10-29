"""Status: quem tem o vendor do doccheck e em que versão."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from doccheck import __version__, status


def repo_fake(raiz: Path, nome: str, versao: str | None) -> Path:
    repo = raiz / nome
    (repo / ".git").mkdir(parents=True)
    if versao is not None:
        init = repo / ".githooks" / "doccheck" / "__init__.py"
        init.parent.mkdir(parents=True)
        init.write_text(f'"""x"""\n__version__ = "{versao}"\n', encoding="utf-8")
    return repo


def test_coletar_classifica(tmp_path):
    repo_fake(tmp_path, "em-dia", __version__)
    repo_fake(tmp_path, "atrasado", "0.0.9")
    repo_fake(tmp_path, "sem-vendor", None)
    (tmp_path / "nao-e-repo").mkdir()

    linhas = status.coletar(tmp_path)
    por_nome = {linha["repo"]: linha for linha in linhas}

    assert por_nome["em-dia"]["estado"] == "em dia"
    assert por_nome["atrasado"]["estado"] == "atrasado"
    assert por_nome["atrasado"]["versao"] == "0.0.9"
    assert por_nome["sem-vendor"]["estado"] == "ausente"
    assert "nao-e-repo" not in por_nome


def test_resumo_conta_estados(tmp_path):
    repo_fake(tmp_path, "a", __version__)
    repo_fake(tmp_path, "b", "0.0.1")
    repo_fake(tmp_path, "c", None)

    numero = status.resumo(status.coletar(tmp_path))
    assert numero["em dia"] == 1 and numero["atrasado"] == 1 and numero["ausente"] == 1
    assert numero["versao_instalada"] == __version__


def test_cli_status_sai_1_quando_ha_atraso(tmp_path, capsys):
    from doccheck.cli import main

    repo_fake(tmp_path, "atrasado", "0.0.1")
    assert main(["status", str(tmp_path)]) == 1
    assert "atrasado" in capsys.readouterr().out


def test_cli_status_sai_0_quando_tudo_em_dia(tmp_path, capsys):
    from doccheck.cli import main

    repo_fake(tmp_path, "ok", __version__)
    assert main(["status", str(tmp_path)]) == 0
    assert "em dia" in capsys.readouterr().out
