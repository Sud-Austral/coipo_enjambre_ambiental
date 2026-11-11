"""Asocia cada artículo resumido con su parte oficial en BCN (idParte) leyendo el XML de la norma."""
import re, unicodedata, xml.etree.ElementTree as ET
NS = '{http://www.leychile.cl/esquemas}'
SUF = ['bis', 'ter', 'quater', 'quinquies', 'sexies', 'septies', 'octies', 'nonies']
ORD = {'unico':1,'primero':1,'segundo':2,'tercero':3,'cuarto':4,'quinto':5,'sexto':6,'septimo':7,'octavo':8,'noveno':9,'decimo':10,
       'undecimo':11,'duodecimo':12,'decimotercero':13,'decimocuarto':14,'decimoquinto':15,'decimosexto':16,'decimoseptimo':17,
       'decimoctavo':18,'decimonoveno':19,'vigesimo':20}
def nrm(s):
    s = unicodedata.normalize('NFD', str(s).lower()); return ''.join(c for c in s if unicodedata.category(c) != 'Mn')
def clave(txt):
    """(numero, sufijo) del encabezado de un artículo o de un num del visor; None si no se reconoce."""
    t = nrm(txt).strip()
    t = re.sub(r'^(losma|art(iculo|\.)?s?)\s*', '', t).strip()
    t = re.sub(r'^(art(iculo|\.)?)\s*', '', t).strip()
    m = re.match(r'(\d+)\s*[°ºo]?\.?\s*-?\s*(bis|ter|quater|quinquies|sexies|septies|octies|nonies)?\b', t)
    if m: return (int(m.group(1)), m.group(2) or '')
    t2 = re.sub(r'\s+', '', t.split('.')[0].split('-')[0])
    for k in sorted(ORD, key=len, reverse=True):
        if t.startswith(k) or t2.startswith(k):
            resto = t[len(k):].strip()
            if k == 'decimo':
                for u, v in (('tercero',13),('cuarto',14),('quinto',15),('sexto',16),('septimo',17),('octavo',18),('noveno',19),('primero',11),('segundo',12)):
                    if resto.startswith(u): return (v, '')
            if k == 'vigesimo':
                for u, v in (('primero',21),('segundo',22),('tercero',23),('cuarto',24),('quinto',25),('sexto',26),('septimo',27),('octavo',28),('noveno',29)):
                    if resto.startswith(u): return (v, '')
            return (ORD[k], '')
    return None
def indice(xml):
    r = ET.parse(xml).getroot(); idx = {}
    def rec(e, dentro):
        for h in e:
            if h.tag != NS + 'EstructuraFuncional' and h.tag != NS + 'EstructurasFuncionales':
                continue
            if h.tag == NS + 'EstructurasFuncionales': rec(h, dentro); continue
            es_art = h.get('tipoParte') == 'Artículo'
            if es_art:
                t = re.sub(r'\s+', ' ', h.findtext(NS + 'Texto') or '').strip()
                k = clave(t[:60])
                if k: idx.setdefault((k, h.get('transitorio') == 'transitorio', dentro), []).append((h.get('idParte'), t[:160]))
            rec(h, dentro or es_art)
    rec(r, False)
    return idx, r.get('fechaVersion')
def enlazar(norma, xml):
    idx, ver = indice(xml); n_ok = 0
    hay_interno = any(k[2] for k in idx)
    for a in norma.get('articulos') or []:
        num = str(a.get('num'))
        k = clave(num)
        if not k: continue
        trans = 'transitor' in nrm(num)
        interno = nrm(num).startswith('losma')
        cands = idx.get((k, trans, interno))
        if not cands and not interno: cands = idx.get((k, trans, True))
        if not cands and trans: cands = (idx.get((k, True, True)) or []) + (idx.get((k, True, False)) or [])
        if cands and len(cands) == 1:
            a['id_parte'] = cands[0][0]; n_ok += 1
    return n_ok, ver
