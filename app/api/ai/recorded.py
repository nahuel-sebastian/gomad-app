"""Respuestas grabadas de OCI Language para las frases de la demo (DEC-03, R6 del plan de la fila 4).

Si OCI no responde y el texto (normalizado) es uno de estos, se usa el analisis grabado: la demo da lo mismo
con red o sin ella. Solo texto de ejemplo, sin ubicacion ni datos personales."""
from ai.dictionary import Analysis, normalize

RECORDED_ON = None   # fecha de la grabacion real (se rellena al grabar)

RECORDED = {
    normalize(text): analysis for text, analysis in [
        ("15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado",
         Analysis(entities=[("15 km", "QUANTITY")], phrases=["parque", "supermercado"])),
    ]
}


def recorded(text):
    return RECORDED.get(normalize(text))
