#!/usr/bin/env python3
"""Synchronisation KoboToolbox -> data.json de l'application El Behgua (version en ligne).

Usage : python3 kobo_sync.py data.json data_new.json  (clé API dans la variable KOBO_TOKEN)
Code de sortie : 0 = nouvelles fiches intégrées (publier data_new.json), 3 = rien de nouveau, 1 = erreur.
Portage fidèle de KOBO.integrate() de l'application (et de la macro Kobo_Ecrire du classeur).
"""
import json, os, sys, time, datetime, urllib.request, urllib.parse, base64

def day(s):
    if s in (None, ''): return None
    s = str(s).strip()
    try: return (datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10])) - datetime.date(1970, 1, 1)).days
    except Exception: return None
def num(v):
    if v in (None, ''): return None
    try:
        x = float(str(v).replace(',', '.'))
        return None if x != x or x in (float('inf'), float('-inf')) else x
    except Exception: return None
def fd(d): x = datetime.date(1970, 1, 1) + datetime.timedelta(days=d); return x.strftime('%d/%m/%Y')
def stamp(): return datetime.datetime.now(datetime.timezone.utc).strftime('%d/%m/%Y %H:%M')
def find(o, name):
    if not isinstance(o, dict): return None
    name = name.lower()
    for k, v in o.items():
        l = k.lower()
        if l == name or l.endswith('/' + name): return v
    return None
def s_(v): return '' if v is None else str(v).strip()
def tray(v, autre):
    s = s_(v)
    return (s_(autre) or 'Autre') if s.lower() == 'autre' else s.replace('_', ' ')
TYPES = {'velage': 'Vêlage', 'tarissement': 'Tarissement', 'chaleur': 'Chaleur', 'ia': 'Insémination (IA)', 'diag_gestation': 'Diagnostic gestation', 'maladie': 'Maladie / Traitement', 'mammite': 'Mammite', 'vaccination': 'Vaccination', 'deparasitage': 'Déparasitage', 'mortalite': 'Mortalité', 'sortie': 'Sortie / Vente', 'entree': 'Entrée', 'avortement': 'Avortement'}
MOTIFS = {'acidite': 'Acidité', 'densite': 'Densité', 'alcool': 'Test alcool positif', 'proprete': 'Propreté', 'temperature': 'Température', 'mouillage': 'Mouillage'}

GEST = {'gestante': 'Gestante', 'vide': 'Vide', 'douteux': 'Douteux, à revoir'}
def gest(res, mois, detail, lieu):
    parts = []
    if s_(res): parts.append(GEST.get(s_(res).lower(), s_(res)) + (' (%s mois)' % s_(mois) if s_(mois) else ''))
    if s_(detail): parts.append(s_(detail))
    if lieu == 'nbeika': parts.append('Nbeika')
    return ' · '.join(parts)

def parse(s):
    f = lambda n: find(s, n)
    F = dict(idx=s_(f('_id')), uuid=s_(f('_uuid')), d=day(f('date_traite')), session=s_(f('session')).lower(), trayeur=tray(f('trayeur'), f('trayeur_autre')),
             heure=s_(f('heure_debut'))[:5], livraison=s_(f('livraison')).lower(), bon=s_(f('n_bon')), livre=num(f('livre_mpe')), recu=num(f('recu_smpl')),
             refus=num(f('refus')), motif=s_(f('motif')), dens=num(f('densite')), alcool=s_(f('test_alcool')).lower(), traites=[], events=[], lieu=s_(f('lieu')))
    if not F['trayeur'] and s_(f('agent')): F['trayeur'] = s_(f('agent'))
    for grp, cid, cl in (('traite', 'vache_id', 'litres'), ('autres', 'autre_id', 'autre_litres')):
        for e in (f(grp) or []):
            F['traites'].append(dict(id=s_(find(e, cid)).upper(), L=num(find(e, cl)), tray=tray(find(e, 'trayeur'), find(e, 'trayeur_autre'))))
    for e in (f('evenements') or []):
        g = lambda n: find(e, n)
        F['events'].append(dict(type=TYPES.get(s_(g('ev_type')).lower(), 'Autre'), id=s_(g('ev_id')).upper(), newid=s_(g('ev_nouvel_id')).upper(), race=s_(g('ev_race')).upper(),
                                statut=s_(g('ev_statut')).lower(), velage=day(g('ev_velage')), detail=gest(g('ev_gestation'), g('ev_mois'), g('ev_detail'), F['lieu']), trait=s_(g('ev_traitement')), retrait=num(g('ev_retrait')), rappel=day(g('ev_rappel'))))
    return F

def decode(raw):
    dic, L = raw['dict'], raw['lait']; rows = []; d = 0
    for i in range(len(L['id'])):
        d += L['d'][i]
        rows.append(dict(d=d, id=dic[L['id'][i]], race=dic[L['race'][i]], m=L['m'][i], s=L['s'][i], t=L['t'][i], src=dic[L['src'][i]], obs=dic[L['obs'][i]],
                         tm=dic[L['tm'][i]], hm=dic[L['hm'][i]], ts=dic[L['ts'][i]], hs=dic[L['hs'][i]]))
    return rows
def encode(raw, rows):
    dic, dl = {}, []
    def I(s):
        s = s or ''
        if s not in dic: dic[s] = len(dl); dl.append(s)
        return dic[s]
    rows = sorted(rows, key=lambda r: (r['d'], r['id']))
    L = {k: [] for k in ['d', 'id', 'race', 'm', 's', 't', 'src', 'obs', 'tm', 'hm', 'ts', 'hs']}; p = 0
    for r in rows:
        L['d'].append(r['d'] - p); p = r['d']
        for k in ['id', 'race', 'src', 'obs', 'tm', 'hm', 'ts', 'hs']: L[k].append(I(r.get(k)))
        L['m'].append(r.get('m')); L['s'].append(r.get('s'))
        L['t'].append(r.get('t') if r.get('m') is None and r.get('s') is None else None)
    raw['dict'] = dl; raw['lait'] = L

def integrate(raw, fiches):
    rows = decode(raw); key = {(r['d'], r['id']): r for r in rows}
    P = raw['param']; reg = raw['reg']; ev = raw['ev']; klog = raw['kobolog']
    regmap = {v['id']: v for v in reg}
    def race_of(i):
        if i in regmap: return regmap[i].get('race') or ''
        for r in rows:
            if r['id'] == i: return r.get('race') or ''
        return ''
    def add_event(e, maj=True):
        ev.append([e['d'], e['id'], e['type'], e.get('detail', ''), e.get('trait', ''), e.get('retrait'), e.get('rappel'), e.get('obs', ''), e.get('src', '')])
        v = regmap.get(e['id'])
        if not v or not maj: return
        t = e['type']
        if t == 'Vêlage': v['statut'] = 'En lactation'; v['velage'] = e['d']; v['nbv'] = (v.get('nbv') or 0) + 1
        elif t == 'Tarissement': v['statut'] = 'Tarie'
        elif t == 'Mortalité': v['statut'] = 'Morte'; v['sortie'] = e['d']; v['motif'] = 'Mortalité'
        elif t == 'Sortie / Vente': v['statut'] = 'Sortie'; v['sortie'] = e['d']; v['motif'] = e.get('detail', '')
    def reg_add(i, race, dEnt, orig, st, dVel):
        v = regmap.get(i)
        if v:
            if v['statut'] == 'Sortie':
                v['obs'] = 'Sortie' + (' le ' + fd(v['sortie']) if v.get('sortie') is not None else '') + (' (%s)' % v['motif'] if v.get('motif') else '') + ', réintégrée le ' + fd(dEnt) + (' | ' + v['obs'] if v.get('obs') else '')
                v.update(sortie=None, motif='', entree=dEnt)
                if orig: v['origine'] = orig
                if race: v['race'] = race
                if dVel is not None and (v.get('velage') is None or dVel > v['velage']): v['velage'] = dVel; v['nbv'] = (v.get('nbv') or 0) + 1
                v['statut'] = st
                return True, '%s : réintégrée (était sortie), statut %s' % (i, st)
            if v['statut'] == 'Morte': return False, '%s : identifiant d’une vache MORTE, non ajoutée (vérifier le numéro)' % i
            return False, '%s : déjà présente dans le registre (%s)' % (i, v['statut'])
        v = dict(id=i, alias='', race=race, entree=dEnt, origine=orig, velage=dVel, nbv=1 if dVel is not None else 0, statut=st, sortie=None, motif='', obs='')
        reg.append(v); regmap[i] = v
        return True, '%s : ajoutée au registre (%s)' % (i, st)
    deja = {(k[0] if isinstance(k, list) else k.get('uuid')) for k in klog}; seen = set(); src = 'Kobo ' + stamp(); notes = []
    nNew = nSkip = nLig = nSm = nEv = 0
    for F in fiches:
        if F['d'] is None: continue
        if F['uuid'] and F['uuid'] in deja: nSkip += 1; continue
        k0 = F['idx'] + '|' + F['uuid']
        if k0 in seen: continue
        seen.add(k0); nNew += 1; nv = 0; tt = 0.0; ne = 0
        if F['livraison'] == 'oui':
            s = next((x for x in raw['smpl'] if x['d'] == F['d']), None)
            if not s: s = dict(d=F['d'], bon='', livre=None, recu=None, refus=None, motif='', dens=None, alcool='', obs='', prix=None); raw['smpl'].append(s)
            if F['bon']: s['bon'] = F['bon']
            for a, b in (('livre', 'livre'), ('recu', 'recu'), ('refus', 'refus'), ('dens', 'dens')):
                if F[b] is not None: s[a] = F[b]
            if F['motif']: s['motif'] = MOTIFS.get(F['motif'].lower(), 'Autre')
            if F['alcool']: s['alcool'] = 'Positif' if F['alcool'] == 'positif' else 'Négatif'
            s['obs'] = 'Kobo – ' + F['trayeur']
            if P.get('prixLait') is not None: s['prix'] = P['prixLait']
            nSm += 1
        for t in F['traites']:
            if not t['id'] or t['L'] is None: continue
            tr = t['tray'] or F['trayeur']
            r = key.get((F['d'], t['id']))
            if not r:
                r = dict(d=F['d'], id=t['id'], race=race_of(t['id']), m=None, s=None, t=None, src=src, obs='', tm='', hm='', ts='', hs='')
                rows.append(r); key[(F['d'], t['id'])] = r
            if F['session'] == 'matin': r.update(m=t['L'], tm=tr, hm=F['heure'])
            else: r.update(s=t['L'], ts=tr, hs=F['heure'])
            nv += 1; tt += t['L']; nLig += 1
        for e in F['events']:
            i = e['id']
            if e['type'] == 'Entrée':
                i = e['newid']
                st = 'Tarie' if e['statut'] == 'tarie' else 'En lactation'
                if i:
                    ok, note = reg_add(i, e['race'], F['d'], e['detail'], st, e['velage']); notes.append(note)
                    if ok and e['velage'] is not None: add_event(dict(d=e['velage'], id=i, type='Vêlage', src=src), False)
            if i:
                add_event(dict(d=F['d'], id=i, type=e['type'], detail=e['detail'], trait=e['trait'], retrait=e['retrait'], rappel=e['rappel'], obs=('Trayeur : ' + F['trayeur']) if F['trayeur'] else '', src=src))
                ne += 1; nEv += 1
        klog.append(dict(uuid=F['uuid'], d=F['d'], session=F['session'], trayeur=F['trayeur'], heure=F['heure'], nv=nv, total=round(tt, 3), livre=F['livre'] if F['livraison'] == 'oui' else None, nev=ne, at=stamp(), via='Claude (cloud)'))
    encode(raw, rows)
    resume = '%d fiche(s), %d traite(s) vache, %d livraison(s) SMPL, %d événement(s)' % (nNew, nLig, nSm, nEv) + (' · %d déjà importée(s)' % nSkip if nSkip else '') + (' · Registre : ' + ' ; '.join(notes) if notes else '')
    return nNew, resume, notes

def http(method, url, tok, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Token ' + tok, 'Accept': 'application/json', **({'Content-Type': 'application/json'} if body is not None else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        t = r.read().decode('utf-8'); return json.loads(t) if t.strip() else {}

def lists(raw):
    reg = raw['reg']; lact = [v for v in reg if v['statut'] == 'En lactation']
    t1 = 'name,label,rang,race,nb\r\n' + ''.join('%s,%s - %s,%d,%s,%d\r\n' % (v['id'], v['id'], v['race'], k + 1, v['race'], len(lact)) for k, v in enumerate(lact))
    t2 = 'name,label,site\r\n' + ''.join('%s,%s - %s - %s,%s\r\n' % (v['id'], v['id'], v['race'], v['statut'], 'nbeika' if v['statut'] == 'Tarie' else 'elbehgua') for v in reg if v['statut'] in ('En lactation', 'Tarie'))
    t3 = 'name,label\r\n' + ''.join('%s,%s\r\n' % (n.replace(' ', '_').replace(',', ''), n.replace(',', '')) for n in raw['param'].get('trayeurs', []) if n) + 'autre,Autre (écrire le nom) / أخرى\r\n'
    return len(lact), [('vaches.csv', t1), ('vaches_toutes.csv', t2), ('trayeurs.csv', t3)]
def publish_lists(raw, srv, uid, tok):
    n, files = lists(raw); base = '%s/api/v2/assets/%s' % (srv, uid)
    ex = http('GET', base + '/files/?file_type=form_media&format=json&limit=200', tok)
    for f in ex.get('results', []):
        if (f.get('metadata') or {}).get('filename', '').lower() in ('vaches.csv', 'vaches_toutes.csv', 'trayeurs.csv'): http('DELETE', base + '/files/%s/' % f['uid'], tok)
    for fn, txt in files:
        http('POST', base + '/files/?format=json', tok, {'description': 'default', 'file_type': 'form_media', 'metadata': {'filename': fn}, 'base64Encoded': 'data:text/csv;base64,' + base64.b64encode(txt.encode('utf-8')).decode()})
    a = http('GET', base + '/?format=json', tok)
    http('PATCH', base + '/deployment/?format=json', tok, {'active': True, 'version_id': a['version_id']})
    return n

def main():
    src, dst = sys.argv[1], sys.argv[2]
    tok = os.environ.get('KOBO_TOKEN', '').strip()
    raw = json.load(open(src, encoding='utf-8'))
    P = raw['param']; srv = (P.get('koboServeur') or 'https://kf.kobotoolbox.org').rstrip('/'); uid = P.get('koboUid')
    changed = False; msg = []
    try:
        last = int(P.get('koboLastId') or 0); mx = last; fiches = []
        url = '%s/api/v2/assets/%s/data/?format=json&limit=300&sort=%s&query=%s' % (srv, uid, urllib.parse.quote('{"_id":1}'), urllib.parse.quote(json.dumps({'_id': {'$gt': last}})))
        for _ in range(200):
            js = http('GET', url, tok)
            for s in js.get('results', []):
                fiches.append(parse(s)); mx = max(mx, int(find(s, '_id') or 0))
            url = js.get('next')
            if not url: break
        if fiches:
            n, resume, notes = integrate(raw, fiches); P['koboLastId'] = mx; changed = True
            raw.setdefault('journal', []).insert(0, {'t': stamp(), 'type': 'Synchro Kobo', 'resume': 'Synchro Kobo (cloud) : ' + resume})
            msg.append(resume)
        else: msg.append('à jour (aucune nouvelle fiche)')
        if P.get('publierListes'):
            n = publish_lists(raw, srv, uid, tok); P['publierListes'] = False; changed = True
            raw.setdefault('journal', []).insert(0, {'t': stamp(), 'type': 'Kobo', 'resume': 'Listes publiées sur Kobo (%d vaches en lactation) et formulaire redéployé' % n})
            msg.append('listes publiées (%d vaches en lactation)' % n)
        P['syncCloud'] = stamp() + ' · ' + ' · '.join(msg); P['syncCloudOk'] = True
    except Exception as e:
        P['syncCloud'] = stamp() + ' · ÉCHEC : ' + str(e)[:200]; P['syncCloudOk'] = False; changed = True
        print('ERREUR', e)
    if changed:
        raw['rev'] = int(time.time() * 1000)
        json.dump(raw, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(P['syncCloud'])
    sys.exit(0 if changed else 3)

if __name__ == '__main__':
    main()
