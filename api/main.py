"""Servicio API.

Microservicio que sirve el modelo entrenado. No entrena nada: **lee** el modelo
que el servicio `entrenador` dejo en el volumen compartido y expone endpoints
HTTP para predecir. Cada prediccion se guarda en Postgres, que a su vez
persiste en otro volumen.

Endpoints:
    GET  /salud          estado del servicio, del modelo y de la base
    GET  /modelo         metadatos del modelo entrenado
    POST /predecir       predice el resultado de un partido y lo guarda
    GET  /predicciones   historial guardado en Postgres
"""

from __future__ import annotations

import json
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DIR_MODELOS = Path(os.getenv("DIR_MODELOS", "/modelos"))
RUTA_MODELO = DIR_MODELOS / "modelo.joblib"
RUTA_METADATOS = DIR_MODELOS / "metadatos.json"
URL_BD = os.getenv("URL_BD", "")

estado: dict[str, Any] = {"modelo": None, "metadatos": None}


def cargar_modelo() -> bool:
    """Carga el modelo del volumen. Se reintenta si todavia no existe."""
    if estado["modelo"] is not None:
        return True
    if not RUTA_MODELO.exists():
        return False
    estado["modelo"] = joblib.load(RUTA_MODELO)
    if RUTA_METADATOS.exists():
        estado["metadatos"] = json.loads(RUTA_METADATOS.read_text(encoding="utf-8"))
    print(f"[api] modelo cargado desde {RUTA_MODELO}", flush=True)
    return True


def guardar_prediccion(entrada: dict, prediccion: str, probabilidades: dict | None) -> bool:
    """Inserta la prediccion en Postgres. Si la base no esta, no rompe la API."""
    if not URL_BD:
        return False
    try:
        with psycopg.connect(URL_BD, connect_timeout=5) as con, con.cursor() as cur:
            cur.execute(
                """INSERT INTO predicciones (entrada, prediccion, probabilidades, modelo)
                   VALUES (%s, %s, %s, %s)""",
                (
                    json.dumps(entrada, ensure_ascii=False),
                    prediccion,
                    json.dumps(probabilidades, ensure_ascii=False) if probabilidades else None,
                    (estado["metadatos"] or {}).get("modelo", "desconocido"),
                ),
            )
        return True
    except Exception as exc:  # la API sigue viva aunque la base falle
        print(f"[api] no se pudo guardar en la base: {exc}", flush=True)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    cargar_modelo()
    yield


app = FastAPI(
    title="API de prediccion — Champions League",
    description="Actividad 4 (MLE/MLOps, UVG). Sirve el pipeline calibrado en la Actividad 3.",
    version="1.0.0",
    lifespan=lifespan,
)


class Partido(BaseModel):
    """Las mismas columnas crudas que espera el pipeline de la Actividad 3.

    Ojo con el formato: la posesion va como texto ('63%') y los tiros/atajadas
    como texto ('3 of 10'), porque asi vienen en el CSV original y el pipeline
    los convierte adentro.
    """

    home_team: str = Field(examples=["Real Madrid"])
    away_team: str = Field(examples=["Marseille"])
    home_possession: str = Field(examples=["43%"])
    away_possession: str = Field(examples=["57%"])
    home_shots_on_target: str = Field(examples=["15 of 28"])
    away_shots_on_target: str = Field(examples=["5 of 15"])
    home_saves: str = Field(examples=["4 of 5"])
    away_saves: str = Field(examples=["13 of 15"])
    home_shots_on_target_pct: float | None = Field(default=None, examples=[53.6])
    away_shots_on_target_pct: float | None = Field(default=None, examples=[33.3])
    home_saves_pct: float | None = Field(default=None, examples=[80.0])
    away_saves_pct: float | None = Field(default=None, examples=[86.7])


@app.get("/salud")
def salud() -> dict:
    bd_ok = False
    if URL_BD:
        try:
            with psycopg.connect(URL_BD, connect_timeout=3) as con, con.cursor() as cur:
                cur.execute("SELECT 1")
                bd_ok = True
        except Exception:
            bd_ok = False
    return {
        "estado": "ok",
        "contenedor": socket.gethostname(),
        "modelo_cargado": cargar_modelo(),
        "base_de_datos": bd_ok,
    }


@app.get("/modelo")
def modelo() -> dict:
    if not cargar_modelo():
        raise HTTPException(503, "El modelo todavia no existe. ¿Ya corrio el entrenador?")
    return estado["metadatos"] or {"aviso": "el modelo existe pero sin metadatos"}


@app.post("/predecir")
def predecir(partido: Partido) -> dict:
    if not cargar_modelo():
        raise HTTPException(503, "El modelo todavia no existe. ¿Ya corrio el entrenador?")

    entrada = partido.model_dump()
    X = pd.DataFrame([entrada])
    pipe = estado["modelo"]
    prediccion = str(pipe.predict(X)[0])

    probabilidades = None
    if hasattr(pipe, "predict_proba"):
        probas = pipe.predict_proba(X)[0]
        probabilidades = {str(c): round(float(p), 4) for c, p in zip(pipe.classes_, probas)}

    guardado = guardar_prediccion(entrada, prediccion, probabilidades)
    return {
        "prediccion": prediccion,
        "probabilidades": probabilidades,
        "guardado_en_bd": guardado,
        "atendido_por": socket.gethostname(),
    }


@app.get("/predicciones")
def predicciones(limite: int = 10) -> dict:
    if not URL_BD:
        raise HTTPException(503, "Este servicio no tiene base de datos configurada")
    try:
        with psycopg.connect(URL_BD, connect_timeout=5) as con, con.cursor() as cur:
            cur.execute(
                """SELECT id, creado_en, prediccion, modelo, entrada
                   FROM predicciones ORDER BY id DESC LIMIT %s""",
                (limite,),
            )
            filas = cur.fetchall()
            cur.execute("SELECT count(*) FROM predicciones")
            total = cur.fetchone()[0]
    except Exception as exc:
        raise HTTPException(503, f"No se pudo consultar la base: {exc}")

    return {
        "total_historico": total,
        "predicciones": [
            {
                "id": f[0],
                "creado_en": f[1].isoformat(),
                "prediccion": f[2],
                "modelo": f[3],
                "partido": f"{f[4].get('home_team')} vs {f[4].get('away_team')}",
            }
            for f in filas
        ],
    }
