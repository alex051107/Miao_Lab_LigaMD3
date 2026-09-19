"""Synthetic fixtures only: no simulation data, Slurm, SSH, or AMBER required."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "_scripts/check_ligamd3_tutorial_params.py"
WRAPPER = ROOT / "_scripts/validate_before_submit.sh"
spec = importlib.util.spec_from_file_location("parameter_gate", CHECKER)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def parameters(mode="equil"):
    values = {key: str(value) for key, value in gate.COMMON.items()}
    values.update(ntp="1", taup="0.5", temp0="310", tempi="310",
                  watnam="WAT", owtnm="O", timask1=":10", scmask1=":10",
                  timask2="", scmask2="", edpro2atm="100", ntwprt="120",
                  atom_p="50", atom_l="2", dblig="2.78", sigma0p="1.5",
                  ntave="4000", ntcmd="40000", nteb="12000", ntcmdprep="8000",
                  ntebprep="8000", nstlim="52000", irest_gamd="0",
                  ntpr="5000", ntwx="5000", ntwr="5000")
    if mode == "production":
        values.update(irest_gamd="1", ntcmd="0", nteb="0", ntcmdprep="0",
                      ntebprep="0", nstlim="50000000", ntpr="500", ntwx="500")
    return values


def mdin(values):
    strings = {"watnam", "owtnm", "timask1", "timask2", "scmask1", "scmask2"}
    return "Synthetic test input\n&cntrl\n" + "".join(
        f" {key} = {repr(value) if key in strings else value},\n"
        for key, value in values.items()) + "/\n"


def fixture(directory, mode="equil"):
    (directory / "md.in").write_text(mdin(parameters(mode)))
    (directory / "cmd-source.mdin").write_text(mdin({"temp0": "310", "ntp": "1", "taup": "0.5"}))
    (directory / "step3_input.parm7").write_text(
        "%VERSION synthetic fixture\n%FLAG POINTERS\n%FORMAT(10I8)\n    1000       0\n" + "%COMMENT synthetic padding\n" * 80)
    coordinate = "step5_10.rst7" if mode == "equil" else "gamd-1.rst"
    (directory / coordinate).write_text("synthetic coordinates, not usable by AMBER\n" + "0" * 100001)
    if mode == "production":
        (directory / "gamd-restart.dat").write_text("synthetic boost state\n" + "0" * 101)
    script = "run-equil.pbs" if mode == "equil" else "run-prod.pbs"
    restart = "gamd-1.rst" if mode == "equil" else "md-1.rst"
    (directory / script).write_text(
        "#!/bin/bash\n#SBATCH --job-name=synthetic\nset -euo pipefail\n"
        "command -v pmemd.cuda\n"
        f"pmemd.cuda -O -i md.in -p step3_input.parm7 -c {coordinate} "
        f"-r {restart} -o md-1.out -x md-1.nc -gamd gamd-1.log\n")


class ParserTests(unittest.TestCase):
    def test_comments_case_strings_and_fortran_exponents(self):
        p = gate.parse_cntrl("Title ntf=2\n&CNTRL\n NTF=1, dt=2D-3, ! ntf=2\n mask=':1@N!x/y', name='can''t' /\n&other ntf=2 /\n")
        self.assertEqual(p["ntf"], "1")
        self.assertEqual(p["mask"], ":1@N!x/y")
        self.assertEqual(p["name"], "can't")
        self.assertEqual(gate.number(p["dt"]), gate.Decimal("0.002"))

    def test_duplicate_keys_rejected_even_if_equal(self):
        for duplicate in ("ntf=2", "NTF=1", "barostat=2"):
            with self.subTest(duplicate=duplicate), self.assertRaises(gate.InvalidInput):
                gate.parse_cntrl("&cntrl ntf=1, barostat=1, " + duplicate + " /\n")

    def test_missing_values_not_taken_from_other_groups_or_title(self):
        p = gate.parse_cntrl("ntf=1\n&cntrl dt=.002 /\n&extra ntf=1 /\n")
        self.assertNotIn("ntf", p)

    def test_malformed_namelists_fail_closed(self):
        for text in ("ntf=1", "&cntrl ntf=1", "&cntrl ntf=1 /\n&cntrl ntf=2 /",
                     "&cntrl mask='unterminated /", "&cntrl ntf(1)=1 /",
                     "&cntrl ntf=1 rubbish /", "&cntrl ntf=1 &end", "&cntrl ntf='1'bad /", "&cntrl ntf='1' /"):
            with self.subTest(text=text), self.assertRaises(gate.InvalidInput):
                gate.parse_cntrl(text)


class ParameterTests(unittest.TestCase):
    def test_tutorial_and_lab_profile_values_are_pinned(self):
        # Independent oracle: do not derive the required values from COMMON.
        required = {
            "imin": 0, "ntt": 3, "gamma_ln": 1, "ig": -1, "cut": 9,
            "dt": "0.002", "ntc": 2, "ntf": 1, "ntb": 2, "ntxo": 2,
            "ioutfm": 1, "iwrap": 1, "barostat": 1, "pres0": 1,
            "igamd": 28, "sigma0d": 6, "sigma0b": 6, "iep": 2,
            "ied": 1, "ieb": 1, "bgpro2atm": 1, "gti_cpu_output": 0,
            "gti_add_sc": 1, "icfe": 1, "ifsc": 1, "ibblig": 1, "nlig": 1,
            "irest": 0, "ntx": 1,
        }
        self.assertEqual(gate.COMMON, required)

    def test_valid_equil_and_production(self):
        for mode in ("equil", "production"):
            self.assertEqual(gate.validate(parameters(mode), mode, 1000), [])

    def test_every_fixed_parameter_missing_or_mutated_fails(self):
        for mode in ("equil", "production"):
            for key in gate.COMMON:
                for mutation in (None, "999"):
                    with self.subTest(mode=mode, key=key, mutation=mutation):
                        p = parameters(mode)
                        if mutation is None:
                            del p[key]
                        else:
                            p[key] = mutation
                        self.assertTrue(gate.validate(p, mode, 1000))

    def test_historical_bad_template_and_each_switch_blocked(self):
        bad = {"ntf": "2", "barostat": "2", "irest": "1", "ntx": "5"}
        for changes in (bad, *({key: value} for key, value in bad.items())):
            for mode in ("equil", "production"):
                with self.subTest(changes=changes, mode=mode):
                    self.assertTrue(gate.validate(parameters(mode) | changes, mode, 1000))

    def test_finite_positive_integers_and_topology_bounds(self):
        for key in ("temp0", "sigma0p", "dblig", "atom_p", "atom_l", "ntave"):
            for invalid in ("nan", "inf", "-inf", "0", "-1"):
                with self.subTest(key=key, invalid=invalid):
                    self.assertTrue(gate.validate(parameters() | {key: invalid}, "equil", 1000))
        for key in ("atom_p", "atom_l", "ntwprt", "edpro2atm", "ntave", "nteb", "ntwr"):
            self.assertTrue(gate.validate(parameters() | {key: "1.5"}, "equil", 1000))
        self.assertTrue(gate.validate(parameters() | {"atom_p": "1001"}, "equil", 1000))

    def test_stage_and_time_chain(self):
        for changes in ({"nteb": "12001"}, {"ntcmdprep": "8001"}, {"nstlim": "51999"},
                        {"ntcmd": "40001"}, {"tempi": "300"}):
            self.assertTrue(gate.validate(parameters() | changes, "equil", 1000))
        for changes in ({"ntave": "1"}, {"nteb": "12000"}, {"ntwx": "5000"}, {"nstlim": "49999999"}):
            self.assertTrue(gate.validate(parameters("production") | changes, "production", 1000))
        self.assertTrue(gate.validate(parameters(), "equilibration", 1000))
        self.assertTrue(gate.validate(parameters(), "production", 1000))

    def test_cmd_inheritance_and_membrane_surface_terms(self):
        cmd = {"temp0": "310", "ntp": "1", "taup": "0.5"}
        self.assertEqual(gate.validate(parameters(), "equil", 1000, cmd), [])
        for key, wrong in (("temp0", "300"), ("ntp", "3"), ("taup", "1")):
            self.assertTrue(gate.validate(parameters(), "equil", 1000, cmd | {key: wrong}))
        self.assertTrue(gate.validate(parameters(), "equil", 1000, {}))
        surface = {"ntp": "3", "taup": "1", "csurften": "3", "gamma_ten": "0", "ninterface": "2"}
        self.assertEqual(gate.validate(parameters() | surface, "equil", 1000, cmd | surface), [])
        for key in gate.SURFACE:
            changed = parameters() | surface
            del changed[key]
            self.assertTrue(gate.validate(changed, "equil", 1000, cmd | surface))
        for temperature in ("nan", "300", "invalid", ""):
            self.assertTrue(gate.validate(parameters(), "equil", 1000, cmd, temperature))


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ligamd3-gate-test-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        fixture(self.directory)

    def run_gate(self, *args, wrapper=True):
        command = ["bash", str(WRAPPER)] if wrapper else [sys.executable, str(CHECKER)]
        env = os.environ.copy()
        env.pop("LIGAMD3_TEMP", None)
        env.pop("LIGAMD3_CMD_INPUT", None)
        env.pop("LIGAMD3_REFERENCE_EQUIL", None)
        return subprocess.run(command + [str(self.directory), *args], capture_output=True, text=True, env=env, timeout=10)

    def test_valid_wrapper_and_no_submission_side_effect(self):
        before = sorted(p.name for p in self.directory.iterdir())
        for mode in ((), ("equil",), ("auto",)):
            result = self.run_gate(*mode)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("queue state are NOT established", result.stdout)
        self.assertEqual(before, sorted(p.name for p in self.directory.iterdir()))

    def test_missing_source_blocks_wrapper_but_labels_fixed_only_audit(self):
        (self.directory / "cmd-source.mdin").unlink()
        self.assertNotEqual(self.run_gate().returncode, 0)
        result = self.run_gate(wrapper=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("cMD source UNVERIFIED", result.stdout)

    def test_explicit_source_and_invalid_source(self):
        source = self.directory / "cmd-source.mdin"
        renamed = self.directory / "chosen-source.mdin"
        source.rename(renamed)
        self.assertEqual(self.run_gate("equil", "--cmd-input", str(renamed)).returncode, 0)
        self.assertNotEqual(self.run_gate("--cmd-input", str(self.directory / "md.in")).returncode, 0)
        renamed.write_text(mdin({"igamd": "28", "temp0": "310", "ntp": "1", "taup": "0.5"}))
        self.assertNotEqual(self.run_gate("--cmd-input", str(renamed)).returncode, 0)

    def test_no_parameter_path_bypasses_wrapper(self):
        valid = mdin(parameters())
        for invalid in (valid.replace(" ntf = 1,\n", "") + "&extra ntf=1 /\n",
                        valid.replace("/\n", "ntf=2, /\n"),
                        valid.replace("igamd = 28", "igamd = 0"),
                        valid.replace(" temp0 = 310,", " temp0 = 300,").replace("tempi = 310", "tempi = 300"),
                        valid.replace("/\n", "")):
            with self.subTest(invalid=invalid[-120:]):
                (self.directory / "md.in").write_text(invalid)
                self.assertNotEqual(self.run_gate().returncode, 0)
        (self.directory / "md.in").write_text(valid.upper().replace("SYNTHETIC TEST INPUT", "Synthetic"))
        self.assertEqual(self.run_gate().returncode, 0)

    def test_bad_stage_paths_and_topology_fail_cleanly(self):
        for mode in ("equilibration", "typo", "production"):
            self.assertNotEqual(self.run_gate(mode).returncode, 0)
        (self.directory / "step3_input.parm7").write_text("%FLAG POINTERS\n%FORMAT(10I8)\n")
        self.assertNotEqual(self.run_gate().returncode, 0)
        (self.directory / "md.in").unlink()
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_wrong_ambiguous_or_dynamic_launch_blocks(self):
        script = self.directory / "run-equil.pbs"
        valid = script.read_text()
        for invalid in (valid.replace("-i md.in", "-i other.in"),
                        valid.replace("-p step3_input.parm7", "-p other.parm7"),
                        valid.replace("-i md.in", "-i md.in -i other.in"),
                        valid.replace("-c step5_10.rst7", "-c $SEED"),
                        valid.replace("-gamd gamd-1.log", "-gamd md.in"),
                        valid.replace("-O -i", "-O -inf md.in -i"),
                        valid.replace("pmemd.cuda -O", "srun pmemd.cuda -O"),
                        valid + "pmemd.cuda -i other.in\n"):
            script.write_text(invalid)
            self.assertNotEqual(self.run_gate().returncode, 0)
        script.write_text(valid)
        (self.directory / "run-prod.pbs").write_text(valid)
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_missing_checker_is_not_success(self):
        standalone = self.directory / "validate_before_submit.sh"
        shutil.copyfile(WRAPPER, standalone)
        result = subprocess.run(["bash", str(standalone), str(self.directory)], capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)

    def test_production_and_input_output_alias(self):
        (self.directory / "run-equil.pbs").unlink()
        fixture(self.directory, "production")
        self.assertEqual(self.run_gate("production").returncode, 0)
        (self.directory / "run-prod.pbs").rename(self.directory / "run-equil.pbs")
        script = self.directory / "run-equil.pbs"
        script.write_text(script.read_text().replace("command -v pmemd.cuda", "which pmemd.cuda"))
        self.assertEqual(self.run_gate("production").returncode, 0)
        (self.directory / "md-1.rst").symlink_to("gamd-1.rst")
        self.assertNotEqual(self.run_gate("production").returncode, 0)

    def test_exact_reference_allows_reviewed_replication_without_inventing_cmd_defaults(self):
        reference = self.directory / "reference"
        reference.mkdir()
        fixture(reference)
        (self.directory / "cmd-source.mdin").unlink()
        result = self.run_gate("equil", "--reference-equil", str(reference))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("original cMD transition requires its existing review", result.stdout)
        (self.directory / "md.in").write_text(mdin(parameters() | {"sigma0p": "1.7"}))
        self.assertEqual(self.run_gate("--reference-equil", str(reference)).returncode, 0)
        (self.directory / "md.in").write_text(mdin(parameters() | {"taup": "1"}))
        self.assertNotEqual(self.run_gate("--reference-equil", str(reference)).returncode, 0)
        (self.directory / "md.in").write_text(mdin(parameters()))
        (reference / "step5_10.rst7").write_text("changed")
        self.assertNotEqual(self.run_gate("--reference-equil", str(reference)).returncode, 0)

    def test_production_reference_checks_exact_seed_sigma_and_parameters(self):
        reference = self.directory / "reference"
        reference.mkdir()
        fixture(reference)
        (self.directory / "run-equil.pbs").unlink()
        fixture(self.directory, "production")
        for name in ("gamd-1.rst", "gamd-restart.dat"):
            shutil.copyfile(self.directory / name, reference / name)
        self.assertEqual(self.run_gate("production", "--reference-equil", str(reference)).returncode, 0)
        (reference / "md.in").write_text(mdin(parameters() | {"sigma0p": "1.7"}))
        self.assertNotEqual(self.run_gate("production", "--reference-equil", str(reference)).returncode, 0)
        (reference / "md.in").write_text(mdin(parameters() | {"ntf": "2"}))
        self.assertNotEqual(self.run_gate("production", "--reference-equil", str(reference)).returncode, 0)


if __name__ == "__main__":
    unittest.main()
