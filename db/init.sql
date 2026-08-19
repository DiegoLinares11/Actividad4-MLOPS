-- Se ejecuta UNA sola vez: cuando el volumen de Postgres esta vacio.
-- Si el volumen ya tiene datos, Docker ignora este script (y por eso los
-- datos sobreviven a un `docker compose down` sin -v).
CREATE TABLE IF NOT EXISTS predicciones (
    id             SERIAL PRIMARY KEY,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now(),
    entrada        JSONB       NOT NULL,
    prediccion     TEXT        NOT NULL,
    probabilidades JSONB,
    modelo         TEXT
);

CREATE INDEX IF NOT EXISTS idx_predicciones_creado_en ON predicciones (creado_en DESC);
