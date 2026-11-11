#!/usr/bin/env python3
"""Fusiona los lotes, aplica las correcciones de los verificadores independientes, valida y genera index.html."""
import json, glob, os, re, sys, collections, copy
sys.path.insert(0, '/home/claude/app')

BASE = '/home/claude'
CATS = {"nucleo","institucionalidad","seia","aire","agua","ruido-luz-olores","planes","biodiversidad-areas","bosques-suelo",
        "residuos-sustancias","clima-energia","territorio-patrimonio","mineria","pesca-costa","fiscalizacion-justicia",
        "participacion-indigena","tratados"}
RELS = {"reglamenta","modifica","crea_organo","deroga","reemplaza","remite","complementa","implementa_tratado","pas"}
LOTES = ['r1_nucleo','r2_institucional','r3_seia','r4_calidad_emision','r5_sectorial','r6_residuos_clima_tratados','r7_complemento']
# orden de aplicación: auditorías por lote primero, identidad (v1) al final porque trae versiones canónicas
FIXES = ['v2','v3','v4','v5','v1','v6','v7']
avisos = []
def artnum(x): return re.sub(r'\s+', ' ', str(x)).strip().lower()

lotes = {}
for nombre in LOTES:
    ruta = f'{BASE}/data/{nombre}.json'
    if os.path.exists(ruta): lotes[nombre] = json.load(open(ruta, encoding='utf-8'))
fixes = [(v, json.load(open(f'{BASE}/verif/fix_{v}.json', encoding='utf-8'))) for v in FIXES if os.path.exists(f'{BASE}/verif/fix_{v}.json')]
alias = {}
for _, f in fixes: alias.update(f.get('alias') or {})
pas = [p for d in lotes.values() for p in d.get('pas', [])]
estructura = next((d['estructura_19300'] for d in lotes.values() if d.get('estructura_19300')), [])

def versiones(i):
    i = alias.get(i, i)
    return [n for d in lotes.values() for n in d.get('normas', []) if alias.get(n['id'], n['id']) == i]

stats = collections.Counter()
novedades_fix = None
for v, f in fixes:
    pend = []
    for c in f.get('cambios') or []:
        if c['id'] == '__raiz__':
            if c['campo'] == 'estructura_19300': estructura = c['valor']
            if c['campo'] == 'novedades': novedades_fix = c['valor']
            continue
        vs = versiones(c['id'])
        if not vs: avisos.append(f'{v}: cambio sin norma {c["id"]}'); continue
        objs = []
        for n in vs:
            if 'art' in c:
                arts = n.get('articulos') or []
                if c['art'] is None:
                    a = next((x for x in arts if x.get('num') in (None, '', 'None') and (not c.get('epigrafe_actual') or x.get('epigrafe') == c['epigrafe_actual'])), None)
                else:
                    a = next((x for x in arts if artnum(x.get('num')) == artnum(c['art'])), None)
                if a is not None: objs.append(a)
            else: objs.append(n)
        pend.append((c, objs))
    for c, objs in pend:           # se resuelven todos los destinos antes de aplicar, para que renumerar no rompa cambios posteriores
        for o in objs:
            o[c['campo']] = c['valor']
            if 'art' not in c and c['campo'] == 'id_norma_bcn' and c['valor']: o['url'] = f'https://www.bcn.cl/leychile/navegar?idNorma={c["valor"]}'
        stats['cambios' if objs else 'cambios_sin_destino'] += 1
        if not objs and c['id'] not in ('ley-21850', 'ds-10-2025-mma'): avisos.append(f'{v}: cambio sin artículo {c["id"]} art {c.get("art")}')
    for c in f.get('art_eliminar') or []:
        for n in versiones(c['id']):
            if c['art'] is None: n['articulos'] = [x for x in n.get('articulos') or [] if x.get('num') not in (None, '', 'None')]
            else: n['articulos'] = [x for x in n.get('articulos') or [] if artnum(x.get('num')) != artnum(c['art'])]
        stats['art_eliminar'] += 1
    for c in f.get('art_agregar') or []:
        a = c['articulo']
        for n in versiones(c['id']):
            n['articulos'] = [x for x in n.get('articulos') or [] if artnum(x.get('num')) != artnum(a['num'])] + [copy.deepcopy(a)]
        stats['art_agregar'] += 1
    for c in f.get('rel_eliminar') or []:
        d = alias.get(c['destino'], c['destino'])
        def coincide(r):
            if alias.get(r.get('destino'), r.get('destino')) != d: return False
            if c.get('tipo') and r.get('tipo') != c['tipo']: return False
            for k in ('art_origen', 'art_destino'):
                if k in c and c[k] is not None and str(r.get(k)) != str(c[k]): return False
            return True
        for n in versiones(c['id']): n['relaciones'] = [r for r in n.get('relaciones') or [] if not coincide(r)]
        stats['rel_eliminar'] += 1
    for c in f.get('rel_agregar') or []:
        r = c['relacion']
        vs = versiones(c['id'])
        if not vs: avisos.append(f'{v}: rel_agregar sin norma {c["id"]}')
        for n in vs:
            if not any(x.get('tipo') == r['tipo'] and x.get('destino') == r['destino'] and str(x.get('art_origen')) == str(r.get('art_origen')) and str(x.get('art_destino')) == str(r.get('art_destino')) for x in n.get('relaciones') or []):
                n.setdefault('relaciones', []).append(copy.deepcopy(r))
        stats['rel_agregar'] += 1
    for c in f.get('pas_cambios') or []:
        for p in pas:
            if str(p['art']) == str(c['art']):
                p[c['campo']] = c['valor']
                if c['campo'] == 'organismo': p['organismo_verificado'] = True
        stats['pas_cambios'] += 1
canon = {}
for v, f in fixes:
    if v == 'v1': canon['ley-21850'] = {artnum(c['articulo']['num']) for c in f.get('art_agregar') or [] if c['id'] == 'ley-21850'}
for i, nums in canon.items():
    for n in versiones(i): n['articulos'] = [x for x in n.get('articulos') or [] if artnum(x.get('num')) in nums]
eliminar = {i for _, f in fixes for i in (f.get('eliminar') or []) if i not in alias}

# ---- fusión de duplicados entre lotes
def riqueza(n): return len(n.get('articulos') or []) * 3 + len(n.get('relaciones') or []) + len(n.get('resumen') or '') / 200
normas = {}
for nombre, d in lotes.items():
    for n in d.get('normas', []):
        n['_orig'] = n['id']; n['id'] = alias.get(n['id'], n['id']); n['_lote'] = nombre
        if n['id'] in eliminar: continue
        if n['id'] not in normas: normas[n['id']] = n; continue
        a, b = normas[n['id']], n
        keep, other = (a, b) if riqueza(a) >= riqueza(b) else (b, a)
        if a['_orig'] != b['_orig']: keep, other = (a, b) if a['_orig'] == a['id'] else (b, a)
        for r in other.get('relaciones') or []:
            iguales = [x for x in keep.get('relaciones') or [] if x.get('tipo') == r.get('tipo') and alias.get(x.get('destino'), x.get('destino')) == alias.get(r.get('destino'), r.get('destino'))]
            if not iguales: keep.setdefault('relaciones', []).append(r)
            elif r.get('destino') == 'ley-19300' and r.get('tipo') == 'modifica' and other['_lote'] == 'r1_nucleo':
                keep['relaciones'] = [x for x in keep['relaciones'] if x not in iguales] + [r]   # prevalece la versión auditada contra versiones históricas
        for k in ('id_norma_bcn', 'url', 'fecha_publicacion', 'ultima_modificacion', 'organismo', 'titulo_oficial', 'relevancia_titulares'):
            if not keep.get(k) and other.get(k): keep[k] = other[k]
        keep['fuentes_consultadas'] = list(dict.fromkeys((keep.get('fuentes_consultadas') or []) + (other.get('fuentes_consultadas') or [])))
        for k in ('id_norma_bcn', 'fecha_publicacion', 'estado'):
            if a.get(k) and b.get(k) and a[k] != b[k]: avisos.append(f'CONFLICTO {n["id"]}.{k}: {a["_lote"]}={a[k]} vs {b["_lote"]}={b[k]}')
        normas[n['id']] = keep

def clave_art(a):
    m = re.match(r'\s*(\d+)\s*[°º]?\s*(.*)', str(a.get('num')))
    orden = ['', 'bis', 'ter', 'quáter', 'quater', 'quinquies', 'sexies', 'septies', 'octies']
    if not m: return (10**6, 0, str(a.get('num')))
    suf = m.group(2).strip().lower()
    return (int(m.group(1)), orden.index(suf) if suf in orden else 20, suf)

# ---- capas editoriales verificadas (avisos de vigencia y novedades)
extra = json.load(open(f'{BASE}/data/editorial.json', encoding='utf-8')) if os.path.exists(f'{BASE}/data/editorial.json') else {}
out = []
for i, n in normas.items():
    if n.get('categoria') not in CATS: avisos.append(f'CATEGORIA {i}: {n.get("categoria")}')
    if n.get('id_norma_bcn'): n['url'] = f'https://www.bcn.cl/leychile/navegar?idNorma={n["id_norma_bcn"]}'
    if not n.get('url'): avisos.append(f'SIN URL {i}')
    if not n.get('anio') and n.get('fecha_publicacion'): n['anio'] = int(n['fecha_publicacion'][:4])
    rels, vistos = [], set()
    for r in n.get('relaciones') or []:
        r['destino'] = alias.get(r.get('destino'), r.get('destino'))
        if r.get('tipo') not in RELS: avisos.append(f'REL tipo {i}: {r.get("tipo")}'); r['tipo'] = 'remite'
        k = (r['tipo'], r['destino'], str(r.get('art_origen')), str(r.get('art_destino')))
        if r['destino'] and r['destino'] != i and k not in vistos: vistos.add(k); rels.append(r)
    n['relaciones'] = rels
    arts = [a for a in n.get('articulos') or [] if a.get('num') not in (None, '', 'None')]
    if len(arts) != len(n.get('articulos') or []): avisos.append(f'ART sin número descartado en {i}')
    for a in arts:
        a['num'] = re.sub(r'^\s*art(ículo|\.)?\s*', '', str(a['num']), flags=re.I).strip()
        for k in ('nota', 'fuente', 'verificado'): a.pop(k, None)
    if i == 'ley-19300': arts.sort(key=lambda a: (1 if re.search('transitor', str(a.get('num')) + str(a.get('titulo')), re.I) else 0,) + clave_art(a))
    n['articulos'] = arts
    if i in (extra.get('avisos') or {}) and not n.get('aviso'): n['aviso'] = extra['avisos'][i]
    if i in (extra.get('categoria') or {}): n['categoria'] = extra['categoria'][i]
    if i.startswith('of-') and extra.get('fuente_sea') and extra['fuente_sea'] not in (n.get('fuentes_consultadas') or []): n.setdefault('fuentes_consultadas', []).append(extra['fuente_sea'])
    for k in ('_lote', '_orig', 'confianza', 'notas_verificacion', 'estructura'): n.pop(k, None)
    out.append(n)

ids = {n['id'] for n in out}
porid = {n['id']: n for n in out}
for n in out:                      # normaliza la dirección: la norma chilena implementa el tratado
    if n['tipo'] != 'Tratado': continue
    for r in [r for r in n['relaciones'] if r['tipo'] == 'implementa_tratado']:
        n['relaciones'].remove(r)
        t = porid.get(r['destino'])
        if t is None: r['tipo'] = 'remite'; n['relaciones'].append(r); continue
        if not any(x['tipo'] == 'implementa_tratado' and x['destino'] == n['id'] for x in t['relaciones']):
            t['relaciones'].append({'tipo': 'implementa_tratado', 'destino': n['id'], 'art_origen': r.get('art_destino'), 'art_destino': r.get('art_origen'), 'nota': r.get('nota')})
for n in out:                      # una norma derogada no puede "reemplazar" a la que la derogó
    n['relaciones'] = [r for r in n['relaciones'] if not (r['tipo'] in ('reemplaza', 'deroga') and r['destino'] in porid and (porid[r['destino']].get('fecha_publicacion') or '0') > (n.get('fecha_publicacion') or '9'))]
colg = collections.Counter(r['destino'] for n in out for r in n['relaciones'] if r['destino'] not in ids)
for p in pas:
    p['norma_fundante_id'] = alias.get(p.get('norma_fundante_id'), p.get('norma_fundante_id'))
    if p.get('norma_fundante_id') and p['norma_fundante_id'] not in ids: colg['PAS→' + p['norma_fundante_id']] += 1
    p['grupo'] = (extra.get('pas_grupo') or {}).get(str(p['art'])) or re.split(r'\s*[\(,;]| y | con | junto ', p.get('organismo') or 'Sin organismo único')[0].strip()
ds40 = next((n for n in out if n['id'] == 'ds-40-2012-mma'), None)
if ds40:
    for n in out:
        n['relaciones'] = [r for r in n['relaciones'] if r['tipo'] != 'pas']          # las aristas PAS se generan solo desde la tabla auditada
    for p in pas:
        t = p.get('norma_fundante_id')
        if t in ids: ds40['relaciones'].append({'tipo': 'pas', 'destino': t, 'art_origen': str(p['art']), 'art_destino': None, 'nota': p['nombre'][:120]})

# ---- sustento textual de los vínculos blandos: ¿alguno de los dos textos oficiales cita al otro?
import xml.etree.ElementTree as ET, unicodedata
_txt = {}
def texto(n):
    b = n.get('id_norma_bcn')
    if not b: return None
    if b not in _txt:
        try:
            r = ET.parse(f'{BASE}/verif/xml/{b}.xml').getroot()
            t = ' '.join(x for x in r.itertext())
            t = unicodedata.normalize('NFD', t.lower()); t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
            _txt[b] = re.sub(r'\s+', ' ', t)
        except Exception: _txt[b] = None
    return _txt[b]
def patron(n):
    num = re.sub(r'\D', '', str(n.get('numero') or '').split('/')[0].split(' ')[0])
    if not num: return None
    pun = f'{int(num):,}'.replace(',', r'\.?')
    an = str(n.get('anio') or '')
    if n['tipo'] == 'Ley': return rf'ley(es)?[^.;]{{0,60}}?\b{pun}\b'
    if n['tipo'] == 'Decreto Supremo': return rf'(decreto|d\.s\.)[^.;]{{0,45}}?n[°ºo.]*\s*{pun}\b[^.;]{{0,90}}?{an}' if an else None
    if n['tipo'] == 'DFL': return rf'fuerza de ley[^.;]{{0,30}}?n[°ºo.]*\s*{pun}\b'
    if n['tipo'] == 'Decreto Ley': return rf'decreto ley[^.;]{{0,20}}?n[°ºo.]*\s*{pun}\b'
    if n['tipo'] == 'Resolución': return rf'resolucion[^.;]{{0,40}}?n[°ºo.]*\s*{pun}\b'
    return None
NOMBRES = {'cpr-1980': r'constitucion politica', 'codigo-penal': r'codigo penal', 'dfl-1122-1981': r'codigo de aguas', 'dfl-725-1967': r'codigo sanitario',
           'ley-18248': r'codigo de mineria', 'dfl-458-1975': r'ley general de urbanismo', 'ds-47-1992-minvu': r'ordenanza general', 'ds-430-1991-economia': r'ley general de pesca',
           'ds-40-2012-mma': r'reglamento del sistema de evaluacion de impacto ambiental', 'ley-19300': r'19\.?300'}
def cita(a, b):
    t = texto(a)
    if not t: return None
    ps = [p for p in (patron(b), NOMBRES.get(b['id'])) if p]
    if b['tipo'] == 'Tratado':
        clave = re.sub(r'[^a-z ]', '', unicodedata.normalize('NFD', (b.get('nombre_corto') or '').lower()).encode('ascii', 'ignore').decode())
        pal = [w for w in clave.split() if len(w) > 5 and w not in ('convencion', 'convenio', 'protocolo', 'acuerdo', 'tratado', 'sobre')]
        if pal: ps.append(r'(convencion|convenio|protocolo|acuerdo|tratado)[^.;]{0,80}?' + pal[0])
    if not ps: return None
    return any(re.search(p, t) for p in ps)
cnt = collections.Counter()
for n in out:
    for r in n['relaciones']:
        if r['tipo'] not in ('complementa', 'remite'): continue
        t = porid.get(r['destino'])
        if not t: continue
        c1, c2 = cita(n, t), cita(t, n)
        r['cita'] = True if (c1 or c2) else (None if (c1 is None and c2 is None) else False)
        cnt[str(r['cita'])] += 1
print('vínculos blandos con cita textual:', dict(cnt))

for p in pas:
    if str(p['art']) in (extra.get('pas_nota') or {}): p['nota'] = extra['pas_nota'][str(p['art'])]
import mejoras
sim, rep_mej = mejoras.aplicar(out, pas, avisos)
print('mejoras:', rep_mej)
cnt = collections.Counter(str(r.get('cita')) for n in out for r in n['relaciones'] if r['tipo'] in ('complementa', 'remite') and r['destino'] in porid)
def fechas_cl(o, clave=None):
    if isinstance(o, dict): return {k: (v if k in ('url', 'fuentes_consultadas', 'fecha_publicacion', 'version_bcn', 'id', 'destino', 'norma_fundante_id') else fechas_cl(v, k)) for k, v in o.items()}
    if isinstance(o, list): return [fechas_cl(x, clave) for x in o]
    if isinstance(o, str): return re.sub(r'\b(\d{4})-(\d{2})-(\d{2})\b', r'\3-\2-\1', o)
    return o
for n in out:      # el nombre del organismo va sin aclaraciones (para filtrar y contar); la aclaración se guarda aparte
    notas, base = {}, []
    for o in n.get('organismos_competentes') or []:
        m = re.match(r'^(.*?)\s*\((.+)\)\s*$', o)
        nb = m.group(1).strip() if m else o
        if m: notas[nb] = m.group(2).strip()
        if nb not in base: base.append(nb)
    if base: n['organismos_competentes'] = base
    if notas: n['organismos_nota'] = notas
out = fechas_cl(out); pas = fechas_cl(pas); sim = fechas_cl(sim)
porid = {n['id']: n for n in out}
out.sort(key=lambda n: (n.get('fecha_publicacion') or str(n.get('anio') or 0), n['id']))
ctl = json.load(open(f'{BASE}/verif/control_final_bcn.json')) if os.path.exists(f'{BASE}/verif/control_final_bcn.json') else {}
data = {'meta': {'corte': '10-11-2026', 'nota': 'Datos contrastados con las fichas y textos oficiales de la Biblioteca del Congreso Nacional al 10-11-2026.',
                 'con_bcn': sum(1 for n in out if n.get('id_norma_bcn')), 'sin_bcn': sum(1 for n in out if not n.get('id_norma_bcn')),
                 'bcn_ok': ctl.get('ok'), 'correcciones': sum(v for k, v in stats.items() if k != 'cambios_sin_destino'),
                 'mejoras': rep_mej, 'fuera': len(colg), 'tematicos': cnt.get('False', 0) + cnt.get('None', 0)},
        'normas': out, 'pas': pas, 'estructura_19300': estructura, 'novedades': sim.pop('_novedades', None) or novedades_fix or extra.get('novedades') or [], 'sim': sim}
json.dump(data, open(f'{BASE}/app/data.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
html = open(f'{BASE}/app/template.html', encoding='utf-8').read()
html = html.replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
open(f'{BASE}/app/index.html', 'w', encoding='utf-8').write(html)
print(f'normas={len(out)} pas={len(pas)} arts={sum(len(n["articulos"]) for n in out)} rels={sum(len(n["relaciones"]) for n in out)} html={len(html)//1024}KB')
print('fixes aplicados:', dict(stats))
print('destinos colgantes:', dict(colg.most_common(60)))
print('\n'.join(avisos) or 'sin avisos')
