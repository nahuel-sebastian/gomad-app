import pandas as pd

from common import RAW, ine_code, latest_csv, municipalities, normalize_name, read_csv, write
from normalize import normalizer


@normalizer("population")
def run():
    df = read_csv(latest_csv(RAW / "padron", ["Año", "Tipo territorio", "Código territorio", "Sexo", "Valor"]))
    # padron mezcla municipios, zonas estadisticas y total regional (informe-datos §2.12)
    df = df[df["Tipo territorio"] == "Municipios"]
    df = df[df["Sexo"] == "Total"]
    # "-" = sin dato (Tres Cantos antes de su segregacion en 1991)
    df = df[df["Valor"].str.strip() != "-"]
    # "Código territorio" = codigo INE de 3 digitos + digito de control ("0014" -> 28001); el nombre solo de respaldo
    by_name = dict(zip(municipalities()["name_norm"], municipalities()["ine_code"]))
    df["ine_code"] = [ine_code(c[:3]) if len(c) == 4 else by_name.get(normalize_name(t))
                      for c, t in zip(df["Código territorio"].str.strip(), df["Territorio"])]
    unmatched = df["ine_code"].isna().sum()
    if unmatched:
        print(f"   population: {unmatched} filas sin casar por nombre:",
              sorted(df.loc[df.ine_code.isna(), "Territorio"].unique())[:10])
    out = pd.DataFrame({"ine_code": df["ine_code"], "year": df["Año"].astype(int),
                        "population": df["Valor"].map(lambda v: int(float(str(v).replace(".", "").replace(",", "."))))})
    out = out.dropna(subset=["ine_code"])
    return write(out, "population")
