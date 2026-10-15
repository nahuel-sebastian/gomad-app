import sys
import traceback

from normalize import load_all

registry = load_all()
names = sys.argv[1:] or list(registry)
failures = 0
for name in names:
    try:
        print(f"-> {name}: {registry[name]()}")
    except Exception:  # una fuente rota no para el resto; el parquet anterior se mantiene
        failures += 1
        traceback.print_exc()
sys.exit(1 if failures else 0)
