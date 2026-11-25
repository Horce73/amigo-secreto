import argparse
import base64
import csv
import functools
import hashlib
import html
import http.server
import json
import os
import random
import re
import secrets
import shutil
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REVEAL_URL = os.environ.get("REVEAL_URL", "https://horce73.github.io/amigo-secreto/")
DOCS_DIR = Path(__file__).parent / "docs"
DATA_PATH = DOCS_DIR / "data.json"
PREVIEW_DIR = Path(__file__).parent / "preview"
CODES_OUTPUT_FILE = Path(__file__).parent / "codigos_sorteo.txt"
PBKDF2_ITERATIONS = 600_000
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class ParticipantError(ValueError):
    pass


def load_participants(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        raise ParticipantError(f"No existe el archivo: {path}")

    participants: list[tuple[str, str]] = []
    seen_emails: set[str] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if (reader.fieldnames or [])[:2] != ["name", "email"]:
            raise ParticipantError("El CSV debe empezar con las columnas: name,email")

        for line_number, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip().lower()

            if not name or not email:
                raise ParticipantError(f"Fila {line_number}: name y email son obligatorios")
            if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                raise ParticipantError(f"Fila {line_number}: correo inválido ({email})")
            if email in seen_emails:
                raise ParticipantError(f"Correo duplicado: {email}")

            seen_emails.add(email)
            participants.append((name, email))

    if len(participants) < 2:
        raise ParticipantError("Se necesitan al menos 2 participantes")

    return participants


GENERIC_CLUE_PREFIXES = ("caracteristica", "característica", "pista", "clue")
IMAGE_COLUMN_NAMES = {"imagen", "imágenes", "imagenes", "image", "images", "img", "foto", "fotos"}
IMAGE_TAG_RE = re.compile(r"\[img:\s*([^\]]+?)\s*\]", re.IGNORECASE)


def _is_generic_clue_column(label: str) -> bool:
    """Indica si el nombre de columna es genérico y no debe anteponerse como etiqueta."""
    return label.strip().lower().startswith(GENERIC_CLUE_PREFIXES)


def _parse_clue_part(part: str, label: str | None = None) -> str | dict[str, str]:
    """Convierte una pista de texto o con etiqueta [img: ruta] en string o dict estructurado."""
    match = IMAGE_TAG_RE.search(part)
    if not match:
        return f"{label}: {part}" if label else part

    image_src = match.group(1).strip()
    text = IMAGE_TAG_RE.sub("", part).strip()
    if label and text:
        text = f"{label}: {text}"
    if not image_src:
        return text
    clue: dict[str, str] = {"image": image_src}
    if text:
        clue["text"] = text
    return clue


def load_clues(path: Path) -> dict[str, list[str | dict[str, str]]]:
    """Lee columnas opcionales del CSV (después de name,email) como características e imágenes."""
    clues_by_email: dict[str, list[str | dict[str, str]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        extra_labels = (reader.fieldnames or [])[2:]
        if not extra_labels:
            return clues_by_email

        for row in reader:
            email = (row.get("email") or "").strip().lower()
            if not email:
                continue
            person_clues: list[str | dict[str, str]] = []
            for label in extra_labels:
                raw_value = (row.get(label) or "").strip()
                if not raw_value:
                    continue
                parts = [part.strip() for part in raw_value.split("|") if part.strip()]
                clean_label = label.strip()
                normalized_label = clean_label.lower()

                if normalized_label in IMAGE_COLUMN_NAMES:
                    for part in parts:
                        parsed = _parse_clue_part(part)
                        person_clues.append(parsed if isinstance(parsed, dict) else {"image": part})
                elif _is_generic_clue_column(clean_label):
                    for part in parts:
                        parsed = _parse_clue_part(part)
                        if parsed:
                            person_clues.append(parsed)
                else:
                    for part in parts:
                        parsed = _parse_clue_part(part, label=clean_label)
                        if parsed:
                            person_clues.append(parsed)
            if person_clues:
                clues_by_email[email] = person_clues

    return clues_by_email


def create_assignments(
    participants: list[tuple[str, str]], rng: random.Random | None = None
) -> dict[str, tuple[str, str]]:
    rng = rng or random.SystemRandom()
    emails = [email for _, email in participants]

    for _ in range(1000):
        receivers = emails.copy()
        rng.shuffle(receivers)
        if all(giver != receiver for giver, receiver in zip(emails, receivers)):
            return {
                giver: (next(name for name, email in participants if email == receiver), receiver)
                for giver, receiver in zip(emails, receivers)
            }

    raise ParticipantError("No se pudo generar un sorteo válido")


def validate_assignments(
    participants: list[tuple[str, str]],
    assignments: dict[str, tuple[str, str]],
) -> None:
    giver_emails = {email for _, email in participants}
    if set(assignments) != giver_emails:
        raise ParticipantError("El sorteo no contiene exactamente a todos los participantes")

    receiver_emails: set[str] = set()
    for giver, (_, receiver) in assignments.items():
        if giver == receiver:
            raise ParticipantError("Una persona fue asignada a sí misma")
        if receiver in receiver_emails:
            raise ParticipantError(f"Receptor duplicado en el sorteo: {receiver}")
        receiver_emails.add(receiver)

    if receiver_emails != giver_emails:
        raise ParticipantError("Los receptores no coinciden exactamente con los participantes")


def normalize_code(code: str) -> str:
    return "".join(c for c in code.upper() if c in CODE_ALPHABET)


def generate_code(used_ids: set[str]) -> str:
    def group(size: int) -> str:
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(size))

    while True:
        code = f"{group(4)}-{group(5)}-{group(5)}"
        if code[:4] not in used_ids:
            used_ids.add(code[:4])
            return code


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _derive_key(code: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", normalize_code(code).encode(), salt, PBKDF2_ITERATIONS, 32
    )


def encrypt_payload(code: str, payload: dict) -> dict[str, str]:
    salt, iv = os.urandom(16), os.urandom(12)
    plain = json.dumps(payload, ensure_ascii=False).encode()
    ciphertext = AESGCM(_derive_key(code, salt)).encrypt(iv, plain, None)
    return {"salt": _b64(salt), "iv": _b64(iv), "ct": _b64(ciphertext)}


def decrypt_payload(code: str, entry: dict[str, str]) -> dict:
    key = _derive_key(code, base64.b64decode(entry["salt"]))
    plain = AESGCM(key).decrypt(
        base64.b64decode(entry["iv"]), base64.b64decode(entry["ct"]), None
    )
    return json.loads(plain)


def create_codes(
    assignments: dict[str, tuple[str, str]],
    clues: dict[str, list[str | dict[str, str]]] | None = None,
) -> tuple[dict[str, str], dict]:
    """Genera códigos cifrados que revelan el nombre y características opcionales del amigo secreto."""
    used_ids: set[str] = set()
    codes: dict[str, str] = {}
    entries: dict[str, dict[str, str]] = {}
    for giver_email, (receiver_name, receiver_email) in assignments.items():
        code = generate_code(used_ids)
        codes[giver_email] = code
        payload: dict[str, object] = {"name": receiver_name}
        person_clues = (clues or {}).get(receiver_email, [])
        if person_clues:
            payload["clues"] = person_clues
        entries[code[:4]] = encrypt_payload(code, payload)
    # Orden aleatorio: la posición en el archivo no debe revelar quién es quién.
    shuffled = list(entries.items())
    random.SystemRandom().shuffle(shuffled)
    return codes, {"iterations": PBKDF2_ITERATIONS, "entries": dict(shuffled)}


def build_message(giver_name: str, code: str) -> EmailMessage:
    link = f"{REVEAL_URL}#{code}"
    name = html.escape(giver_name)
    message = EmailMessage()
    message["Subject"] = "Tu código del amigo secreto"
    message.set_content(
        f"Hola {giver_name},\n\n"
        f"Tu código secreto es: {code}\n\n"
        f"Descubre a tu amigo secreto aquí: {link}\n\n"
        "Guarda este correo: el código es solo tuyo."
    )
    message.add_alternative(
        f"""\
<html><body style="margin:0;padding:0;background:#f5efe8;color:#2b221e;font-family:system-ui,-apple-system,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5efe8;padding:32px 12px;">
<tr><td align="center">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border:1.5px solid #d8c8b8;border-radius:18px;color:#2b221e;box-shadow:0 12px 30px rgba(85,60,45,0.08);">
<tr><td align="center" style="padding:32px 24px 8px;font-size:26px;font-weight:bold;color:#78211e;letter-spacing:1px;">Amigo Secreto</td></tr>
<tr><td style="padding:20px 32px 0;font-size:16px;line-height:1.6;color:#5e544d;">
Hola <b>{name}</b>,<br><br>
El sorteo ya se ha realizado. Para descubrir confidencialmente quién es tu amigo secreto, utiliza tu código personal:
</td></tr>
<tr><td align="center" style="padding:24px;">
<div style="display:inline-block;background:#fbf8f5;color:#78211e;border:1.5px solid #bb9771;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:22px;letter-spacing:3px;padding:14px 24px;border-radius:10px;font-weight:bold;">{code}</div>
</td></tr>
<tr><td align="center" style="padding:0 24px 28px;">
<a href="{link}" style="display:inline-block;background:#78211e;color:#ffffff;text-decoration:none;font-size:16px;font-weight:bold;padding:14px 32px;border-radius:999px;">Descubrir a mi amigo secreto</a>
</td></tr>
<tr><td align="center" style="padding:0 32px 28px;font-size:13px;color:#7a6e65;line-height:1.5;">
Guarda este mensaje confidencialmente.<br>También puedes ingresar manualmente el código en <a href="{html.escape(REVEAL_URL)}" style="color:#78211e;text-decoration:none;font-weight:bold;">{html.escape(REVEAL_URL)}</a>
</td></tr>
</table>
</td></tr></table>
</body></html>""",
        subtype="html",
    )
    return message


def send_codes(participants: list[tuple[str, str]], codes: dict[str, str]) -> None:
    username = (os.environ.get("GMAIL_USER") or "").strip()
    password = (os.environ.get("GMAIL_APP_PASSWORD") or "").strip()

    if not username or not password:
        raise ParticipantError(
            "Configura GMAIL_USER y GMAIL_APP_PASSWORD antes de usar --send"
        )

    names_by_email = {email: name for name, email in participants}

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(username, password)

        for email, code in codes.items():
            message = build_message(names_by_email[email], code)
            message["From"] = username
            message["To"] = email
            smtp.send_message(message)
            print(f"Correo enviado a {names_by_email[email]} <{email}>")


def serve_directory(directory: Path, port: int = 8000) -> None:
    """Inicia un servidor HTTP local para probar la interfaz en el navegador."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"\nServidor local activo en: http://localhost:{port}/")
        print("Presiona Ctrl+C para detener el servidor.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


def export_codes_report(
    participants: list[tuple[str, str]],
    codes: dict[str, str],
    port: int = 8000,
) -> str:
    """Genera un reporte legible con los códigos y enlaces de revelación."""
    lines = [
        "=" * 64,
        "SORTEO DE AMIGO SECRETO - CÓDIGOS DE REVELACIÓN",
        "=" * 64,
        "CONFIDENCIAL: No compartas este archivo completo ni lo subas a GitHub.",
        "Entrega a cada participante únicamente su código o enlace personal.",
        "-" * 64,
    ]
    for name, email in participants:
        code = codes[email]
        local_link = f"http://localhost:{port}/#{code}"
        web_link = f"{REVEAL_URL}#{code}"
        lines.append(f"Participante: {name} <{email}>")
        lines.append(f"Código:       {code}")
        lines.append(f"Enlace local: {local_link}")
        lines.append(f"Enlace web:   {web_link}")
        lines.append("-" * 64)

    return "\n".join(lines)


def format_matches_table(
    participants: list[tuple[str, str]],
    assignments: dict[str, tuple[str, str]],
    codes: dict[str, str] | None = None,
    port: int = 8000,
) -> str:
    """Genera una tabla clara de emparejamientos para depuración y pruebas."""
    lines = [
        "=" * 86,
        "EMPAREJAMIENTOS DEL SORTEO (MODO DE PRUEBA Y VERIFICACIÓN)",
        "=" * 86,
    ]
    if codes:
        lines.append(
            f"{'Quién regala':<18} -> {'Le regala a':<18} | {'Código':<17} | {'Enlace Local'}"
        )
        lines.append("-" * 86)
        for name, email in participants:
            receiver_name, _ = assignments[email]
            code = codes[email]
            local_url = f"http://localhost:{port}/#{code}"
            lines.append(
                f"{name:<18} -> {receiver_name:<18} | {code:<17} | {local_url}"
            )
    else:
        lines.append(f"{'Quién regala':<28} -> {'Le regala a'}")
        lines.append("-" * 86)
        for name, email in participants:
            receiver_name, _ = assignments[email]
            lines.append(f"{name:<28} -> {receiver_name}")

    lines.append("-" * 86)
    lines.append(
        f"Verificación: {len(participants)} participantes | 0 auto-asignados | 0 repetidos"
    )
    lines.append("=" * 86)
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sorteo de Amigo Secreto con cifrado en el navegador"
    )
    parser.add_argument("csv", nargs="?", default="participants.csv", type=Path)
    parser.add_argument("--only", metavar="EMAIL", help="Enviar solo a este correo (pruebas)")
    parser.add_argument(
        "--port", type=int, default=8000, help="Puerto para el servidor local (por defecto: 8000)"
    )
    parser.add_argument(
        "--show-matches",
        action="store_true",
        help="Mostrar en consola la tabla de emparejamientos (quién le regala a quién) para pruebas",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--generate",
        action="store_true",
        help="Generar el sorteo, guardar docs/data.json y listar códigos sin enviar correos",
    )
    mode.add_argument(
        "--serve",
        action="store_true",
        help="Iniciar el servidor HTTP local para abrir la interfaz de docs/",
    )
    mode.add_argument("--dry-run", action="store_true", help="Solo validar el archivo CSV")
    mode.add_argument(
        "--preview",
        action="store_true",
        help="Generar sorteo de prueba temporal y mostrar URL de prueba",
    )
    mode.add_argument("--send", action="store_true", help="Enviar los códigos por Gmail")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Si se pide únicamente servir la carpeta docs existente
    if args.serve and not args.generate:
        serve_directory(DOCS_DIR, port=args.port)
        return 0

    try:
        participants = load_participants(args.csv)
        clues = load_clues(args.csv)
        assignments = create_assignments(participants)
        validate_assignments(participants, assignments)

        # Modo validación en seco
        if args.dry_run:
            if args.show_matches:
                print("\n" + format_matches_table(participants, assignments) + "\n")
            else:
                print(f"Sorteo válido para {len(participants)} participantes.")
                if clues:
                    print(f"Características cargadas para {len(clues)} de {len(participants)} participantes.")
                print("No se muestra quién le regala a quién (usa --show-matches para verlo).")
            return 0

        # Modo previsualización temporal
        if args.preview:
            codes, data = create_codes(assignments, clues)
            email = (args.only or participants[0][1]).strip().lower()
            if email not in codes:
                raise ParticipantError(f"{email} no está en el CSV")
            shutil.copytree(DOCS_DIR, PREVIEW_DIR, dirs_exist_ok=True)
            (PREVIEW_DIR / "data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
            print(f"Código de prueba para {email}: {codes[email]}")
            print(f"Enlace local: http://localhost:{args.port}/#{codes[email]}")
            print(f"Iniciando servidor en preview/ (puerto {args.port})...")
            serve_directory(PREVIEW_DIR, port=args.port)
            return 0

        # Modo generación local (sin enviar correos)
        if args.generate:
            codes, data = create_codes(assignments, clues)
            DOCS_DIR.mkdir(parents=True, exist_ok=True)
            DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")

            report = export_codes_report(participants, codes, port=args.port)
            CODES_OUTPUT_FILE.write_text(report, encoding="utf-8")

            if args.show_matches:
                print("\n" + format_matches_table(participants, assignments, codes, port=args.port) + "\n")
            else:
                print("\n" + report + "\n")

            print("Sorteo generado con éxito.")
            if clues:
                print(f"Características incluidas para {len(clues)} de {len(participants)} participantes.")
            print(f"Archivo actualizado: {DATA_PATH.relative_to(Path.cwd())}")
            print(f"Reporte confidencial guardado en: {CODES_OUTPUT_FILE.name} (ignorado por git)")
            print("\nPuedes probar la página localmente con:")
            print(f"  .venv/bin/python secret_santa.py --serve --port {args.port}")
            print("  O directamente abriendo cualquiera de los enlaces locales de arriba.\n")
            return 0

        if not args.send:
            if args.show_matches:
                print("\n" + format_matches_table(participants, assignments) + "\n")
            else:
                print(f"Sorteo válido para {len(participants)} participantes.")
                if clues:
                    print(f"Características cargadas para {len(clues)} de {len(participants)} participantes.")
                print("Para generar los códigos y guardar docs/data.json sin enviar correos, ejecuta:")
                print(f"  .venv/bin/python secret_santa.py {args.csv} --generate")
                print("Añade --show-matches si quieres ver quién le regala a quién en consola.")
            return 0

        # Modo envío por correo (Gmail)
        recipients = participants
        if args.only:
            only = args.only.strip().lower()
            recipients = [p for p in participants if p[1] == only]
            if not recipients:
                raise ParticipantError(f"{only} no está en el CSV")

        print("Se enviarán correos a:")
        for name, email in recipients:
            print(f"  {name} <{email}>")
        answer = input("¿Confirmas el envío? [sí/no]: ").strip().lower()
        if answer not in {"sí", "si", "s"}:
            print("Envío cancelado.")
            return 0

        codes, data = create_codes(assignments, clues)
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")

        try:
            send_codes(participants, {e: codes[e] for _, e in recipients})
        except (OSError, smtplib.SMTPException):
            print(
                "El envío se interrumpió. Si repites el sorteo, los códigos ya enviados "
                "dejan de servir: vuelve a enviar a todos.",
                file=sys.stderr,
            )
            raise
        print("Listo. Publica docs/data.json en git para que los códigos funcionen en GitHub Pages.")
        return 0
    except (ParticipantError, smtplib.SMTPException) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
