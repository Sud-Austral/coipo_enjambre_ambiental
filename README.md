# Enjambre Regulatorio Ambiental (coipo_enjambre_regulatorio)

Visor interactivo de la regulación ambiental chilena que pesa sobre los proyectos de inversión, a partir de la Ley 19.300 sobre Bases Generales del Medio Ambiente.

- 232 normas, 1.651 artículos resumidos, 540 vínculos y los 51 permisos y pronunciamientos del Reglamento del SEIA.
- Datos contrastados con las fichas y textos oficiales de la Biblioteca del Congreso Nacional (BCN) al 10-11-2026.
- Los resúmenes orientan y no reemplazan el texto oficial; cada ficha enlaza a la norma en BCN.

## Publicar

Sitio estático en Docker (nginx) con el contrato `infra-docker-base`: push a `uat` despliega en vm3 cuando `vars.UAT_LISTO` está activo; `main` es producción. Local: `docker compose up --build` con `.env` (`APP_PORT`).

## Qué contiene

| Ruta | Contenido |
|---|---|
| `sitio/index.html` | El visor completo en un solo archivo, con los datos incluidos. Es lo único necesario para publicar. |
| `sitio/datos/data.json` | Los mismos datos del visor en formato legible, para reutilizarlos. |
| `fuente/template.html` | Plantilla de la aplicación (HTML, CSS y JavaScript) sin datos; lleva el marcador `__DATA__`. |
| `fuente/build.py`, `mejoras.py`, `enlaces.py` | Guiones que fusionan los lotes, aplican las correcciones de auditoría y generan `index.html`. |
| `fuente/lotes/` | Lotes de datos por tema, capa editorial, articulados completos, etapas y simulador. |
| `fuente/correcciones/` | Correcciones entregadas por las auditorías independientes. |

## Dependencias externas

El visor carga dos recursos desde internet; sin conexión funciona, pero sin gráficos:

- D3 7.9.0 desde `cdnjs.cloudflare.com` (grafo y línea de tiempo).
- Tipografías Archivo y Open Sans desde Google Fonts (si no cargan, usa Arial).

## Para modificar

- **Cambios de diseño o comportamiento:** editar `fuente/template.html` y volver a generar.
- **Cambios de datos:** editar los lotes o agregar correcciones y volver a generar.
- **Generar:** `python3 fuente/build.py`. Los guiones tienen rutas absolutas (`/home/claude/...`) y esperan los textos oficiales de BCN en XML en una carpeta local, que no se incluyen por tamaño. Hay que ajustar esas rutas antes de ejecutarlos; la descarga de cada texto es `https://www.bcn.cl/leychile/Consulta/obtxml?opt=7&idNorma=<ID>`.
- **Atajo sin guiones:** para un cambio puntual de datos, reemplazar en `index.html` el contenido del bloque `<script id="datos" type="application/json">` por el JSON actualizado.

## Límites conocidos

- 16 vínculos parten de instructivos y guías del SEA cuyo texto no está en BCN; se dibujan con línea punteada.
- El simulador trabaja con 10 tipologías y 11 condiciones generales; no reemplaza una consulta de pertinencia.
- La regulación cambia con frecuencia: conviene revisar periódicamente la fecha de versión de cada norma en BCN.
