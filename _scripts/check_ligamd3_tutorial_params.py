#!/usr/bin/env python3
"""Read-only LiGaMD3 tutorial/lab-profile validation, not scientific approval.

See docs/parameter-validation.md for the supported input syntax, source contract,
and deployment boundary. Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import shlex
import sys


class InvalidInput(ValueError):
    pass


def parse_cntrl(text: str) -> dict[str, str]:
    """Parse exactly one terminated, scalar &cntrl; never search later groups.

    Deliberately reject duplicates and unsupported syntax instead of trying to
    reproduce Fortran's override semantics. Keys/groups are case insensitive;
    quoted strings (including doubled quotes) and ! comments are supported.
    """
    starts = list(re.finditer(r"(?im)^[ \t]*&cntrl\b", text))
    if len(starts) != 1:
        raise InvalidInput("expected exactly one &cntrl namelist on its own line")
    pos = starts[0].end()
    body = []
    quote = None
    while pos < len(text):
        char = text[pos]
        if quote:
            if char in "\r\n":
                raise InvalidInput("multiline quoted values are unsupported")
            body.append(char)
            if char == quote:
                if pos + 1 < len(text) and text[pos + 1] == quote:
                    body.append(char)
                    pos += 1
                else:
                    quote = None
        elif char in "\"'":
            quote = char
            body.append(char)
        elif char == "!":
            end = text.find("\n", pos)
            pos = len(text) if end < 0 else end
            body.append("\n")
            continue
        elif char == "/":
            break
        else:
            body.append(char)
        pos += 1
    else:
        raise InvalidInput("missing / terminator (or unterminated quote) in &cntrl")

    body = "".join(body)
    assignment = re.compile(
        r"([A-Za-z][A-Za-z0-9_]*)\s*=\s*"
        r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|[^\s,=/&]+)"
    )
    values = {}
    pos = 0
    while pos < len(body):
        separator = re.match(r"[\s,]*", body[pos:])
        pos += separator.end()
        if pos == len(body):
            break
        match = assignment.match(body, pos)
        if not match:
            raise InvalidInput(f"unsupported &cntrl syntax near {body[pos:pos + 40]!r}")
        key, value = match.groups()
        key = key.lower()
        if key in values:
            raise InvalidInput(f"duplicate &cntrl assignment: {key}")
        if value[0] in "\"'":
            value = value[1:-1].replace(value[0] * 2, value[0])
            if number(value) is not None:
                raise InvalidInput(f"quoted numeric assignment is unsupported: {key}")
        values[key] = value
        pos = match.end()
        if pos < len(body) and not body[pos].isspace() and body[pos] != ",":
            raise InvalidInput(f"missing separator after {key}")
    return values


def read_cntrl(path: Path) -> dict[str, str]:
    return parse_cntrl(path.read_text(encoding="utf-8"))


def number(value: str | None) -> Decimal | None:
    if value is None or not re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?", value
    ):
        return None
    try:
        result = Decimal(re.sub("[dD]", "e", value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def natom(path: Path) -> int:
    with path.open(encoding="ascii") as handle:
        for line in handle:
            if line.strip() == "%FLAG POINTERS":
                if not next(handle, "").startswith("%FORMAT("):
                    break
                # AMBER POINTERS is fixed-width 10I8; whitespace also covers
                # small test fixtures and ordinary NATOM values.
                raw = next(handle, "")[:8].strip()
                if re.fullmatch(r"[0-9]+", raw) and int(raw) > 0:
                    return int(raw)
                break
    raise InvalidInput(f"missing or invalid NATOM in {path.name}")


COMMON = {
    "imin": 0, "ntt": 3, "gamma_ln": 1, "ig": -1, "cut": 9,
    "dt": "0.002", "ntc": 2, "ntf": 1, "ntb": 2, "ntxo": 2,
    "ioutfm": 1, "iwrap": 1, "barostat": 1, "pres0": 1,
    "igamd": 28, "sigma0d": 6, "sigma0b": 6, "iep": 2,
    "ied": 1, "ieb": 1, "bgpro2atm": 1, "gti_cpu_output": 0,
    "gti_add_sc": 1, "icfe": 1, "ifsc": 1, "ibblig": 1, "nlig": 1,
    "irest": 0, "ntx": 1,
}
INHERITED = ("temp0", "ntp", "taup")
SURFACE = ("csurften", "gamma_ten", "ninterface")


def validate(values: dict[str, str], mode: str, count: int,
             cmd: dict[str, str] | None = None,
             campaign_temp: str | None = None) -> list[str]:
    errors = []
    def require(ok, message):
        if not ok:
            errors.append(message)
    def num(key):
        return number(values.get(key))
    for key, expected in COMMON.items():
        require(num(key) == Decimal(str(expected)),
                f"{key}={values.get(key)!r}; required {expected}")
    for key in ("ntave", "ntwprt", "edpro2atm", "atom_p", "atom_l",
                "nstlim", "ntpr", "ntwx", "ntwr"):
        v = num(key)
        require(v is not None and v > 0 and v == v.to_integral_value(),
                f"{key} must be a positive integer")
    for key in ("dblig", "sigma0p", "temp0"):
        v = num(key)
        require(v is not None and v > 0, f"{key} must be finite and positive")
    for key in ("ntwprt", "edpro2atm", "atom_p", "atom_l"):
        v = num(key)
        require(v is not None and 0 < v <= count, f"{key} exceeds topology NATOM={count}")
    require(num("ntp") in (1, 3), "ntp must be 1 (solution) or 3 (membrane)")
    require(num("taup") in (Decimal("0.5"), Decimal(1)), "taup must be 0.5 or 1.0")
    require(values.get("watnam") == "WAT" and values.get("owtnm") == "O",
            "watnam/owtnm must be WAT/O")
    require(bool(values.get("timask1")) and values.get("timask1") == values.get("scmask1"),
            "timask1/scmask1 must be equal and nonempty")
    require(not values.get("timask2") and not values.get("scmask2"), "timask2/scmask2 must be empty")
    require(num("temp0") is not None and num("tempi") == num("temp0"), "tempi must equal temp0")
    if campaign_temp is not None:
        expected = number(campaign_temp)
        require(expected is not None and expected > 0 and num("temp0") == expected,
                "temp0 must match finite positive LIGAMD3_TEMP")
    if cmd is not None:
        for key in INHERITED + SURFACE:
            if key in INHERITED or key in cmd or key in values:
                expected = number(cmd.get(key))
                require(expected is not None and num(key) == expected,
                        f"{key} must match the explicit cMD input ({cmd.get(key)!r})")

    ntave, ntcmd, nteb = (num(key) for key in ("ntave", "ntcmd", "nteb"))
    require(ntave is not None and ntave >= 4 * count, "ntave must be >= 4*NATOM in both stages")
    for key in ("ntcmd", "nteb", "ntcmdprep", "ntebprep"):
        v = num(key)
        require(v is not None and v >= 0 and v == v.to_integral_value(),
                f"{key} must be a nonnegative integer")
    if mode == "equil":
        require(num("irest_gamd") == 0, "Equil requires irest_gamd=0")
        valid_window = ntave is not None and ntave > 0 and ntave == ntave.to_integral_value()
        valid_boost = nteb is not None and nteb > 0 and nteb == nteb.to_integral_value()
        # Integer arithmetic avoids rounding and Decimal context-dependent %.
        require(valid_window and valid_boost and int(nteb) % int(ntave) == 0,
                "nteb must be a positive integer multiple of ntave")
        require(valid_window and ntcmd == 10 * ntave, "ntcmd must equal 10*ntave")
        require(valid_window and num("ntcmdprep") == num("ntebprep") == 2 * ntave,
                "ntcmdprep and ntebprep must equal 2*ntave")
        require(ntcmd is not None and nteb is not None and num("nstlim") == ntcmd + nteb,
                "nstlim must equal ntcmd+nteb")
    elif mode == "production":
        for key, expected in {"irest_gamd": 1, "ntcmd": 0, "nteb": 0,
                              "ntcmdprep": 0, "ntebprep": 0, "nstlim": 50000000,
                              "ntpr": 500, "ntwx": 500}.items():
            require(num(key) == expected, f"Production requires {key}={expected}")
    else:
        errors.append(f"unknown mode {mode!r}")
    return errors


def check_submission_files(directory: Path, mode: str) -> list[str]:
    """Check the supported literal launch template; never execute its shell."""
    errors = []
    expected_script = "run-equil.pbs" if mode == "equil" else "run-prod.pbs"
    scripts = [p.name for p in (directory / name for name in
               ("run-equil.pbs", "run-prod.pbs", "sub-cmd.slum")) if p.exists()]
    if scripts != [expected_script]:
        return [f"expected only {expected_script}; found {scripts}"]
    coordinate = "step5_10.rst7" if mode == "equil" else "gamd-1.rst"
    restart = "gamd-1.rst" if mode == "equil" else "md-1.rst"
    required = {"step3_input.parm7": 1000, coordinate: 100000}
    if mode == "production":
        required["gamd-restart.dat"] = 100
    for name, minimum in required.items():
        path = directory / name
        if not path.is_file() or path.stat().st_size <= minimum:
            errors.append(f"{name} missing or too small (requires >{minimum} bytes)")
    commands = []
    script = (directory / expected_script).read_text(encoding="utf-8").replace("\\\n", " ")
    for line in script.splitlines():
        tokens = shlex.split(line, comments=True)
        if tokens and any("pmemd.cuda" in token for token in tokens):
            if tokens == ["command", "-v", "pmemd.cuda"]:
                continue
            if tokens[0] != "pmemd.cuda" or any(c in line for c in "$`;|&<>"):
                errors.append("unsupported dynamic/wrapped pmemd.cuda launch; use the literal template")
            else:
                commands.append(tokens)
    if len(commands) != 1:
        return errors + ["expected exactly one literal pmemd.cuda launch"]
    tokens = commands[0]
    for flag, value in {"-i": "md.in", "-p": "step3_input.parm7", "-c": coordinate,
                        "-r": restart, "-o": "md-1.out", "-x": "md-1.nc",
                        "-gamd": "gamd-1.log"}.items():
        positions = [i for i, token in enumerate(tokens) if token == flag]
        if len(positions) != 1 or positions[0] + 1 >= len(tokens) or tokens[positions[0] + 1] != value:
            errors.append(f"launch must specify exactly one {flag} {value}")
    # Unknown flags could redirect an additional output onto a checked input.
    allowed = {"-i", "-p", "-c", "-r", "-o", "-x", "-gamd"}
    pos = 1
    while pos < len(tokens):
        if tokens[pos] == "-O":
            pos += 1
        elif tokens[pos] in allowed and pos + 1 < len(tokens):
            pos += 2
        else:
            errors.append(f"unsupported launch argument {tokens[pos]!r}")
            break
    inputs = [directory / name for name in ("md.in", *required)]
    for name in (restart, "md-1.out", "md-1.nc", "gamd-1.log"):
        output = directory / name
        for source in inputs:
            if output.resolve() == source.resolve() or (output.exists() and source.exists() and output.samefile(source)):
                errors.append(f"output {name} aliases input {source.name}")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("mode", nargs="?", choices=("auto", "equil", "production"), default="auto")
    parser.add_argument("--cmd-input", type=Path, help="exact source cMD production input")
    parser.add_argument("--submission", action="store_true", help="require cMD source and launch/file checks; does not submit")
    args = parser.parse_args(argv)
    try:
        if not args.job_dir.is_dir():
            raise InvalidInput("job_dir must be an existing individual job directory, not an md.in file")
        values = read_cntrl(args.job_dir / "md.in")
        mode = args.mode
        if mode == "auto":
            restart = number(values.get("irest_gamd"))
            if restart not in (0, 1):
                raise InvalidInput("cannot infer stage: irest_gamd must be 0 or 1")
            mode = "equil" if restart == 0 else "production"
        source = args.cmd_input or (args.job_dir / "cmd-source.mdin")
        cmd = None
        if args.cmd_input is not None or source.exists() or args.submission:
            if source.resolve() == (args.job_dir / "md.in").resolve() or (
                source.exists() and source.samefile(args.job_dir / "md.in")
            ):
                raise InvalidInput("cMD source cannot be the target md.in")
            cmd = read_cntrl(source)
            if "igamd" in cmd and number(cmd["igamd"]) != 0:
                raise InvalidInput("cMD source must not be a GaMD input")
        errors = validate(values, mode, natom(args.job_dir / "step3_input.parm7"),
                          cmd, os.environ.get("LIGAMD3_TEMP"))
        if args.submission:
            errors.extend(check_submission_files(args.job_dir, mode))
        if errors:
            for error in errors:
                print(f"[FAIL] {error}")
            print(f"FAIL ({len(errors)}) mode={mode}")
            return 1
        scope = "PARAMETERS_AND_CMD_SOURCE" if cmd is not None else "FIXED_PARAMETERS_ONLY; cMD source UNVERIFIED"
        print(f"PASS {scope} mode={mode}")
        print("Scientific eligibility, exact source lineage, atom identity, and queue state are NOT established.")
        return 0
    except (OSError, UnicodeError, ValueError, ArithmeticError) as error:
        print(f"[FAIL] {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
