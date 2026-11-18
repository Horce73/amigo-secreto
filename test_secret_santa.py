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
        clues = {email: [["Hobby", f"hobby de {name}"]] for name, email in participants}
        codes, data = create_codes(assignments, clues)

        for giver, code in codes.items():
            entry = data["entries"][normalize_code(code)[:4]]
            name, email = assignments[giver]
            self.assertEqual(
                decrypt_payload(code, entry), {"name": name, "clues": clues[email]}
            )

        first, second = list(codes.values())[:2]
        with self.assertRaises(Exception):
            decrypt_payload(first, data["entries"][normalize_code(second)[:4]])

    def test_load_clues_uses_extra_columns_and_skips_empty_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            path.write_text(
                "name,email,Hobby,Comida\nAna,ANA@example.com,Dibujar,\nBruno,b@example.com,,Pizza\n",
                encoding="utf-8",
            )
            self.assertEqual(
                load_clues(path),
                {"ana@example.com": [["Hobby", "Dibujar"]], "b@example.com": [["Comida", "Pizza"]]},
            )
            self.assertEqual(len(load_participants(path)), 2)

    def test_normalize_code_ignores_case_and_dashes(self):
        self.assertEqual(normalize_code("ab2c-defgh-jkmnp"), "AB2CDEFGHJKMNP")


if __name__ == "__main__":
    unittest.main()
