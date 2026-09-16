import json, sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv(".env")
from sodapy import Socrata
c = Socrata("www.datos.gov.co", os.getenv("SOCRATA_APP_TOKEN"), timeout=120)
rows = json.load(open(sys.argv[1], encoding="utf-8"))
HOY="2026-09-15"
def txt(r): return (r.get("nombre_del_procedimiento","")+" "+r.get("descripci_n_del_procedimiento","")).upper()
def es_conc(r):
    t=txt(r); return ("CONCESI" in t or "SOCIO ESTRAT" in t or ("ECONOM" in t and "MIXTA" in t)) and "INTERVENTOR" not in t
sel = [r for r in rows if (r.get("estado_del_procedimiento") in ("Publicado","Abierto") and (r.get("fecha_de_recepcion_de") or "")[:10]>=HOY and es_conc(r)) or (r.get("estado_del_procedimiento")=="Evaluación" and es_conc(r))]
nits = sorted({r["nit_entidad"] for r in sel})
print("nits:", nits)
q = ",".join(f"'{n}'" for n in nits)
prop = c.get("hgi6-6wh3", where=f"nit_entidad in ({q}) AND fecha_publicaci_n >= '2025-01-01T00:00:00'", limit=20000)
print("registros hgi6 por NIT entidad:", len(prop))
json.dump(prop, open(sys.argv[2],"w",encoding="utf-8"), ensure_ascii=False)
by_ent = {}
for p in prop:
    if "ALUMBRADO" in (p.get("nombre_procedimiento","")).upper() or "CONCESI" in p.get("nombre_procedimiento","").upper() or "SOCIO" in p.get("nombre_procedimiento","").upper():
        by_ent.setdefault((p["nit_entidad"], p["id_procedimiento"], p["nombre_procedimiento"][:100], p["fecha_publicaci_n"][:10]), set()).add((p["proveedor"].strip(), p["nit_proveedor"]))
for k in sorted(by_ent, key=lambda k: k[3], reverse=True):
    ent = next((r["entidad"] for r in sel if r["nit_entidad"]==k[0]), k[0])
    print(f"\n{ent} | {k[1]} | {k[3]} | {k[2]}")
    for n,nit in sorted(by_ent[k]): print(f"   - {n} (NIT {nit})")
