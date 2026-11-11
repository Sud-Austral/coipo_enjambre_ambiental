import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SITIO = RAIZ / "sitio"


def _datos_embebidos():
    html = (SITIO / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<script id="datos" type="application/json">(.*?)</script>', html, re.S)
    assert m, "index.html no trae el bloque de datos"
    return json.loads(m.group(1))


def test_datos_embebidos_completos():
    d = _datos_embebidos()
    assert len(d["normas"]) == 232
    assert len(d["pas"]) == 51


def test_datos_json_igual_al_embebido():
    publicado = json.loads((SITIO / "datos" / "data.json").read_text(encoding="utf-8"))
    assert publicado == _datos_embebidos()


def test_health_identifica_la_app():
    conf = (RAIZ / "nginx.conf").read_text(encoding="utf-8")
    cuerpo = re.search(r"location = /health \{.*?return 200 '(.*?)';", conf, re.S).group(1)
    assert json.loads(cuerpo)["app"] == "coipo_enjambre_regulatorio"


def test_compose_publica_solo_en_localhost():
    compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:${APP_PORT' in compose
