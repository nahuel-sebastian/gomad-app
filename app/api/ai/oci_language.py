"""Adaptador de OCI Language (DEC-03): entidades y frases clave de un texto. A OCI solo va el texto de la persona.

Sin credenciales o con IA_PROVEEDOR distinto de oci_language, from_env devuelve None y el asistente usa solo
el diccionario. Nunca se registran claves ni el texto."""
import logging
import os
import pathlib

from ai.dictionary import Analysis

log = logging.getLogger("gomad.api")
PROVIDER = "oci_language"


class OciLanguage:
    def __init__(self, client, compartment_id, language_code):
        self.client = client
        self.compartment_id = compartment_id
        self.language_code = language_code

    def analyze(self, text):
        from oci.ai_language import models     # importacion tardia: el SDK tarda en cargar

        docs = [models.TextDocument(key="1", text=text, language_code=self.language_code)]
        entities = self.client.batch_detect_language_entities(models.BatchDetectLanguageEntitiesDetails(
            documents=docs, compartment_id=self.compartment_id)).data.documents[0].entities
        phrases = self.client.batch_detect_language_key_phrases(models.BatchDetectLanguageKeyPhrasesDetails(
            documents=docs, compartment_id=self.compartment_id)).data.documents[0].key_phrases
        return Analysis(entities=[(e.text, e.type) for e in entities or []],
                        phrases=[p.text for p in phrases or []])


def from_env(env, cfg):
    """OciLanguage con las variables OCI_* (app/.env) o None si no esta configurado o la config no vale."""
    if env.get("IA_PROVEEDOR") != PROVIDER or not env.get("OCI_COMPARTMENT_ID"):
        return None
    path = pathlib.Path(os.path.expanduser(env.get("OCI_CONFIG_FILE") or "~/.oci/config"))
    if not path.exists():
        log.warning("asistente: sin fichero de configuracion de OCI; solo diccionario")
        return None
    try:
        import oci

        config = oci.config.from_file(str(path))
        if env.get("OCI_REGION"):
            config["region"] = env["OCI_REGION"]
        timeout = cfg["oci"]["timeout_s"]
        client = oci.ai_language.AIServiceLanguageClient(config, timeout=(timeout, timeout),
                                                         retry_strategy=oci.retry.NoneRetryStrategy())
    except Exception as e:          # config rota o clave ausente: el asistente sigue con el diccionario
        log.warning("asistente: OCI Language no disponible (%s); solo diccionario", type(e).__name__)
        return None
    return OciLanguage(client, env["OCI_COMPARTMENT_ID"], cfg["oci"]["language_code"])
