"""Respuestas grabadas de OCI Language para las frases de la demo (DEC-03, R6 del plan de la fila 4).

Si OCI no responde y el texto (normalizado) es uno de estos, se usa el analisis grabado: la demo da lo mismo
con red o sin ella. Grabadas con OCI Language real (eu-madrid-1) el 18/10/2026; solo texto de ejemplo, sin
ubicacion ni datos personales."""
from ai.dictionary import Analysis, normalize

RECORDED_ON = "2026-10-18"

RECORDED = {
    normalize(text): analysis for text, analysis in [
        ("15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado",
         Analysis(entities=[("15 km", "QUANTITY"), ("parque", "LOCATION"), ("bancos", "LOCATION"),
                            ("supermercado", "LOCATION")],
                  phrases=["15 km", "supermercado", "parque", "bancos"])),
        ("Quiero correr 10 km sin tráfico",
         Analysis(entities=[("10 km", "QUANTITY")], phrases=["10 km sin", "tráfico"])),
        ("Un paseo de media hora llano y con bancos",
         Analysis(entities=[("bancos", "LOCATION")], phrases=["media hora llano", "paseo", "bancos"])),
        ("Media hora con mi hija hasta unos columpios y volver, sin tráfico",
         Analysis(entities=[("Media hora", "DATETIME")], phrases=["media hora", "columpios", "hija", "tráfico"])),
        ("45 minutos con mi perro y que pase por fuentes",
         Analysis(entities=[("45 minutos", "DATETIME")], phrases=["45 minutos", "perro"])),
    ]
}


def recorded(text):
    return RECORDED.get(normalize(text))
