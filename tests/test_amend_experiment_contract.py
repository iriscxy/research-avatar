import unittest

from tools.amend_experiment_contract import amend, digest


class ExperimentContractAmendmentTests(unittest.TestCase):
    def test_amendment_increments_and_requires_reapproval(self):
        contract = {"schema_version": "1.0", "contract_version": 1,
                    "approval_status": "approved", "generated_at": "2026-08-01"}
        contract["approval_contract_sha256"] = digest(contract)
        revised = amend(
            contract, reason="Change threshold", compatibility="rerun E2",
            changed_fields=["decision_space.D1"], changed_at="2026-08-14",
        )
        self.assertEqual(revised["contract_version"], 2)
        self.assertEqual(revised["approval_status"], "pending")
        self.assertEqual(revised["parent_approval_sha256"], contract["approval_contract_sha256"])
        self.assertNotIn("approval_contract_sha256", revised)

    def test_stale_approval_cannot_be_amended(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            amend({"approval_status": "approved", "approval_contract_sha256": "bad"},
                  reason="x", compatibility="y", changed_fields=["z"],
                  changed_at="2026-08-14")


if __name__ == "__main__":
    unittest.main()
