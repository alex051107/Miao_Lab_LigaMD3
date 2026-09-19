import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_scripts"))
from classify_paired import classify, read_series, stats


class PairedTests(unittest.TestCase):
    def classify(self, d, r=None, **kwargs):
        return classify(d, r if r is not None else d,
                        **(dict(stage="equil", state="COMPLETED", expected=len(d), captured=len(d),
                                frame_ns=.01, parameters_valid=True) | kwargs))

    def test_equil_clean_is_not_production_or_prefix_seed(self):
        self.assertTrue(self.classify([4.] * 10)["seed_candidate"])
        for kwargs in ({"state": "RUNNING"}, {"stage": "production"}, {"parameters_valid": False}):
            self.assertFalse(self.classify([4.] * 10, **kwargs)["seed_candidate"])

    def test_both_metrics_required(self):
        self.assertEqual(self.classify([20.] * 10)["classification"], "DEPARTURE_CANDIDATE")
        for d, r in (([20.] * 10, [4.] * 10), ([4.] * 10, [20.] * 10)):
            self.assertEqual(self.classify(d, r)["classification"], "DEPARTURE_UNCONFIRMED_ONE_METRIC")

    def test_rmsd_excludes_seed_and_boundary_thresholds(self):
        for value, expected in ((9.99, "CLEAN_BOUND"), (10, "EDGE"), (12.99, "EDGE"), (13, "SEED_EXCLUDED_GE13")):
            self.assertEqual(self.classify([4.] * 10, [value] * 10)["classification"], expected)

    def test_last_frame_does_not_establish_duration(self):
        self.assertEqual(self.classify([4.] * 99 + [20.])["classification"], "INSUFFICIENT_POST_ONSET_COVERAGE")
        self.assertEqual(self.classify([4.] * 90 + [20.] + [4.] * 9)["classification"], "CENSORED_UNDETERMINED")
        # Sustained separation is not censored merely because an onset exists.
        self.assertEqual(self.classify([4.] * 50 + [20.] * 50)["classification"], "DEPARTURE_CANDIDATE")

    def test_failed_and_incomplete_are_never_evidence(self):
        for state in ("FAILED", "TIMEOUT", "CANCELLED", "NODE_FAIL", "OUT_OF_MEMORY", "PREEMPTED", "BOOT_FAIL"):
            self.assertEqual(self.classify([20.] * 10, state=state)["classification"], "FAILED_OR_STOPPED_PARTIAL_NOT_EVIDENCE")
        self.assertEqual(self.classify([4.] * 10, expected=11)["classification"], "INCOMPLETE_TERMINAL")
        self.assertFalse(self.classify([4.] * 10, numerical_failure=True)["seed_candidate"])

    def test_no_silent_truncation_nonfinite_or_extra_frames(self):
        for d, r, kw in (([4.] * 10, [4.] * 9, {}), ([float("nan")], [4.], {}),
                         ([4.] * 10, [4.] * 10, {"expected": 9})):
            with self.assertRaises(ValueError):
                self.classify(d, r, **kw)

    def test_stage_time_and_start_checks(self):
        self.assertEqual(self.classify([4.] * 100, frame_ns=.001)["covered_ns"], .1)
        self.assertEqual(self.classify([4.] * 100, frame_ns=.01)["covered_ns"], 1)
        self.assertEqual(self.classify([4.] * 9, stage="production")["start_check"], "INSUFFICIENT_FRAMES")
        self.assertEqual(self.classify([20.] * 10, stage="production")["start_check"], "REVIEW_UNBOUND_START")
        self.assertEqual(stats([1., 3., 5.], .1)["last1ns_mean_A"], 3.)

    def test_reader_rejects_misaligned_skipped_bad_and_stride_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "series.dat"
            for content in ("1 4\n3 5\n", "1 4\n1 5\n", "1 bad\n", "1 nan\n", "", "1 4 8\n"):
                p.write_text(content)
                with self.assertRaises(ValueError):
                    read_series(p)
            p.write_text("# frame value\n1.000 4\n2.000 5\n")
            self.assertEqual(read_series(p), [4, 5])


if __name__ == "__main__":
    unittest.main()
