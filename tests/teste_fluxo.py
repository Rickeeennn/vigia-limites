"""Teste ponta a ponta com OneDrive simulado (pasta local) e repo Git local."""
import os, subprocess, sys, tempfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import transpilador as t

class DriveFalso:
    def __init__(s, d): s.d = Path(d)
    def baixar(s, p, n): f = s.d / n; return f.read_bytes() if f.exists() else None
    def enviar(s, p, n, c): (s.d / n).write_bytes(c)
    def listar(s, p): return [{"id": f.name, "name": f.name} for f in s.d.iterdir()]
    def apagar(s, i): (s.d / i).unlink()

RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp())
# compila o dw.jar como o workflow faz
subprocess.run(["javac", "-d", str(tmp / "dwout"), *map(str, (RAIZ / "dw/src/dw").glob("*.java"))], check=True)
(tmp / "m.txt").write_text("Main-Class: dw.Main\n")
subprocess.run(["jar", "cfm", str(tmp / "dw.jar"), str(tmp / "m.txt"), "-C", str(tmp / "dwout"), "."], check=True)
JAR = str(tmp / "dw.jar")
od = tmp / "onedrive"; od.mkdir()
bare = tmp / "destino.git"
subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
semente = tmp / "semente"
subprocess.run(["git", "clone", "-q", str(bare), str(semente)], check=True)
(semente / "README.md").write_text("dados\n")
for c in (["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], ["push", "-q", "origin", "HEAD"]):
    subprocess.run(["git", "-C", str(semente), *c], check=True)

drive = DriveFalso(od)
def rodar(titulo):
    print(f"\n--- {titulo}")
    t.executar(drive, t.RepoDestino(str(bare), "config/limites.json"), "Limites", "tanques.dw", JAR)
    print("   OneDrive:", sorted(f.name for f in od.iterdir()))

arq = od / "tanques.dw"
EX = RAIZ / "dw/exemplos"
rodar("1) arquivo ausente")
arq.write_bytes((EX / "tanques.dw").read_bytes()); rodar("2) primeiro arquivo válido (exemplos/tanques.dw)")
rodar("3) sem mudança")
arq.write_bytes((EX / "com_erros.dw").read_bytes()); rodar("4) arquivo inválido (exemplos/com_erros.dw)")
rodar("5) mesmo inválido de novo (não duplica relatório)")
print(next(od.glob("RELATORIO*")).read_text())
arq.write_bytes("Todos os tanques:\r\nVaz\u00e3oMin: 150\r\n\r\nTanque 3\r\nNivelMax: 80,5%\r\n".encode("cp1252"))
rodar("6) corrigido, salvo em ANSI pelo Bloco de Notas")

saida = subprocess.run(["git", "--git-dir", str(bare), "show", "main:config/limites.json"], capture_output=True, text=True).stdout
print(saida)
print(subprocess.run(["git", "--git-dir", str(bare), "log", "--oneline", "main"], capture_output=True, text=True).stdout)
print(subprocess.run(["git", "--git-dir", str(bare), "tag"], capture_output=True, text=True).stdout)
assert json.loads(saida)["versao"] == 2
print("TESTE OK")
