import argparse
import base64
import csv
import hashlib
import html
import json
import os
import random
import secrets
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REVEAL_URL = os.environ.get("REVEAL_URL", "https://horce73.github.io/amigo-secreto/")
DATA_PATH = Path(__file__).parent / "docs" / "data.json"
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
        if reader.fieldnames != ["name", "email"]:
            raise ParticipantError("El CSV debe tener las columnas exactas: name,email")

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

    for giver, (_, receiver) in assignments.items():
        if giver == receiver:
            raise ParticipantError("Una persona fue asignada a sí misma")


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


def encrypt_name(code: str, name: str) -> dict[str, str]:
    salt, iv = os.urandom(16), os.urandom(12)
    ciphertext = AESGCM(_derive_key(code, salt)).encrypt(iv, name.encode(), None)
    return {"salt": _b64(salt), "iv": _b64(iv), "ct": _b64(ciphertext)}


def decrypt_name(code: str, entry: dict[str, str]) -> str:
    key = _derive_key(code, base64.b64decode(entry["salt"]))
    plain = AESGCM(key).decrypt(
        base64.b64decode(entry["iv"]), base64.b64decode(entry["ct"]), None
    )
    return plain.decode()


def create_codes(
    assignments: dict[str, tuple[str, str]],
) -> tuple[dict[str, str], dict]:
    used_ids: set[str] = set()
    codes: dict[str, str] = {}
    entries: dict[str, dict[str, str]] = {}
    for giver_email, (receiver_name, _) in assignments.items():
        code = generate_code(used_ids)
        codes[giver_email] = code
        entries[code[:4]] = encrypt_name(code, receiver_name)
    return codes, {"iterations": PBKDF2_ITERATIONS, "entries": entries}


def build_message(giver_name: str, code: str) -> EmailMessage:
    link = f"{REVEAL_URL}#{code}"
    name = html.escape(giver_name)
    message = EmailMessage()
    message["Subject"] = "🎄 Tu código del amigo secreto"
    message.set_content(
        f"Hola {giver_name},\n\n"
        f"Tu código secreto es: {code}\n\n"
        f"Descubre a tu amigo secreto aquí: {link}\n\n"
        "Guarda este correo: el código es solo tuyo."
    )
    message.add_alternative(
        f"""\
<html><body style="margin:0;padding:0;background:#0b3d2e;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b3d2e;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#fffaf0;border:3px solid #d4a73c;border-radius:16px;font-family:Georgia,'Times New Roman',serif;color:#2b2b2b;">
<tr><td align="center" style="padding:28px 24px 8px;font-size:40px;">🎄🎁🎄</td></tr>
<tr><td align="center" style="padding:0 24px;font-size:28px;font-weight:bold;color:#b3202a;">Amigo Secreto</td></tr>
<tr><td style="padding:20px 32px 0;font-size:17px;line-height:1.6;">
Hola <b>{name}</b>,<br><br>
Ya salió el sorteo y alguien especial espera tu regalo. Para descubrir quién es, usa tu código secreto:
</td></tr>
<tr><td align="center" style="padding:20px 24px;">
<div style="display:inline-block;background:#0b3d2e;color:#f4d27a;font-family:'Courier New',monospace;font-size:24px;letter-spacing:3px;padding:14px 22px;border-radius:10px;">{code}</div>
</td></tr>
<tr><td align="center" style="padding:0 24px 24px;">
<a href="{link}" style="display:inline-block;background:#b3202a;color:#ffffff;text-decoration:none;font-size:18px;font-weight:bold;padding:14px 30px;border-radius:999px;">🎅 Descubrir a mi amigo secreto</a>
</td></tr>
<tr><td align="center" style="padding:0 32px 28px;font-size:13px;color:#777;line-height:1.5;">
Guarda este correo: el código es solo tuyo.<br>Si el botón no abre, copia el código en {html.escape(REVEAL_URL)}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sortear y enviar amigo secreto")
    parser.add_argument("csv", nargs="?", default="participants.csv", type=Path)
    parser.add_argument("--only", metavar="EMAIL", help="Enviar solo a este correo (pruebas)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Solo validar el sorteo")
    mode.add_argument("--send", action="store_true", help="Enviar los códigos por Gmail")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        participants = load_participants(args.csv)
        assignments = create_assignments(participants)
        validate_assignments(participants, assignments)

        if not args.send:
            print(f"Sorteo válido para {len(participants)} participantes.")
            print("No se muestra quién le regala a quién.")
            return 0

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

        codes, data = create_codes(assignments)
        DATA_PATH.parent.mkdir(exist_ok=True)
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
        print("Listo. Publica docs/data.json para que los códigos funcionen.")
        return 0
    except (ParticipantError, smtplib.SMTPException) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
