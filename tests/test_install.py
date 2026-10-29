"""Instalacao: vendoriza o pacote e preserva hook que o repo ja tinha."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from doccheck.instalar import instalar


def test_install_vendoriza_e_aponta_hooks_path(tmp_path):
    instalar(tmp_path, silencioso=True)
    assert (tmp_path / ".githooks" / "doccheck" / "cli.py").is_file()
    assert (tmp_path / ".githooks" / "check_docs.py").is_file()
    assert ".githooks/* text eol=lf" in (tmp_path / ".gitattributes").read_text(encoding="utf-8")


def test_install_preserva_hook_existente(tmp_path):
    """Hook que o repo já tinha não pode ser apagado: vira pre-commit.local."""
    hook = tmp_path / ".githooks" / "pre-commit"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\necho antigo\n", encoding="utf-8", newline="\n")

    instalar(tmp_path, silencioso=True)

    local = tmp_path / ".githooks" / "pre-commit.local"
    assert local.is_file() and "antigo" in local.read_text(encoding="utf-8")
    novo = hook.read_text(encoding="utf-8")
    assert "# doccheck:" in novo and "pre-commit.local" in novo


def test_install_nao_sobrescreve_local_existente(tmp_path):
    githooks = tmp_path / ".githooks"
    githooks.mkdir()
    (githooks / "pre-commit").write_text("#!/bin/sh\n# doccheck: meu\n",
                                         encoding="utf-8", newline="\n")
    (githooks / "pre-commit.local").write_text("#!/bin/sh\necho meu\n",
                                               encoding="utf-8", newline="\n")

    instalar(tmp_path, silencioso=True)

    assert "echo meu" in (githooks / "pre-commit.local").read_text(encoding="utf-8")
