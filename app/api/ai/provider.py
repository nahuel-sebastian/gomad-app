"""Proveedor de IA de F6 (DEC-03): OCI Language + diccionario para interpretar y plantillas para redactar.

Implementa ai.base.AIProvider. Nunca decide rutas ni comprueba condiciones: eso lo hace el motor."""
import logging
import time

from ai.dictionary import interpret_text
from ai.oci_language import from_env
from ai.recorded import recorded

log = logging.getLogger("gomad.api")


def _lower_first(text):
    return text[:1].lower() + text[1:]


def _join(items, last):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + last + items[-1]


class RulesProvider:
    def __init__(self, cfg, language=None, clock=time.monotonic):
        self.cfg = cfg
        self.language = language
        self.clock = clock
        self.paused_until = 0.0    # tras un fallo de OCI no se le vuelve a llamar hasta aqui (oci.cooldown_s)

    def _analysis(self, text):
        if self.language is not None and self.clock() >= self.paused_until:
            try:
                return self.language.analyze(text)
            except Exception as e:     # caida, tiempo agotado o permisos: se sigue sin OCI (sin el texto en el log)
                self.paused_until = self.clock() + self.cfg["oci"]["cooldown_s"]
                log.warning("asistente: OCI Language fallo (%s); diccionario durante %s s",
                            type(e).__name__, self.cfg["oci"]["cooldown_s"])
        return recorded(text)

    def interpret(self, text):
        return interpret_text(text, self._analysis(text), self.cfg)

    def write_up(self, conditions, route_summary):
        t = self.cfg["templates"]
        out = t["summary"].format(summary=route_summary)
        if conditions:
            met = sum(c.met for c in conditions)
            out += t["score"].format(met=met, total=len(conditions))
            failed = [_lower_first(c.condition) for c in conditions if not c.met]
            if failed:
                out += t["failed"].format(failed=_join(failed, t["join_last"]))
        return out


def build_provider(cfg, env):
    return RulesProvider(cfg, from_env(env, cfg))
