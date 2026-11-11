# coipo_enjambre_regulatorio

Visor interactivo de la regulacion ambiental chilena que pesa sobre los proyectos de inversion
(Ley 19.300 y normas vinculadas): 232 normas, 1.651 articulos resumidos, 540 vinculos y los 51 permisos
y pronunciamientos del Reglamento del SEIA, contrastados con BCN al 10-11-2026.

## Perfil y alcance
- Liviano: sitio estatico (`sitio/index.html` con los datos embebidos) servido por nginx en Docker.
- Sin backend, sin login, sin base de datos, sin PII.
- `/health` devuelve `"app": "coipo_enjambre_regulatorio"` (contrato infra-docker-base), definido en `nginx.conf`.

## Estructura
- `sitio/`: lo que se publica (`index.html`, `datos/data.json`).
- `fuente/`: plantilla, guiones de generacion, lotes de datos y correcciones de auditoria.
  Los guiones traen rutas `/home/claude/...` del entorno original: ajustarlas antes de regenerar.
- `insumos/`: ficha del problema y la solucion.

## Reglas
- Configuracion solo por `.env` (ver `.env.example`). Nunca credenciales en el repo.
- Ramas: `uat` despliega a vm3 (si `vars.UAT_LISTO`), `main` es produccion (PR aprobado + `vars.SERVIDOR_LISTO`).
- Si cambian los datos, `sitio/datos/data.json` debe ser igual al JSON embebido en `index.html` (lo vigila la prueba).

## Probar
```
pip install -r requirements-dev.txt
python -m pytest -q
docker compose up --build   # con .env (APP_PORT)
```
