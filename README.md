# Actividad 4 · Docker, Docker Compose y microservicios

Curso **Machine Learning Engineering (MLE/MLOps)** — Universidad del Valle de Guatemala.

Diego Linares · Andy Fuentes · Diederich Solis · Christian Echeverria

El pipeline de scikit-learn que calibramos en la [Actividad 3](https://github.com/DiegoLinares11/Actividad3-MLOPS)
ahora corre repartido en tres contenedores que se levantan con un solo comando.

> **La investigación completa está en [`Investigacion_Docker.pdf`](Investigacion_Docker.pdf)**
> (fuente en `Investigacion_Docker.tex`): Docker vs máquinas virtuales, imágenes y capas, Docker
> Compose, la arquitectura de microservicios y las formas de persistir datos.

---

## Cómo levantarlo

```bash
cp .env.example .env        # y cambiá POSTGRES_PASSWORD
docker compose up --build   # la primera vez construye las imágenes y entrena
```

Documentación interactiva de la API: <http://localhost:8000/docs>

## Los tres servicios

```
   ./datos (CSV) ──►  entrenador  ──escribe──►  ╔ volumen: modelos ╗
   bind mount, ro     corre y muere             ╚════════╤═════════╝
                                                         │ lee (ro)
   puerto 8000  ────►  api (FastAPI)  ──guarda──►  db (Postgres)
   único expuesto      siempre encendida           ╚ volumen: pgdata ╝
```

| Servicio | Tipo | Qué hace | Ciclo de vida |
|---|---|---|---|
| `entrenador` | Trabajo por lotes | Lee el CSV, calibra con `RandomizedSearchCV`, guarda `modelo.joblib` | Corre y **muere** |
| `api` | Servicio | Carga el modelo del volumen y responde predicciones por HTTP | Siempre encendido |
| `db` | Estado | Guarda el historial de predicciones | Siempre encendido |

## Endpoints

| Método | Endpoint | Qué hace |
|---|---|---|
| `GET` | `/salud` | Estado del servicio, del modelo y de la base |
| `GET` | `/modelo` | Métricas, hiperparámetros elegidos, versiones y fecha de entrenamiento |
| `POST` | `/predecir` | Predice el resultado de un partido y lo guarda |
| `GET` | `/predicciones?limite=10` | Historial guardado en Postgres |

Ejemplo (Real Madrid 2–1 Marseille, del dataset):

```bash
curl -X POST http://localhost:8000/predecir -H "Content-Type: application/json" -d "{\"home_team\":\"Real Madrid\",\"away_team\":\"Marseille\",\"home_possession\":\"43%\",\"away_possession\":\"57%\",\"home_shots_on_target\":\"15 of 28\",\"away_shots_on_target\":\"5 of 15\",\"home_saves\":\"4 of 5\",\"away_saves\":\"13 of 15\",\"home_shots_on_target_pct\":53.6,\"away_shots_on_target_pct\":33.3,\"home_saves_pct\":80.0,\"away_saves_pct\":86.7}"
```

> La posesión va como texto (`"43%"`) y los tiros como `"15 of 28"` porque así vienen en el CSV
> original: esa conversión es parte del pipeline, no un paso previo.

## Persistencia: las tres pruebas

```bash
# 1) El modelo sobrevive a su creador
docker compose ps -a                        # act4-entrenador: exited
curl http://localhost:8000/modelo           # ...y el modelo sigue disponible

# 2) La base sobrevive a un apagado completo
docker compose down && docker compose up -d
curl http://localhost:8000/predicciones     # el historial sigue ahí

# 3) Sin volúmenes no queda nada
docker compose down -v                      # -v borra los volúmenes
docker compose up --build                   # entrena de cero, historial en 0
```

## Estructura

```
.
├── Investigacion_Docker.tex / .pdf   # la investigación (entregable)
├── docker-compose.yml                # servicios, red y volúmenes
├── .env.example                      # variables (copiar a .env)
├── datos/champions_league_matches.csv        # bind mount de solo lectura
├── libreria/act3_pipeline-0.1.0-py3-none-any.whl   # paquete de la Actividad 3
├── entrenador/   Dockerfile · requirements.txt · entrenar.py
├── api/          Dockerfile · requirements.txt · main.py
└── db/init.sql                       # tabla de predicciones
```

## Detalle que no es obvio

Las **dos** imágenes instalan el wheel de la Actividad 3 y fijan **las mismas versiones exactas**
de scikit-learn, pandas, numpy y scipy. No es redundancia: un modelo serializado con `joblib`
guarda la *ruta de importación* de sus clases, no su código. Como el pipeline contiene los
transformadores propios `PorcentajeATexto` y `RatioATexto`, la API necesita poder importarlos del
mismo módulo para reconstruirlo.

## Pendiente

- [ ] Capturas de evidencia en `capturas/` (ver sección 7 del PDF)
- [ ] Ejecutar en una segunda computadora para comprobar que da lo mismo
