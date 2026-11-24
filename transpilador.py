"""
Vigia de limites de alerta (roda no GitHub Actions, a cada 5 minutos).

  OneDrive (tanques.dw do PO) --Graph API--> validador da linguagem .dw (dw.jar)
                                                  |
                         válido: JSON versionado --+--> inválido: RELATORIO_ERRO_*.txt
                         no repositório GitHub          na mesma pasta do OneDrive

A validação é feita pelo próprio dw.jar (fonte única das regras da linguagem);
este script só orquestra: baixa, chama o jar, publica ou reporta.

O script não guarda estado: compara o SHA-256 do arquivo no OneDrive com o
"hash_origem" do último JSON publicado e com os relatórios de erro já gravados.

Variáveis de ambiente (vêm dos Secrets/Variables do GitHub):
  MS_CLIENT_ID        id do app registrado no Microsoft Entra (gratuito)
  MS_REFRESH_TOKEN    gerado uma única vez com autorizar.py
  MS_TENANT           "consumers" (conta pessoal) ou "organizations" — padrão: consumers
  ONEDRIVE_PASTA      ex.: Limites
  ONEDRIVE_ARQUIVO    ex.: tanques.dw
  DW_JAR              caminho do validador (padrão: dw.jar, compilado no workflow)
  DESTINO_REPO        ex.: minha-org/limites-dados  (repo que recebe o JSON)
  DESTINO_ARQUIVO     ex.: config/limites.json
  GH_PAT              token do GitHub com permissão de escrita no DESTINO_REPO
  NOVO_TOKEN_ARQ      (opcional) onde gravar o refresh token renovado
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
PREFIXO_RELATORIO = "RELATORIO_ERRO_"


def log(msg: str) -> None:
    # Atenção: em repositório público o log é público. Nunca imprima o conteúdo do arquivo.
    print(f"[{datetime.now(FUSO):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def mascarar(segredo: str) -> None:
    """Pede ao GitHub Actions para esconder o valor em qualquer log."""
    if os.getenv("GITHUB_ACTIONS"):
        print(f"::add-mask::{segredo}", flush=True)


# =================================================================== OneDrive
class OneDrive:
    """Cliente mínimo do Microsoft Graph usando só a biblioteca padrão."""

    GRAPH = "https://graph.microsoft.com/v1.0"
    ESCOPOS = "Files.ReadWrite offline_access"

    def __init__(self, client_id: str, refresh_token: str, tenant: str = "consumers"):
        resp = self._post_form(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            {"client_id": client_id, "grant_type": "refresh_token",
             "refresh_token": refresh_token, "scope": self.ESCOPOS},
        )
        self.token = resp["access_token"]
        mascarar(self.token)
        # A Microsoft devolve um refresh token novo a cada uso (validade de 90 dias).
        self.novo_refresh_token = resp.get("refresh_token", refresh_token)
        mascarar(self.novo_refresh_token)

    @staticmethod
    def _post_form(url: str, dados: dict) -> dict:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            erro = json.loads(e.read() or b"{}")
            raise RuntimeError(f"Falha ao autenticar na Microsoft: {erro.get('error')} — "
                               f"{erro.get('error_description', '')[:200]}") from None

    def _req(self, metodo: str, caminho: str, corpo: bytes | None = None,
             tipo: str = "application/json") -> bytes:
        req = urllib.request.Request(f"{self.GRAPH}{caminho}", data=corpo, method=metodo,
                                     headers={"Authorization": f"Bearer {self.token}",
                                              "Content-Type": tipo})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise  # tratado por quem chamou
            try:
                erro = json.loads(e.read() or b"{}").get("error", {})
            except ValueError:
                erro = {}
            raise RuntimeError(
                f"OneDrive respondeu {e.code} em {metodo} {caminho.split('?')[0]}: "
                f"{erro.get('code', '')} {erro.get('message', '')[:200]}".strip()) from None

    @staticmethod
    def _caminho(pasta: str, nome: str = "") -> str:
        alvo = "/".join(p for p in (pasta.strip("/"), nome) if p)
        return "/me/drive/root:/" + urllib.parse.quote(alvo)

    def baixar(self, pasta: str, nome: str) -> bytes | None:
        # 1) Pede os metadados do arquivo, que trazem um link de download temporário.
        try:
            meta = json.loads(self._req("GET", self._caminho(pasta, nome)))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        url = meta.get("@microsoft.graph.downloadUrl")
        if not url:
            raise RuntimeError(f"'{nome}' existe no OneDrive, mas não é um arquivo (é uma pasta?).")
        # 2) Baixa SEM o cabeçalho Authorization: o link já é autorizado e o
        #    servidor de download do OneDrive pessoal recusa (401) se ele for enviado.
        with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
            return r.read()

    def enviar(self, pasta: str, nome: str, conteudo: bytes) -> None:
        self._req("PUT", self._caminho(pasta, nome) + ":/content", conteudo, "text/plain; charset=utf-8")

    def listar(self, pasta: str) -> list[dict]:
        dados = json.loads(self._req("GET", self._caminho(pasta) + ":/children?$select=id,name&$top=999"))
        return dados.get("value", [])

    def apagar(self, item_id: str) -> None:
        self._req("DELETE", f"/me/drive/items/{item_id}")


# =================================================================== validação
def para_utf8(conteudo: bytes) -> bytes:
    """O dw.jar lê UTF-8. Bloco de Notas antigo salva em ANSI (cp1252): convertemos antes."""
    try:
        return conteudo.decode("utf-8-sig").encode("utf-8")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace").encode("utf-8")


def validar(conteudo: bytes, nome: str, jar: str) -> tuple[dict, list[str]]:
    """Chama `java -jar dw.jar arquivo --json`. Retorna (limites, erros)."""
    if not conteudo.strip():
        return {}, ["O arquivo está vazio (o upload pode ter falhado)."]

    with tempfile.TemporaryDirectory() as tmp:
        arq = Path(tmp) / (Path(nome).name or "arquivo.dw")
        arq.write_bytes(para_utf8(conteudo))
        r = subprocess.run(["java", "-jar", jar, str(arq), "--json"],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)

    # Remove avisos da JVM (ex.: "Picked up JAVA_TOOL_OPTIONS") que não são do validador.
    saida_erro = [l for l in r.stderr.splitlines() if l.strip() and not l.startswith("Picked up ")]

    if r.returncode == 0:
        return json.loads(r.stdout), []
    if r.returncode == 1:  # arquivo com erros: o jar lista todos, um por linha "  - ..."
        erros = [l.strip()[2:] for l in saida_erro if l.strip().startswith("- ")]
        return {}, erros or saida_erro
    if r.returncode == 2 and saida_erro:  # ex.: "Nao consegui ler o arquivo"
        return {}, saida_erro
    raise RuntimeError(f"dw.jar terminou com código {r.returncode}: {' | '.join(saida_erro)[:300]}")


def montar_relatorio(arquivo: str, erros: list[str]) -> bytes:
    agora = datetime.now(FUSO)
    corpo = [
        "RELATÓRIO DE ERRO — os limites NÃO foram publicados",
        f"Arquivo: {arquivo}",
        f"Verificado em: {agora:%d/%m/%Y %H:%M} (horário de Brasília)",
        "",
        "Problemas encontrados:",
        *[f"  - {e}" for e in erros],
        "",
        "Corrija o arquivo e salve de novo. A próxima verificação acontece em até 5 minutos.",
        "Dica: o README da linguagem .dw explica o formato (Tanque N / Todos os tanques).",
        "A última versão válida continua em vigor no GitHub.",
    ]
    return ("\n".join(corpo) + "\n").encode("utf-8")


# =================================================================== GitHub
def git(pasta: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} falhou: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout.strip()


class RepoDestino:
    """Clona o repositório de destino, lê a última versão e publica a próxima."""

    def __init__(self, url: str, arquivo: str):
        self.dir = Path(tempfile.mkdtemp(prefix="destino_"))
        r = subprocess.run(["git", "clone", "--quiet", "--depth", "50", url, str(self.dir)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("Não consegui clonar o repositório de destino (confira DESTINO_REPO e GH_PAT).")
        git(self.dir, "config", "user.name", "vigia-limites[bot]")
        git(self.dir, "config", "user.email", "vigia-limites@users.noreply.github.com")
        self.arquivo = self.dir / arquivo
        self.atual = json.loads(self.arquivo.read_text("utf-8")) if self.arquivo.exists() else {}

    def publicar(self, limites: dict, hash_origem: str, origem: str) -> int:
        versao = int(self.atual.get("versao", 0)) + 1
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps({
            "versao": versao,
            "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
            "origem": origem,
            "hash_origem": hash_origem,
            "limites": limites,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rel = str(self.arquivo.relative_to(self.dir))
        git(self.dir, "add", rel)
        git(self.dir, "commit", "-m", f"limites v{versao} (origem {hash_origem[:8]})")
        git(self.dir, "tag", f"limites-v{versao}")
        git(self.dir, "push", "origin", "HEAD", f"limites-v{versao}")
        return versao


# =================================================================== principal
def executar(drive, repo: RepoDestino, pasta: str, arquivo: str, jar: str = "dw.jar") -> int:
    conteudo = drive.baixar(pasta, arquivo)
    if conteudo is None:
        log(f"Arquivo '{arquivo}' não encontrado na pasta '{pasta}' do OneDrive.")
        return 0

    h = hashlib.sha256(conteudo).hexdigest()
    relatorios = [i for i in drive.listar(pasta) if i["name"].startswith(PREFIXO_RELATORIO)]

    if repo.atual.get("hash_origem") == h:
        for i in relatorios:  # PO voltou para a versão válida: limpa relatórios pendentes
            drive.apagar(i["id"])
        log(f"Sem alterações (v{repo.atual.get('versao')} já publicada).")
        return 0

    if any(h[:8] in i["name"] for i in relatorios):
        log("Esta versão do arquivo já foi reprovada; aguardando correção do PO.")
        return 0

    limites, erros = validar(conteudo, arquivo, jar)
    if erros:
        nome = f"{PREFIXO_RELATORIO}{datetime.now(FUSO):%Y-%m-%d_%H-%M}_{h[:8]}.txt"
        drive.enviar(pasta, nome, montar_relatorio(arquivo, erros))
        log(f"INVÁLIDO: {len(erros)} problema(s). Relatório gravado no OneDrive: {nome}")
        return 0  # o erro é do arquivo, não do vigia: o job não deve ficar vermelho

    versao = repo.publicar(limites, h, f"OneDrive:/{pasta}/{arquivo}")
    for i in relatorios:
        drive.apagar(i["id"])
    log(f"OK: limites v{versao} publicados ({len(limites.get('tanques', {}))} tanque(s)); "
        f"{len(relatorios)} relatório(s) antigo(s) removido(s).")
    return 0


def main() -> int:
    env = os.environ
    faltando = [v for v in ("MS_CLIENT_ID", "MS_REFRESH_TOKEN", "DESTINO_REPO", "GH_PAT") if not env.get(v)]
    if faltando:
        log(f"Variáveis ausentes: {', '.join(faltando)}")
        return 2

    drive = OneDrive(env["MS_CLIENT_ID"], env["MS_REFRESH_TOKEN"], env.get("MS_TENANT", "consumers"))
    if env.get("NOVO_TOKEN_ARQ") and drive.novo_refresh_token != env["MS_REFRESH_TOKEN"]:
        Path(env["NOVO_TOKEN_ARQ"]).write_text(drive.novo_refresh_token, encoding="utf-8")

    url = f"https://x-access-token:{env['GH_PAT']}@github.com/{env['DESTINO_REPO']}.git"
    repo = RepoDestino(url, env.get("DESTINO_ARQUIVO", "config/limites.json"))
    return executar(drive, repo, env.get("ONEDRIVE_PASTA", "Limites"),
                    env.get("ONEDRIVE_ARQUIVO", "tanques.dw"), env.get("DW_JAR", "dw.jar"))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"FALHA: {e}")
        sys.exit(1)
