# Sorteo de Amigo Secreto

Herramienta en Python para sorteos de Amigo Secreto con revelación confidencial en el navegador (GitHub Pages en `docs/`).

Cada participante recibe un código único (ejemplo: `6V43-CX8PY-38RP7`). Con ese código, la página descifra en el propio navegador (**AES-256 GCM** con clave derivada mediante **PBKDF2 SHA-256**) a quién le tocó regalar. Ni el repositorio público ni quien organiza el sorteo pueden ver los emparejamientos en `docs/data.json`.

---

## Instalación rápida

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Preparación de participantes

1. Crea o edita `participants.csv` (puedes tomar como base `participants.example.csv`).
2. Requiere dos columnas obligatorias (`name` y `email`) y admite columnas opcionales de características o pistas (por ejemplo `caracteristicas`, separando múltiples ítems con `|`).
3. Para mostrar una imagen junto a una característica, agrega `[img: ruta_o_url]` dentro del ítem (por ejemplo guardando tus imágenes en `docs/img/` y usando `img/foto.jpg`) o usa una columna `imagen`.

```csv
name,email,caracteristicas
Ana,ana@example.com,Siempre llega tarde | Fan del café [img: img/cafe.jpg]
Bruno,bruno@example.com,Videojuegos | Nunca responde mensajes
Carla,carla@example.com,Adicta a los tacos
```

> **Nota:** `participants.csv` está en `.gitignore` para no exponer los nombres ni correos reales en el repositorio.

---

## Validar participantes sin sortear

```bash
.venv/bin/python secret_santa.py participants.csv --dry-run
```

Para ver una simulación en pantalla de quién le regalaría a quién (sin guardar archivos ni enviar correos):

```bash
.venv/bin/python secret_santa.py participants.csv --dry-run --show-matches
```

---

## Generar el sorteo localmente (sin enviar correos)

Si deseas generar los códigos y probar todo antes de subirlo a GitHub (o repartir los enlaces tú mismo por mensaje directo):

```bash
.venv/bin/python secret_santa.py participants.csv --generate
```

Si además deseas ver en consola la tabla de emparejamientos para verificar los resultados:

```bash
.venv/bin/python secret_santa.py participants.csv --generate --show-matches
```

Esto hace lo siguiente:
1. Realiza el sorteo aleatorio asegurando que nadie se regale a sí mismo.
2. Cifra los resultados y actualiza automáticamente `docs/data.json`.
3. Muestra en la terminal la lista de códigos y enlaces listos para probar.
4. Guarda un reporte confidencial en `codigos_sorteo.txt` (ignorado por Git) para que puedas consultar los códigos o enlaces de cada participante cuando lo necesites.

---

## Probar la página localmente

Puedes levantar el servidor local directamente con el script:

```bash
.venv/bin/python secret_santa.py --serve
```

O en un puerto específico:

```bash
.venv/bin/python secret_santa.py --serve --port 8080
```

Abre tu navegador en `http://localhost:8000/` o haz clic directamente en cualquiera de los enlaces generados:
`http://localhost:8000/#XXXX-XXXXX-XXXXX`

La página detecta automáticamente el código en la URL, lo descifra al instante y revela el amigo secreto de forma limpia y directa.

---

## Envío automático por Gmail (Opcional)

Si prefieres que los códigos se envíen automáticamente por correo:

1. Activa la verificación en dos pasos en tu cuenta de Google y genera una [Contraseña de aplicación](https://myaccount.google.com/apppasswords).
2. Exporta tus credenciales en la terminal:

```bash
export GMAIL_USER="tu-correo@gmail.com"
export GMAIL_APP_PASSWORD="tu-clave-de-aplicacion"
```

3. (Opcional) Prueba enviando solo a tu propio correo:

```bash
.venv/bin/python secret_santa.py participants.csv --send --only tu-correo@gmail.com
```

4. Para enviar a todos los participantes:

```bash
.venv/bin/python secret_santa.py participants.csv --send
```

---

## Publicar en GitHub Pages

1. Sube los cambios al repositorio:
   ```bash
   git add docs/
   git commit -m "feat: generar sorteo y actualizar interfaz moderna"
   git push origin main
   ```
2. En GitHub: ve a **Settings** → **Pages** → **Source**: *Deploy from a branch* → Rama `main` → Carpeta `/docs`.
3. ¡Listo! Los participantes podrán ingresar a tu enlace de GitHub Pages para revelar a su amigo secreto.
