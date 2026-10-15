#!/usr/bin/env python3
"""Prueba del proveedor de IA (DEC-03): OCI Language con la frase de ejemplo de F6.

Imprime entidades y frases clave y mide la latencia media de 5 llamadas (objetivo < 2 s).
No envia ubicacion ni datos personales. Credenciales: OCI_* de app/.env y el fichero OCI_CONFIG_FILE.
El paso de entidades a AssistantParams (diccionario del catalogo RF-21) es de D-M1, no de esta prueba.
"""
import os
import pathlib
import statistics
import sys
import time

import oci

ROOT = pathlib.Path(__file__).resolve().parent.parent      # app/api
ENV_FILE = ROOT.parent / ".env"                              # app/.env
TEXT = "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado"
CALLS = 5
TARGET_S = 2.0


def read_env(path=ENV_FILE):
    """Lee app/.env (CLAVE=valor por linea) sin dependencias. Las variables de entorno reales mandan."""
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("OCI_")})
    return values


def client(env):
    config = oci.config.from_file(os.path.expanduser(env.get("OCI_CONFIG_FILE") or "~/.oci/config"))
    if env.get("OCI_REGION"):
        config["region"] = env["OCI_REGION"]
    return oci.ai_language.AIServiceLanguageClient(config)


def analyze(lang, compartment_id):
    docs = [oci.ai_language.models.TextDocument(key="1", text=TEXT, language_code="es")]
    entities = lang.batch_detect_language_entities(
        oci.ai_language.models.BatchDetectLanguageEntitiesDetails(documents=docs, compartment_id=compartment_id)
    ).data.documents[0].entities
    phrases = lang.batch_detect_language_key_phrases(
        oci.ai_language.models.BatchDetectLanguageKeyPhrasesDetails(documents=docs, compartment_id=compartment_id)
    ).data.documents[0].key_phrases
    return entities, phrases


def fmt_score(score):
    # OCI puede devolver score nulo
    return "-" if score is None else f"{score:.2f}"


def main():
    env = read_env()
    compartment_id = env.get("OCI_COMPARTMENT_ID")
    if not compartment_id:
        sys.exit("Falta OCI_COMPARTMENT_ID en app/.env (ver app/.env.example)")
    lang = client(env)
    times = []
    for _ in range(CALLS):
        t0 = time.perf_counter()
        entities, phrases = analyze(lang, compartment_id)
        times.append(time.perf_counter() - t0)
    print(f"Texto: {TEXT}")
    print("Entidades:")
    for e in entities:
        print(f"  {e.text!r:24} {e.type or '-':12} {fmt_score(e.score)}")
    print("Frases clave:")
    for p in phrases:
        print(f"  {p.text!r:24} {fmt_score(p.score)}")
    mean = statistics.mean(times)
    print(f"Latencia (entidades + frases clave) en {CALLS} llamadas: media {mean:.2f} s, max {max(times):.2f} s")
    print("OK" if mean < TARGET_S else f"LENTO: media >= {TARGET_S} s")
    return 0 if mean < TARGET_S else 1


if __name__ == "__main__":
    sys.exit(main())
