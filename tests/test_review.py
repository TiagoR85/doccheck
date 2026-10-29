"""Revisão: contexto determinístico e chamada de IA com transporte falso."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from doccheck import review


def repo_git(tmp_path: Path) -> Path:
    def g(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (tmp_path / "README.md").write_text("# A\n\ntexto\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-q", "-m", "base")
    (tmp_path / "app.py").write_text("x = 2\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# A\n\ntexto novo com x = 2\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-q", "-m", "muda")
    return tmp_path


def test_monta_contexto_com_diff_e_docs(tmp_path):
    repo = repo_git(tmp_path)
    ctx = review.montar_contexto(repo, "HEAD~1")
    assert "x = 2" in ctx["diff"]
    assert ctx["docs"] and ctx["docs"][0][0] == "README.md"
    assert "texto novo" in ctx["docs"][0][1]


def test_codigo_muda_e_doc_fica_velha_entra_no_contexto(tmp_path):
    """Só código no diff: a doc viva (README) precisa entrar para haver comparação."""
    repo = repo_git(tmp_path)
    (tmp_path / "app.py").write_text("x = 3\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "so codigo"], cwd=repo,
                   check=True, capture_output=True)

    ctx = review.montar_contexto(repo, "HEAD~1")
    assert "x = 3" in ctx["diff"]
    nomes = [n for n, _ in ctx["docs"]]
    assert "README.md" in nomes, nomes
    assert "texto novo" in dict(ctx["docs"])["README.md"]


def test_sem_ia_devolve_contexto_e_nao_chama(tmp_path):
    repo = repo_git(tmp_path)
    r = review.revisar(repo, ref="HEAD~1", usar_ia=False, env={})
    assert r["usou_ia"] is False
    assert r["contexto"] and r["resposta"] is None
    assert "NADA ENCONTRADO" in r["contexto"]        # instrução vai no prompt


def test_sem_config_pula_com_motivo(tmp_path):
    repo = repo_git(tmp_path)
    r = review.revisar(repo, ref="HEAD~1", usar_ia=True, env={})
    assert r["usou_ia"] is False and "DOCCHECK_IA_URL" in r["pulado"]


def test_chama_transporte_e_reporta_custo(tmp_path):
    repo = repo_git(tmp_path)
    chamadas = []

    def transporte(url, payload, chave):
        chamadas.append((url, payload, chave))
        return {"choices": [{"message": {"content": "- README.md:3 — pergunta"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100}}

    env = {"DOCCHECK_IA_URL": "https://api.exemplo/v1", "DOCCHECK_IA_KEY": "k",
           "DOCCHECK_IA_MODEL": "modelo-x",
           "DOCCHECK_IA_PRECO_IN": "2", "DOCCHECK_IA_PRECO_OUT": "10"}
    r = review.revisar(repo, ref="HEAD~1", usar_ia=True, env=env, transporte=transporte)

    assert r["usou_ia"] and "pergunta" in r["resposta"]
    assert chamadas[0][0] == "https://api.exemplo/v1/chat/completions"
    assert chamadas[0][1]["model"] == "modelo-x"
    assert chamadas[0][2] == "k"
    assert r["custo_usd"] == pytest.approx((1000 * 2 + 100 * 10) / 1_000_000)


def test_aborta_acima_do_teto_sem_chamar(tmp_path):
    repo = repo_git(tmp_path)
    chamou = []

    def transporte(*a):
        chamou.append(a)
        return {}

    env = {"DOCCHECK_IA_URL": "https://api.exemplo/v1",
           "DOCCHECK_IA_PRECO_IN": "1000"}     # US$ 1000 por 1M tokens
    r = review.revisar(repo, ref="HEAD~1", usar_ia=True, max_usd=0.000001,
                       env=env, transporte=transporte)
    assert not chamou
    assert r["usou_ia"] is False and "acima de" in r["pulado"]


def test_config_ia_normaliza_url():
    assert review.config_ia(
        {"DOCCHECK_IA_URL": "https://x/v1/"})["url"] == "https://x/v1/chat/completions"
    assert review.config_ia(
        {"DOCCHECK_IA_URL": "https://x/v1/chat/completions"})["url"].endswith("/chat/completions")
    assert review.config_ia({}) is None


def test_cli_review_sem_ia_sai_zero(tmp_path, capsys):
    from doccheck.cli import main

    repo = repo_git(tmp_path)
    codigo = main(["review", str(repo), "--ref", "HEAD~1"])
    assert codigo == 0
    saida = capsys.readouterr().out
    assert "contexto pronto" in saida
