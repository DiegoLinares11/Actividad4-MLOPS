"""Servicio ENTRENADOR.

Corre una sola vez: calibra el pipeline de la Actividad 3 y deja el modelo
entrenado en un volumen compartido para que el servicio de API lo use.

Es el ejemplo mas claro de por que existen los volumenes: el contenedor del
entrenador termina y desaparece, pero el modelo que produjo **sobrevive**
porque no vive dentro del contenedor sino en un volumen de Docker.

Variables de entorno:
    RUTA_CSV          CSV de partidos (por defecto /datos/champions_league_matches.csv)
    DIR_MODELOS       Carpeta donde guardar el modelo (por defecto /modelos)
    N_ITER            Combinaciones a muestrear en la busqueda (por defecto 60)
    FORZAR_REENTRENO  '1' para reentrenar aunque ya exista un modelo
"""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
import socket
import time
from pathlib import Path

import joblib
import pandas as pd
import sklearn

from act3_pipeline import (
    SCORING,
    baseline,
    busqueda_aleatoria,
    evaluar_en_prueba,
    filtrar_datos,
    separar_datos,
)

RUTA_CSV = Path(os.getenv("RUTA_CSV", "/datos/champions_league_matches.csv"))
DIR_MODELOS = Path(os.getenv("DIR_MODELOS", "/modelos"))
N_ITER = int(os.getenv("N_ITER", "60"))
FORZAR = os.getenv("FORZAR_REENTRENO", "0") == "1"

RUTA_MODELO = DIR_MODELOS / "modelo.joblib"
RUTA_METADATOS = DIR_MODELOS / "metadatos.json"


def log(msg: str) -> None:
    print(f"[entrenador] {msg}", flush=True)


def main() -> int:
    log(f"contenedor {socket.gethostname()} | python {platform.python_version()} "
        f"| sklearn {sklearn.__version__}")
    DIR_MODELOS.mkdir(parents=True, exist_ok=True)

    # --- El modelo persiste entre ejecuciones gracias al volumen ---
    if RUTA_MODELO.exists() and not FORZAR:
        log(f"ya existe {RUTA_MODELO} (viene del volumen de una corrida anterior)")
        log("no se reentrena. Para forzarlo: FORZAR_REENTRENO=1")
        return 0

    if not RUTA_CSV.exists():
        log(f"ERROR: no encuentro el CSV en {RUTA_CSV}")
        return 1

    # --- Datos: llegan por un bind mount, no estan dentro de la imagen ---
    df = pd.read_csv(RUTA_CSV)
    log(f"CSV leido desde el bind mount: {df.shape[0]} filas x {df.shape[1]} columnas")
    df = filtrar_datos(df)
    X_train, X_test, y_train, y_test = separar_datos(df)
    log(f"{len(df)} partidos | train={len(X_train)} test={len(X_test)}")

    # --- Calibracion de hiperparametros (lo de la Actividad 3) ---
    log(f"calibrando con RandomizedSearchCV, {N_ITER} combinaciones, metrica {SCORING}...")
    inicio = time.perf_counter()
    busqueda = busqueda_aleatoria(n_iter=N_ITER)
    busqueda.fit(X_train, y_train)
    segundos = time.perf_counter() - inicio

    modelo = busqueda.best_estimator_
    metricas = evaluar_en_prueba(modelo, X_test, y_test)
    dummy = baseline(X_train, y_train, X_test, y_test)

    log(f"listo en {segundos:.1f} s | mejor {SCORING} en CV = {busqueda.best_score_:.3f}")
    log(f"modelo final: {type(modelo.named_steps['modelo']).__name__}")
    log(f"test -> accuracy={metricas['accuracy']:.3f} f1_macro={metricas['f1_macro']:.3f} "
        f"(baseline {dummy['accuracy']:.3f} / {dummy['f1_macro']:.3f})")

    # --- Guardar en el volumen ---
    joblib.dump(modelo, RUTA_MODELO)
    metadatos = {
        "entrenado_en": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "contenedor": socket.gethostname(),
        "modelo": type(modelo.named_steps["modelo"]).__name__,
        "metrica_optimizada": SCORING,
        "cv_mejor_score": round(float(busqueda.best_score_), 4),
        "test_accuracy": round(metricas["accuracy"], 4),
        "test_f1_macro": round(metricas["f1_macro"], 4),
        "baseline_accuracy": round(dummy["accuracy"], 4),
        "baseline_f1_macro": round(dummy["f1_macro"], 4),
        "segundos_entrenamiento": round(segundos, 1),
        "combinaciones_evaluadas": len(busqueda.cv_results_["params"]),
        "mejores_hiperparametros": {k: str(v) for k, v in busqueda.best_params_.items()},
        "versiones": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
        },
        "clases": sorted(modelo.classes_.tolist()),
    }
    RUTA_METADATOS.write_text(json.dumps(metadatos, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"modelo guardado en {RUTA_MODELO} ({RUTA_MODELO.stat().st_size/1024:.0f} KB)")
    log("el contenedor termina aqui, pero el modelo queda en el volumen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
