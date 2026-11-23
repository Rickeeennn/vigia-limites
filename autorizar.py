"""
Gera o MS_REFRESH_TOKEN — rodar UMA única vez, em qualquer lugar com Python
(GitHub Codespaces, Google Colab ou qualquer computador). Não precisa instalar nada.

    python autorizar.py SEU_CLIENT_ID            # conta pessoal (Outlook/Hotmail/Live)
    python autorizar.py SEU_CLIENT_ID organizations   # conta corporativa/escolar

Abra o link mostrado, digite o código e entre com a conta dona da pasta do OneDrive.
Depois copie o token impresso para o Secret MS_REFRESH_TOKEN do repositório.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ESCOPOS = "Files.ReadWrite offline_access"


def post(url: str, dados: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    client_id = sys.argv[1]
    tenant = sys.argv[2] if len(sys.argv) > 2 else "consumers"
    base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"

    codigo = post(f"{base}/devicecode", {"client_id": client_id, "scope": ESCOPOS})
    if "device_code" not in codigo:
        sys.exit(f"Erro: {codigo.get('error_description', codigo)}")
    print("\n" + codigo["message"] + "\n")

    while True:
        time.sleep(codigo.get("interval", 5))
        r = post(f"{base}/token", {"client_id": client_id, "device_code": codigo["device_code"],
                                   "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if "refresh_token" in r:
            print("Autorizado! Copie o valor abaixo para o Secret MS_REFRESH_TOKEN:\n")
            print(r["refresh_token"])
            return
        if r.get("error") not in ("authorization_pending", "slow_down"):
            sys.exit(f"Erro: {r.get('error_description', r)}")


if __name__ == "__main__":
    main()
