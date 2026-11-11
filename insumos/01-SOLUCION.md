# 01 - Solucion

Visor web estatico ("Enjambre Regulatorio Ambiental") con grafo de normas, linea de tiempo,
fichas por norma con enlace a BCN, listado de PAS y simulador de tipologias.

## Fuentes
| Fuente | Uso | Acceso |
|---|---|---|
| BCN LeyChile (`https://www.bcn.cl/leychile/Consulta/obtxml?opt=7&idNorma=<ID>`) | Texto oficial de cada norma | Publico, descarga en la generacion (no en runtime) |
| D3 7.9.0 (cdnjs.cloudflare.com) | Grafo y linea de tiempo | Navegador |
| Google Fonts (Archivo, Open Sans) | Tipografia | Navegador, con respaldo Arial |

## Decisiones tomadas
- 2026-11-11: repo liviano (nginx + contrato infra-docker-base), sin semilla de la fabrica: no tiene backend, login ni base.
- 2026-11-11: privado en Sud-Austral, ramas `main` y `uat`, sin despliegue hasta definir puerto en vm3 (`vars.UAT_LISTO` sin activar).

## Limites conocidos
- Los resumenes orientan y no reemplazan el texto oficial.
- El simulador no reemplaza una consulta de pertinencia al SEA.
- La regulacion cambia: revisar periodicamente la fecha de version de cada norma en BCN.

## Pendientes
- [PENDIENTE: infraestructura] puerto en vm3 y dominio.
- [PENDIENTE] D3 y fuentes se cargan desde CDN externos; evaluar servirlos locales.
