#!/usr/bin/env python3
"""Read-only, paired-series heartbeat classification. Never submits or confirms koff.

Implements the corrected two-metric campaign screening rule. A candidate still
needs the stage's structural/scientific review. No directory globbing or default
trajectory duration: explicit files, scheduler state and own md.in are required.
"""
import argparse
import json
import math
from pathlib import Path
import sys

from check_ligamd3_tutorial_params import read_cntrl, number, validate, natom

VERSION = "paired-v1-20260919"
STATES = ("COMPLETED", "RUNNING", "PENDING", "FAILED", "CANCELLED", "TIMEOUT",
          "NODE_FAIL", "OUT_OF_MEMORY", "PREEMPTED", "BOOT_FAIL", "UNKNOWN")


def read_series(path):
    values = []
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise ValueError(f"{Path(path).name}: expected frame/value, not silently skipped data")
        frame, value = map(float, fields)
        if not math.isfinite(frame) or frame != len(values) + 1:
            raise ValueError(f"{Path(path).name}: frames must be contiguous from 1")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{Path(path).name}: nonfinite/negative value")
        values.append(value)
    if not values:
        raise ValueError(f"{Path(path).name}: empty series")
    return values


def stats(values, frame_ns):
    n = len(values)
    onset = next((i for i, value in enumerate(values) if value >= 14), None)
    support = 0 if onset is None else n - onset
    sustained = None if onset is None else sum(v >= 14 for v in values[onset:]) / support
    def tail_mean(duration):
        count = max(1, math.ceil(duration / frame_ns))
        tail = values[-count:]
        return sum(tail) / len(tail)
    return {
        "frames": n, "max_A": max(values), "last_A": values[-1],
        "fraction_ge10": sum(v >= 10 for v in values) / n,
        "onset_ns": None if onset is None else (onset + 1) * frame_ns,
        "onset_fraction": None if onset is None else onset / n,
        "post_onset_frames": support, "post_onset_span_ns": max(0, support - 1) * frame_ns,
        "sustained_fraction": sustained,
        "last1ns_mean_A": tail_mean(1), "last5ns_mean_A": tail_mean(5),
        "first10_mean_A": sum(values[:10]) / min(10, n),
    }


def classify(distance, rmsd, *, stage, state, expected, captured, frame_ns,
             parameters_valid=False, numerical_failure=False):
    if stage not in ("equil", "production") or state not in STATES:
        raise ValueError("unknown stage/scheduler state")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0:
        raise ValueError("expected must be a positive integer")
    if not isinstance(captured, int) or isinstance(captured, bool) or not 0 < captured <= expected:
        raise ValueError("captured frame count must come from the actual trajectory")
    if not math.isfinite(frame_ns) or frame_ns <= 0:
        raise ValueError("invalid frame interval")
    if len(distance) != len(rmsd) or len(distance) != captured:
        raise ValueError("paired arrays must exactly match captured trajectory frames; never truncate to min")
    if any(not math.isfinite(v) or v < 0 for v in distance + rmsd):
        raise ValueError("nonfinite/negative paired metric")
    d, r = stats(distance, frame_ns), stats(rmsd, frame_ns)
    result = dict(version=VERSION, stage=stage, job_state=state, frames=captured,
                  expected_frames=expected, covered_ns=captured * frame_ns,
                  distance=d, rmsd=r, seed_candidate=False, scientifically_confirmed=False)
    if not parameters_valid:
        label = "PARAMETERS_UNVERIFIED"
    elif numerical_failure or state in ("FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL",
                                        "OUT_OF_MEMORY", "PREEMPTED", "BOOT_FAIL"):
        label = "FAILED_OR_STOPPED_PARTIAL_NOT_EVIDENCE"
    elif state in ("UNKNOWN", "PENDING"):
        label = "SCHEDULER_STATE_CONFLICT"
    elif state == "COMPLETED" and captured != expected:
        label = "INCOMPLETE_TERMINAL"
    else:
        dep = []
        for s in (d, r):
            if s["onset_ns"] is None:
                dep.append("none")
            elif s["post_onset_frames"] < 2:
                dep.append("insufficient")  # one observation has no sustained duration
            elif s["onset_fraction"] >= 0.9 and s["sustained_fraction"] < 0.8:
                dep.append("censored")
            elif s["sustained_fraction"] >= 0.8:
                dep.append("departed")
            else:
                dep.append("weak")
        if state == "RUNNING":
            label = "PREFIX_DEPARTURE_CANDIDATE" if dep == ["departed", "departed"] else "PREFIX_ONLY"
        elif d["max_A"] < 10 and r["max_A"] < 10:
            label = "CLEAN_BOUND" if stage == "equil" else "BOUND_AT_TERMINAL"
            result["seed_candidate"] = stage == "equil"
        elif dep == ["departed", "departed"]:
            label = "DEPARTURE_CANDIDATE"
        elif "insufficient" in dep:
            label = "INSUFFICIENT_POST_ONSET_COVERAGE"
        elif "departed" in dep:
            label = "DEPARTURE_UNCONFIRMED_ONE_METRIC"
        elif "censored" in dep:
            label = "CENSORED_UNDETERMINED"
        elif max(d["max_A"], r["max_A"]) >= 13:
            label = "SEED_EXCLUDED_GE13"
        else:
            label = "EDGE"
    result["classification"] = label
    if stage == "production":
        result["start_check"] = "INSUFFICIENT_FRAMES" if captured < 10 else (
            "REVIEW_UNBOUND_START" if d["first10_mean_A"] >= 10 else "DISTANCE_SCREEN_PASSED")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--distance", type=Path, required=True)
    parser.add_argument("--rmsd", type=Path, required=True)
    parser.add_argument("--mdin", type=Path, required=True)
    parser.add_argument("--stage", choices=("equil", "production"), required=True)
    parser.add_argument("--state", choices=STATES, required=True)
    parser.add_argument("--captured-frames", type=int, required=True)
    parser.add_argument("--numerical-failure", action="store_true")
    args = parser.parse_args()
    try:
        params = read_cntrl(args.mdin)
        dt, stride, steps = (number(params.get(k)) for k in ("dt", "ntwx", "nstlim"))
        if any(v is None or v <= 0 for v in (dt, stride, steps)) or any(
            v != v.to_integral_value() for v in (stride, steps)
        ):
            raise ValueError("invalid dt/ntwx/nstlim in exact md.in")
        parameter_errors = validate(params, args.stage, natom(args.mdin.parent / "step3_input.parm7"))
        result = classify(read_series(args.distance), read_series(args.rmsd), stage=args.stage,
                          state=args.state, expected=int(steps // stride), captured=args.captured_frames,
                          frame_ns=float(dt * stride / 1000), parameters_valid=not parameter_errors,
                          numerical_failure=args.numerical_failure)
        result["parameter_errors"] = parameter_errors
        print(json.dumps(result, allow_nan=False))
        return 1 if parameter_errors else 0
    except (OSError, ValueError, ArithmeticError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
