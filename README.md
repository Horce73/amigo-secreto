# Sorteo de amigo secreto

Herramienta de consola en Python. Cada participante recibe por correo un código; con él
descubre a su amigo secreto en una página de GitHub Pages (`docs/`). El nombre viaja cifrado
(AES-GCM, clave derivada del código con PBKDF2), así que ni el organizador ni el repo público
revelan los emparejamientos.

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Preparación

1. Copia `participants.example.csv` a `participants.csv`.
2. Reemplaza los datos por los participantes reales.
3. Usa correos únicos por persona.

El CSV debe tener exactamente estas columnas:

```csv
name,email
Ana,ana@example.com
Bruno,bruno@example.com
```

## Prueba segura

Ejecuta:

```bash
python3 secret_santa.py participants.csv --dry-run
```

El modo seguro solo valida el sorteo. No muestra quién le regala a quién y no envía correos.

## Configuración de Gmail

1. Activa la verificación en dos pasos en tu cuenta de Google.
2. Crea una contraseña de aplicación.
3. Exporta tus variables antes de enviar:

```bash
export GMAIL_USER="tu-correo@gmail.com"
export GMAIL_APP_PASSWORD="tu-clave-de-aplicacion"
```

También puedes copiar `.env.example` a `.env`, pero el script no lee ese archivo automáticamente. Exporta sus valores manualmente.

## Envío

Primero prueba con tus propios correos (`--only` envía a uno solo, pero el sorteo incluye a todos):

```bash
python3 secret_santa.py participants.csv --send --only tu-correo@gmail.com
```

Para el envío real, quita `--only`. Cada `--send` hace un sorteo nuevo y reescribe
`docs/data.json`: **publícalo (commit y push) para que los códigos funcionen**. Si repites el
sorteo, los códigos de correos anteriores dejan de servir.

## Página (GitHub Pages)

En el repo: Settings → Pages → Deploy from a branch → `main` → carpeta `/docs`.
El enlace del correo se puede cambiar con la variable `REVEAL_URL`.

El script vuelve a validar duplicados y que nadie resulte asignado a sí mismo antes de enviar.
