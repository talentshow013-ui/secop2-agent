import os, io, sys, json
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv(".env")
from sodapy import Socrata
c = Socrata("www.datos.gov.co", os.getenv("SOCRATA_APP_TOKEN"), timeout=120)
NIT="901742864"
# 1. ofertas presentadas
of = c.get("hgi6-6wh3", where=f"nit_proveedor='{NIT}'", limit=1000)
ids = sorted({x["id_procedimiento"] for x in of})
riv = c.get("hgi6-6wh3", where="id_procedimiento in (" + ",".join(f"'{i}'" for i in ids) + ")", limit=10000) if ids else []
byid = defaultdict(set)
for r in riv: byid[r["id_procedimiento"]].add((r["proveedor"].strip(), r["nit_proveedor"]))
print("=== OFERTAS PRESENTADAS por Servicios Planificados ===")
for x in sorted(of, key=lambda x: x["fecha_publicaci_n"], reverse=True):
    others = [a for a,b in byid[x["id_procedimiento"]] if b != NIT]
    print(f"{x['fecha_publicaci_n'][:10]} | {x['entidad_compradora'][:32]} | {x['nombre_procedimiento'][:70]} | rivales: {others or 'NINGUNO'}")
# 2. procesos (precio base, estado, adjudicación)
pr = c.get("p6dx-8zbt", where=f"nit_del_proveedor_adjudicado='{NIT}' OR upper(nombre_del_proveedor) like '%SERVICIOS PLANIFICADOS%'", limit=1000)
print("\n=== PROCESOS donde figura como adjudicatario (p6dx) ===", len(pr))
for x in sorted(pr, key=lambda x: x.get("fecha_de_publicacion_del",""), reverse=True):
    print(f"{x.get('fecha_de_publicacion_del','')[:10]} | {x['entidad'][:32]} | {x.get('modalidad_de_contratacion')} | estado {x.get('estado_del_procedimiento')} | base ${float(x.get('precio_base',0))/1e6:,.0f}M | adj ${float(x.get('valor_total_adjudicacion',0) or 0)/1e6:,.0f}M | {x.get('duracion')} {x.get('unidad_de_duracion')} | {x.get('nombre_del_procedimiento','')[:70]}")
# 3. precio base de los procesos donde ofertó (por entidad + nombre)
print("\n=== PRECIO BASE de los procesos socio estratégico (p6dx, por entidad) ===")
ents = sorted({x["nit_entidad"] for x in of})
pb = c.get("p6dx-8zbt", where="nit_entidad in (" + ",".join(f"'{e}'" for e in ents) + ") AND fecha_de_publicacion_del >= '2024-06-01T00:00:00' AND (upper(nombre_del_procedimiento) like '%SOCIO%' OR upper(nombre_del_procedimiento) like '%CONCESI%' OR upper(nombre_del_procedimiento) like '%ALUMBRADO%')", limit=1000)
for x in sorted(pb, key=lambda x: x.get("fecha_de_publicacion_del",""), reverse=True):
    print(f"{x.get('fecha_de_publicacion_del','')[:10]} | {x['entidad'][:32]} | {x.get('modalidad_de_contratacion')[:20]} | {x.get('estado_del_procedimiento')} / {x.get('fase','')[:30]} | base ${float(x.get('precio_base',0))/1e6:,.0f}M | {x.get('duracion')} {x.get('unidad_de_duracion')} | ganador: {x.get('nombre_del_proveedor','')[:30]} | {x.get('nombre_del_procedimiento','')[:60]}")
# 4. contratos firmados
ct = c.get("jbjy-vk9h", where=f"documento_proveedor='{NIT}'", select="nombre_entidad,departamento,objeto_del_contrato,tipo_de_contrato,modalidad_de_contratacion,estado_contrato,valor_del_contrato,fecha_de_firma,fecha_de_inicio_del_contrato,fecha_de_fin_del_contrato,proveedor_adjudicado,nombre_representante_legal,tipo_de_identificaci_n_representante_legal,identificaci_n_representante_legal", order="fecha_de_firma DESC", limit=200)
print("\n=== CONTRATOS FIRMADOS (jbjy) ===", len(ct))
for x in ct:
    print(f"{x.get('fecha_de_firma','')[:10]} | {x.get('nombre_entidad','')[:32]} ({x.get('departamento','')}) | {x.get('tipo_de_contrato')} | {x.get('modalidad_de_contratacion','')[:22]} | ${float(x.get('valor_del_contrato',0))/1e6:,.0f}M | {x.get('estado_contrato')} | fin {x.get('fecha_de_fin_del_contrato','')[:10]} | {x.get('objeto_del_contrato','')[:90]}")
if ct: print("Razón social:", ct[0].get("proveedor_adjudicado"), "| Rep. legal:", ct[0].get("nombre_representante_legal"))
json.dump({"of":of,"riv":riv,"pr":pr,"pb":pb,"ct":ct}, open(sys.argv[1],"w",encoding="utf-8"), ensure_ascii=False)
