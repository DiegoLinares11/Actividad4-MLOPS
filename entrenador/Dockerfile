# syntax=docker/dockerfile:1

# Imagen base oficial y "slim" (Debian minimo). Se fija la version exacta:
# 'python:3.12' cambiaria de contenido con el tiempo y la imagen dejaria de
# ser reproducible.
FROM python:3.12-slim

# Sin .pyc y con salida sin buffer, para que los logs salgan en vivo en
# `docker compose logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias se copian e instalan ANTES que el codigo. Docker cachea
# cada instruccion en una capa: si solo cambia entrenar.py, esta capa (que es
# la lenta) se reutiliza y el build tarda segundos en vez de minutos.
COPY entrenador/requirements.txt ./requirements.txt
COPY libreria/act3_pipeline-0.1.0-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir -r requirements.txt /tmp/act3_pipeline-0.1.0-py3-none-any.whl \
    && rm /tmp/act3_pipeline-0.1.0-py3-none-any.whl

# Ahora si, el codigo (lo que mas cambia va al final).
COPY entrenador/entrenar.py ./

# Usuario sin privilegios: si alguien se mete al contenedor, no es root.
RUN useradd --create-home --uid 1000 mlops && chown -R mlops:mlops /app
USER mlops

CMD ["python", "entrenar.py"]
