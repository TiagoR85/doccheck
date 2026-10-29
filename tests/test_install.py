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


def test_vendor_ignora_pycache_gerado_pelo_hook(tmp_path):
    """O hook roda Python dentro do vendor: o .pyc gerado nao pode ser staged."""
    import subprocess

    instalar(tmp_path, silencioso=True)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    cache = tmp_path / ".githooks" / "doccheck" / "__pycache__"
    cache.mkdir()
    (cache / "x.cpython-313.pyc").write_bytes(b"\x00")

    subprocess.run(["git", "add", ".githooks"], cwd=tmp_path, check=True,
                   capture_output=True)
    arquivos = subprocess.run(["git", "ls-files"], cwd=tmp_path, check=True,
                              capture_output=True, text=True).stdout

    assert "__pycache__" not in arquivos, arquivos
    assert ".githooks/doccheck/.gitignore" in arquivos


def test_install_nao_sobrescreve_local_existente(tmp_path):
    githooks = tmp_path / ".githooks"
    githooks.mkdir()
    (githooks / "pre-commit").write_text("#!/bin/sh\n# doccheck: meu\n",
                                         encoding="utf-8", newline="\n")
    (githooks / "pre-commit.local").write_text("#!/bin/sh\necho meu\n",
                                               encoding="utf-8", newline="\n")

    instalar(tmp_path, silencioso=True)

    assert "echo meu" in (githooks / "pre-commit.local").read_text(encoding="utf-8")
