# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY api/requirements.txt ./requirements.txt
COPY libreria/act3_pipeline-0.1.0-py3-none-any.whl /tmp/
# El paquete de la Actividad 3 tambien se instala aqui, aunque la API no
# entrene nada: el modelo guardado con joblib referencia las clases
# PorcentajeATexto y RatioATexto, y Python necesita poder importarlas desde el
# MISMO modulo para reconstruir el pipeline.
RUN pip install --no-cache-dir -r requirements.txt /tmp/act3_pipeline-0.1.0-py3-none-any.whl \
    && rm /tmp/act3_pipeline-0.1.0-py3-none-any.whl

COPY api/main.py ./

RUN useradd --create-home --uid 1000 mlops && chown -R mlops:mlops /app
USER mlops

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
