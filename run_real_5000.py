import sys, importlib, pkgutil
from flask import Flask

def _try_module(modname):
    try:
        return importlib.import_module(modname)
    except Exception:
        return None

def find_flask_app():
    candidates = [
        "app", "app.app", "app.api", "app.main", "app.wsgi",
        "wsgi", "main", "api", "application"
    ]

    for modname in candidates:
        m = _try_module(modname)
        if not m:
            continue

        for _, obj in vars(m).items():
            try:
                if isinstance(obj, Flask):
                    return obj
            except Exception:
                pass

        f = getattr(m, "create_app", None)
        if callable(f):
            try:
                a = f()
                if isinstance(a, Flask):
                    return a
            except Exception:
                pass

    pkg = _try_module("app")
    if pkg and hasattr(pkg, "__path__"):
        for _, subname, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            m = _try_module(subname)
            if not m:
                continue
            for _, obj in vars(m).items():
                try:
                    if isinstance(obj, Flask):
                        return obj
                except Exception:
                    pass
            f = getattr(m, "create_app", None)
            if callable(f):
                try:
                    a = f()
                    if isinstance(a, Flask):
                        return a
                except Exception:
                    pass

    raise RuntimeError("No se encontró ninguna instancia Flask (ni create_app()) en el proyecto")

if __name__ == "__main__":
    app = find_flask_app()
    app.run(host="127.0.0.1", port=5000)
