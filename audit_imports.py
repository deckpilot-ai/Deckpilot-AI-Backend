import pkgutil
import importlib
import sys

errors = []
for importer, modname, ispkg in pkgutil.walk_packages(path=["app"], prefix="app."):
    try:
        importlib.import_module(modname)
    except Exception as e:
        errors.append(f"{modname}: {e}")

if errors:
    print(f"FOUND {len(errors)} IMPORT ERRORS:")
    for err in errors:
        print("  -", err)
    sys.exit(1)
else:
    print("ALL app.* MODULES IMPORTED WITH ZERO ERRORS!")
