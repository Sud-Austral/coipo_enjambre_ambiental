"""Integra las mejoras verificadas: articulado completo, depuración de vínculos, etapas, simulador y enlaces por artículo."""
import json, os, re, sys, glob, collections
sys.path.insert(0, '/home/claude/tools'); import enlaces
B = '/home/claude'
def carga(p):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
def artnum(x): return re.sub(r'\s+', ' ', str(x)).strip().lower()
RELS = {"reglamenta","modifica","crea_organo","deroga","reemplaza","remite","complementa","implementa_tratado","pas"}

def aplicar(out, pas, avisos):
    porid = {n['id']: n for n in out}; rep = collections.Counter()
    # 1) articulado completo + auditoría a1/a2
    fx = [f for f in (carga(f'{B}/verif2/fix_a1.json'), carga(f'{B}/verif2/fix_a2.json')) if f]
    for ruta in sorted(glob.glob(f'{B}/data2/full_*.json')):
        d = carga(ruta); n = porid.get(d['id'])
        if not n: avisos.append(f'full sin norma {d["id"]}'); continue
        arts = d['articulos']
        for f in fx:
            for c in f.get('cambios') or []:
                if c['id'] != d['id']: continue
                a = next((x for x in arts if artnum(x.get('num')) == artnum(c['art'])), None)
                if a is None: avisos.append(f'a1/a2: sin art {c["id"]} {c["art"]}'); continue
                a[c['campo']] = c['valor']; rep['correcciones_articulado'] += 1
            for c in f.get('art_eliminar') or []:
                if c['id'] == d['id']: arts = [x for x in arts if artnum(x.get('num')) != artnum(c['art'])]; rep['correcciones_articulado'] += 1
            for c in f.get('art_agregar') or []:
                if c['id'] == d['id']: arts.append(c['articulo']); rep['correcciones_articulado'] += 1
        n['articulos'] = [{k: a.get(k) for k in ('num', 'epigrafe', 'resumen', 'obliga_titular', 'titulo', 'derogado') if a.get(k) not in (None, False, '') or k == 'obliga_titular'} for a in arts]
        for a in n['articulos']: a['num'] = str(a['num']); a['obliga_titular'] = bool(a.get('obliga_titular'))
        nomT, nomP = {}, {}
        for t in d.get('estructura') or []:
            nomT[t.get('titulo')] = t.get('nombre')
            for p in t.get('parrafos') or []: nomP[f"{t.get('titulo')}, {p.get('parrafo')}"] = p.get('nombre')
        def rot(tx):
            if not tx: return tx
            base = tx.split(',')[0].strip(); pref = 'LOSMA, ' if tx.startswith('LOSMA') else ''
            clave = tx[len(pref):] if pref else tx; base = clave.split(',')[0].strip()
            r = pref + base + (f' · {nomT[base]}' if nomT.get(base) else '')
            if ',' in clave:
                par = clave.split(',', 1)[1].strip(); r += f' — {par}' + (f' · {nomP[clave]}' if nomP.get(clave) else '')
            return r
        for a in n['articulos']:
            if a.get('titulo'): a['titulo'] = rot(a['titulo'])
        n['articulos'].sort(key=lambda a: 1 if 'aprobatorio' in str(a.get('titulo')).lower() else 0)
        n['completo'] = True; rep['articulos_completos'] += len(arts)
    # 2) vínculos temáticos: decisiones t1/t2 + auditoría a5
    tem = carga(f'{B}/data2/tematicos.json') or []
    dec = {}
    for t in ('t1', 't2'):
        f = carga(f'{B}/verif2/fix_{t}.json')
        for x in (f or {}).get('decisiones', []): dec[x['k']] = dict(x)
    a5 = carga(f'{B}/verif2/fix_a5.json') or {}
    for x in a5.get('vinculos') or []:
        k = x['k']; d0 = dec.setdefault(k, {'k': k})
        if x['accion'] == 'eliminar': d0['decision'] = 'eliminar'
        elif x['accion'] in ('corregir', 'restituir'):
            d0['decision'] = 'sustento'
            for c in ('norma_que_cita', 'articulo', 'tipo_corregido', 'nota'):
                if x.get(c): d0[c] = x[c]
    for t in tem:
        d0 = dec.get(t['k']); n = porid.get(t['origen'])
        if not d0 or not n: continue
        r = next((r for r in n['relaciones'] if r['destino'] == t['destino'] and r['tipo'] == t['tipo'] and str(r.get('art_origen')) == str(t['art_origen'])), None)
        if r is None: continue
        if d0.get('decision') == 'eliminar': n['relaciones'].remove(r); rep['vinculos_eliminados'] += 1
        elif d0.get('decision') == 'sustento':
            tipo = d0.get('tipo_corregido') if d0.get('tipo_corregido') in RELS else r['tipo']
            if tipo != r['tipo'] and any(x is not r and x['tipo'] == tipo and x['destino'] == r['destino'] for x in n['relaciones']):
                n['relaciones'].remove(r); rep['vinculos_fusionados'] += 1; continue
            if tipo == 'implementa_tratado' and porid[t['destino']]['tipo'] != 'Tratado': tipo = r['tipo']
            if tipo == 'modifica' and (porid[t['destino']].get('fecha_publicacion') or '0') > (n.get('fecha_publicacion') or '9'): tipo = 'remite'
            r['tipo'] = tipo; r['cita'] = True
            if d0.get('nota'): r['nota'] = d0['nota']
            if d0.get('articulo'):
                if d0.get('norma_que_cita') == t['destino']: r['art_destino'] = d0['articulo']; r['art_origen'] = None if not r.get('art_origen') else r['art_origen']
                else: r['art_origen'] = d0['articulo']
            rep['vinculos_confirmados'] += 1
        else: rep['vinculos_no_verificables'] += 1
    for x in a5.get('vinculos_nuevos') or []:
        n = porid.get(x.get('origen'))
        if n and x.get('destino') in porid and x.get('tipo') in RELS and not any(r['tipo'] == x['tipo'] and r['destino'] == x['destino'] for r in n['relaciones']):
            n['relaciones'].append({'tipo': x['tipo'], 'destino': x['destino'], 'art_origen': x.get('art_origen'), 'art_destino': x.get('art_destino'), 'nota': x.get('nota'), 'cita': True}); rep['vinculos_nuevos'] += 1
    # 3) etapas
    et = carga(f'{B}/data2/etapas.json') or {'normas': {}, 'pas': {}}
    for x in a5.get('etapas') or []:
        et['normas'][x['id']] = {'rol': x['rol'], 'etapas': x.get('etapas') or [], 'sustento': x.get('sustento') or {}}; rep['etapas_corregidas'] += 1
    for x in a5.get('etapas_pas') or []:
        et['pas'][str(x['art'])] = {'etapas': x['etapas'], 'motivo': x.get('motivo')}; rep['etapas_corregidas'] += 1
    VAL = ['diseno', 'evaluacion', 'construccion', 'operacion', 'cierre']
    for n in out:
        e = et['normas'].get(n['id'])
        if not e: continue
        n['rol'] = e.get('rol'); n['etapas'] = [k for k in VAL if k in (e.get('etapas') or [])]
        n['etapas_sustento'] = {k: v for k, v in (e.get('sustento') or {}).items() if k in n['etapas']}
    for p in pas:
        e = et['pas'].get(str(p['art']))
        if e: p['etapas'] = [k for k in VAL if k in (e.get('etapas') or [])]
    # 4) simulador + auditoría a3/a4
    sim = {'tipologias': [], 'condiciones': [], 'planes': []}
    st, sc = carga(f'{B}/data2/sim_tipologias.json'), carga(f'{B}/data2/sim_condiciones.json')
    def fixbloque(bloques, fix, clave):
        if not fix: return
        idx = {b['id']: b for b in bloques}
        for x in fix.get('normas') or []:
            b = idx.get(x.get(clave));
            if not b: continue
            if x['accion'] in ('eliminar', 'corregir'):
                ref = x.get('art_actual')
                hay = [y for y in b.get('normas', []) if y['id'] == x['id'] and (ref is None or str(y.get('art')) == str(ref))]
                if not hay: hay = [y for y in b.get('normas', []) if y['id'] == x['id']][:1]
                if not hay: avisos.append(f'sim: sin entrada {x.get(clave)} {x["id"]}')
                b['normas'] = [y for y in b.get('normas', []) if y not in hay]
            if x['accion'] in ('corregir', 'agregar'): b['normas'].append({'id': x['id'], 'fuerza': x.get('fuerza') or 'segun_caso', 'art': x.get('art'), 'motivo': x.get('motivo')})
            rep['simulador_correcciones'] += 1
        for x in fix.get('pas') or []:
            b = idx.get(x.get(clave))
            if not b: continue
            if x['accion'] in ('eliminar', 'corregir'): b['pas'] = [y for y in b.get('pas', []) if str(y['art']) != str(x['art'])]
            if x['accion'] in ('corregir', 'agregar'): b.setdefault('pas', []).append({'art': x['art'], 'fuerza': x.get('fuerza') or 'segun_caso', 'motivo': x.get('motivo')})
            rep['simulador_correcciones'] += 1
        for x in (fix.get('ingreso') or []) + (fix.get('efecto_seia') or []):
            b = idx.get(x.get(clave))
            if not b: continue
            campo = 'ingreso' if 'ingreso' in b else 'efecto_seia'
            ref = x.get('art_actual') or x.get('art')
            b[campo] = [y for y in b.get(campo, []) if not (y.get('norma') == x.get('norma') and str(y.get('art')) == str(ref))]
            if x['accion'] == 'corregir': b[campo].append({'norma': x['norma'], 'art': x.get('art'), 'texto': x.get('texto')})
            rep['simulador_correcciones'] += 1
        for x in fix.get('organismos') or []:
            b = idx.get(x.get(clave))
            if b: b['organismos'] = x['valor']
    if st:
        fixbloque(st['tipologias'], carga(f'{B}/verif2/fix_a3.json'), 'tip'); sim['tipologias'] = st['tipologias']
    if sc:
        f4 = carga(f'{B}/verif2/fix_a4.json'); fixbloque(sc['condiciones'], f4, 'cond'); sim['condiciones'] = sc['condiciones']
        planes = sc.get('planes_por_zona') or []
        for x in (f4 or {}).get('planes_por_zona') or []:
            planes = [p for p in planes if p['id'] != x['id']]
            if x['accion'] == 'corregir': planes.append({'id': x['id'], 'territorio': x['territorio']})
        sim['planes'] = [{'id': p['id'], 'territorio': p.get('territorio')} for p in planes if p['id'] in porid and porid[p['id']]['estado'] == 'vigente']
    fixbloque(sim['tipologias'] + sim['condiciones'], carga(f'{B}/verif2/fix_a6.json'), 'bloque')
    validos_pas = {str(p['art']) for p in pas}
    for b in sim['tipologias'] + sim['condiciones']:
        antes = len(b.get('normas', []))
        b['normas'] = [x for x in b.get('normas', []) if x['id'] in porid and porid[x['id']]['estado'] == 'vigente']
        if len(b['normas']) != antes: avisos.append(f'sim {b["id"]}: {antes - len(b["normas"])} normas descartadas por id o vigencia')
        b['pas'] = [x for x in b.get('pas', []) if str(x['art']) in validos_pas and str(x['art']) != '121']
        for k in ('meta', 'notas', 'fuera_del_visor'): b.pop(k, None)
    # 4b) auditoría de coherencia normativa (n1): se aplica sobre el conjunto ya integrado
    novedades_n1 = None
    for n1 in (carga(f'{B}/verif2/fix_n1.json') or {}, carga(f'{B}/verif2/fix_n1b.json') or {}):
        for x in n1.get('norma') or []:
            n = porid.get(x['id'])
            if not n: avisos.append(f'n1: sin norma {x["id"]}'); continue
            n[x['campo']] = x['valor']; rep['coherencia'] += 1
        for x in n1.get('articulo') or []:
            n = porid.get(x['id']); a = n and next((y for y in n['articulos'] if artnum(y.get('num')) == artnum(x['art'])), None)
            if a is None: avisos.append(f'n1: sin artículo {x["id"]} {x["art"]}'); continue
            a[x['campo']] = x['valor']; rep['coherencia'] += 1
        for x in n1.get('pas') or []:
            for p in pas:
                if str(p['art']) == str(x['art']): p[x['campo']] = x['valor']; rep['coherencia'] += 1
        fixbloque(sim['tipologias'] + sim['condiciones'], {'normas': n1.get('sim_normas'), 'pas': n1.get('sim_pas')}, 'bloque')
        for x in n1.get('rel_eliminar') or []:
            n = porid.get(x['id'])
            if n:
                antes = len(n['relaciones']); n['relaciones'] = [r for r in n['relaciones'] if not (r['destino'] == x['destino'] and (not x.get('tipo') or r['tipo'] == x['tipo']))]
                rep['coherencia'] += antes - len(n['relaciones'])
        mapa = dict(n1.get('organismos_normalizar') or {})
        if mapa.get('Subsecretaría de Pesca y Acuicultura') == 'SUBPESCA': mapa.pop('Subsecretaría de Pesca y Acuicultura'); mapa['SUBPESCA'] = 'Subsecretaría de Pesca y Acuicultura'
        if mapa:
            for n in out:
                if n.get('organismos_competentes'): n['organismos_competentes'] = list(dict.fromkeys(mapa.get(o, o) for o in n['organismos_competentes']))
            for b in sim['condiciones']:
                if b.get('organismos'): b['organismos'] = list(dict.fromkeys(mapa.get(o, o) for o in b['organismos']))
        for x in n1.get('articulo_agregar') or []:
            n = porid.get(x['id'])
            if n and not any(artnum(y.get('num')) == artnum(x['art']) for y in n['articulos']):
                n['articulos'].append({'num': str(x['art']), 'epigrafe': x.get('epigrafe'), 'resumen': x.get('resumen'), 'obliga_titular': bool(x.get('obliga_titular'))}); rep['coherencia'] += 1
        novedades_n1 = n1.get('novedades') or novedades_n1
    sim['_novedades'] = novedades_n1

    tot = ok = 0
    for n in out:
        b = n.get('id_norma_bcn'); x = f'{B}/verif/xml/{b}.xml'
        if not b or not os.path.exists(x): continue
        try: k, ver = enlaces.enlazar(n, x)
        except Exception as e: avisos.append(f'enlace {n["id"]}: {e}'); continue
        tot += len(n['articulos']); ok += k
        if ver and not ver.startswith('2222'): n['version_bcn'] = ver
    rep['articulos_enlazados'] = ok; rep['articulos_con_ficha_bcn'] = tot
    return sim, dict(rep)
