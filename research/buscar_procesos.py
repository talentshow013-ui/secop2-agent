import os, sys, json
from collections import Counter
from dotenv import load_dotenv
from sodapy import Socrata
load_dotenv(".env")
c = Socrata("www.datos.gov.co", os.getenv("SOCRATA_APP_TOKEN"), timeout=60)
where = ("(upper(nombre_del_procedimiento) like '%ALUMBRADO%' OR upper(descripci_n_del_procedimiento) like '%ALUMBRADO%') "
         "AND (upper(nombre_del_procedimiento) like '%CONCESI%' OR upper(descripci_n_del_procedimiento) like '%CONCESI%' "
         "OR upper(modalidad_de_contratacion) like '%CONCESI%' OR upper(modalidad_de_contratacion) like '%LICITACI%') "
         "AND fecha_de_publicacion_del >= '2025-01-01T00:00:00'")
rows = c.get("p6dx-8zbt", where=where, order="fecha_de_publicacion_del DESC", limit=5000)
print("total:", len(rows))
print("estados:", Counter(r.get("estado_del_procedimiento") for r in rows).most_common())
print("fases:", Counter(r.get("fase") for r in rows).most_common())
print("modalidades:", Counter(r.get("modalidad_de_contratacion") for r in rows).most_common(10))
json.dump(rows, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
