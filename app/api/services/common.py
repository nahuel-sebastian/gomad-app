"""Piezas compartidas por los servicios de la API."""
import schemas as s


def walking_speed_kmh(profile, weights_cfg):
    # velocidad a pie del perfil (weights.yaml -> speeds_kmh); general y sensible caminan a la de «walk»
    speeds = weights_cfg["speeds_kmh"]
    return speeds.get(profile, speeds["walk"])


def data_source(source, labels, date, own_criterion=False):
    return s.DataSource(source=source, label=labels.get(source, source), date=date, own_criterion=own_criterion)
