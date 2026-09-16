import json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv(".env")
from sodapy import Socrata
c = Socrata("www.datos.gov.co", os.getenv("SOCRATA_APP_TOKEN"), timeout=180)
# 1. todo lo que DOLMEN ha ofertado
d = c.get("hgi6-6wh3", where="nit_proveedor='802012179' OR upper(proveedor) like 'DOLMEN%'", limit=5000)
print("ofertas DOLMEN:", len(d))
ids = sorted({x["id_procedimiento"] for x in d})
# 2. quién más ofertó en esos mismos procesos
q = ",".join(f"'{i}'" for i in ids)
rivals = c.get("hgi6-6wh3", where=f"id_procedimiento in ({q})", limit=20000) if ids else []
# 3. mercado nacional: concesiones / socio estratégico alumbrado 2024+
m = c.get("hgi6-6wh3", where="fecha_publicaci_n >= '2024-01-01T00:00:00' AND upper(nombre_procedimiento) like '%ALUMBRADO%' AND (upper(nombre_procedimiento) like '%CONCESI%' OR upper(nombre_procedimiento) like '%SOCIO ESTRAT%' OR upper(nombre_procedimiento) like '%MIXTA%')", limit=20000)
print("registros mercado:", len(m))
json.dump({"dolmen":d,"rivals":rivals,"mercado":m}, open(sys.argv[1],"w",encoding="utf-8"), ensure_ascii=False)
