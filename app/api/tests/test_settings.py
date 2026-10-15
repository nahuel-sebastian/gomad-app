import settings


def test_load_returns_independent_copies():
    data = settings.load("ica_thresholds")
    data["bands"]["NO2"][0] = 999
    data["source"] = "otro"
    again = settings.load("ica_thresholds")
    assert again["bands"]["NO2"][0] == 40 and again["source"] == "BOE-A-2020-10426"


def test_missing_file_is_none():
    assert settings.load("does_not_exist") is None
