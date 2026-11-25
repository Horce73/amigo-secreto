import csv
import random
import tempfile
import unittest
from pathlib import Path

from secret_santa import (
    create_assignments,
    create_codes,
    decrypt_payload,
    load_clues,
    load_participants,
    normalize_code,
    validate_assignments,
)


class SecretSantaTests(unittest.TestCase):
    def test_no_person_is_assigned_to_self(self):
        participants = [(f"Persona {i}", f"persona{i}@example.com") for i in range(20)]
        for seed in range(100):
            assignments = create_assignments(participants, random.Random(seed))
            validate_assignments(participants, assignments)

    def test_reject_duplicate_receivers(self):
        participants = [("A", "a@example.com"), ("B", "b@example.com"), ("C", "c@example.com")]
        # A da a B, B da a B (inválido por autoasignación y duplicado de B)
        invalid_assignments = {
            "a@example.com": ("B", "b@example.com"),
            "b@example.com": ("C", "c@example.com"),
            "c@example.com": ("B", "b@example.com"),  # B recibe dos veces
        }
        with self.assertRaisesRegex(ValueError, "Receptor duplicado"):
            validate_assignments(participants, invalid_assignments)

    def test_reject_duplicate_emails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["name", "email"])
                writer.writerow(["Ana", "ana@example.com"])
                writer.writerow(["Otra Ana", "ANA@example.com"])

            with self.assertRaisesRegex(ValueError, "Correo duplicado"):
                load_participants(path)

    def test_codes_decrypt_only_with_their_own_code(self):
        participants = [(f"Persona {i}", f"persona{i}@example.com") for i in range(5)]
        assignments = create_assignments(participants, random.Random(1))
        codes, data = create_codes(assignments)

        for giver, code in codes.items():
            entry = data["entries"][normalize_code(code)[:4]]
            name, _ = assignments[giver]
            self.assertEqual(
                decrypt_payload(code, entry), {"name": name}
            )

        first, second = list(codes.values())[:2]
        with self.assertRaises(Exception):
            decrypt_payload(first, data["entries"][normalize_code(second)[:4]])

    def test_codes_include_clues_when_provided(self):
        participants = [(f"Persona {i}", f"persona{i}@example.com") for i in range(4)]
        assignments = create_assignments(participants, random.Random(2))
        clues = {email: [f"Alias de {name}", "Otro rasgo"] for name, email in participants}
        codes, data = create_codes(assignments, clues)

        for giver, code in codes.items():
            entry = data["entries"][normalize_code(code)[:4]]
            name, receiver_email = assignments[giver]
            self.assertEqual(
                decrypt_payload(code, entry),
                {"name": name, "clues": clues[receiver_email]},
            )

    def test_load_clues_supports_pipe_lists_and_labeled_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            path.write_text(
                (
                    "name,email,caracteristicas,Hobby\n"
                    "Ana,ANA@example.com,Tipazo | Siempre llega tarde,Dibujar\n"
                    "Bruno,b@example.com,,\n"
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                load_clues(path),
                {
                    "ana@example.com": [
                        "Tipazo",
                        "Siempre llega tarde",
                        "Hobby: Dibujar",
                    ]
                },
            )

    def test_load_clues_supports_inline_images_and_image_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            path.write_text(
                (
                    "name,email,caracteristicas,imagen\n"
                    "Ana,ana@example.com,Paga taxis con iPhone [img: img/taxi.jpg] | [img: img/solo.png],img/extra.webp\n"
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                load_clues(path),
                {
                    "ana@example.com": [
                        {"text": "Paga taxis con iPhone", "image": "img/taxi.jpg"},
                        {"image": "img/solo.png"},
                        {"image": "img/extra.webp"},
                    ]
                },
            )

    def test_csv_allows_extra_columns_without_affecting_participants(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            path.write_text(
                "name,email,Hobby,Comida\nAna,ana@example.com,Dibujar,Pizza\nBruno,b@example.com,Juegos,Sushi\n",
                encoding="utf-8",
            )
            participants = load_participants(path)
            self.assertEqual(len(participants), 2)
            self.assertEqual(participants[0], ("Ana", "ana@example.com"))
            self.assertEqual(participants[1], ("Bruno", "b@example.com"))

    def test_normalize_code_ignores_case_and_dashes(self):
        self.assertEqual(normalize_code("ab2c-defgh-jkmnp"), "AB2CDEFGHJKMNP")


if __name__ == "__main__":
    unittest.main()
