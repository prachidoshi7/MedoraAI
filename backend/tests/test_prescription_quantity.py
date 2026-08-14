"""Tests for editable prescription-to-cart quantity suggestions."""

import unittest

from services.prescription_quantity import suggest_dispense_quantity


class PrescriptionQuantityTests(unittest.TestCase):
    def test_two_doses_for_one_month_suggests_sixty_units(self):
        quantity, basis = suggest_dispense_quantity({
            "dosage": "2 doses",
            "frequency": "",
            "duration": "1 month",
        })

        self.assertEqual(quantity, 60)
        self.assertIn("2 administration(s)/day", basis)
        self.assertIn("30 day(s)", basis)

    def test_combined_direction_phrase_is_also_supported(self):
        quantity, _basis = suggest_dispense_quantity({
            "dosage": "2 doses for 1 month",
            "frequency": "",
            "duration": "",
        })

        self.assertEqual(quantity, 60)

    def test_tablets_frequency_and_weeks_are_combined(self):
        quantity, _basis = suggest_dispense_quantity({
            "dosage": "2 tablets",
            "frequency": "twice daily",
            "duration": "2 weeks",
        })

        self.assertEqual(quantity, 56)

    def test_every_eight_hours_is_three_daily(self):
        quantity, _basis = suggest_dispense_quantity({
            "dosage": "500 mg",
            "frequency": "every 8 hours",
            "duration": "5 days",
        })

        self.assertEqual(quantity, 15)

    def test_unclear_duration_falls_back_for_pharmacist_review(self):
        quantity, basis = suggest_dispense_quantity({
            "dosage": "10 mg",
            "frequency": "as needed",
            "duration": "until symptoms improve",
        })

        self.assertEqual(quantity, 1)
        self.assertIn("review", basis.lower())


if __name__ == "__main__":
    unittest.main()
