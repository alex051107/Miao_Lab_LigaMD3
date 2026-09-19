# LiGaMD3 parameter validation

Start here when preparing **new** Equilibration (Equil) or Production inputs.
This tool checks the project's LiGaMD3 tutorial/lab parameter profile. It does
not run AMBER, select sigma, establish a bound seed, or authorize submission.
Historical workflow examples are not a substitute for this check.

## Check an input

Requires Python 3.10+ and Bash; no third-party Python packages or cluster access.

```sh
# Diagnostic: fixed parameters only if no cMD source is available.
python3 _scripts/check_ligamd3_tutorial_params.py JOB_DIR equil

# Submission parameter/file gate: the exact source cMD input is mandatory.
bash _scripts/validate_before_submit.sh JOB_DIR equil --cmd-input SOURCE_CMD_MDIN
bash _scripts/validate_before_submit.sh REPLICA_DIR production --cmd-input SOURCE_CMD_MDIN

# With no --cmd-input, the submission gate requires JOB_DIR/cmd-source.mdin.
# This can be a recorded link to the actual source input in a NEW staging area.
bash _scripts/validate_before_submit.sh JOB_DIR
```

Pass the individual job/replica directory, not `md.in` or a Production group.
Stage names are `equil`, `production`, and `auto`; unknown names are errors.
`auto` reads `irest_gamd` from the parsed input, never from the directory name.
Explicit stage and launch-script stage must agree with the input.

Both commands are read-only. Exit 0 means the stated checks passed, not that the
job is safe to submit. Exit 1 is a failed check/read; invalid command-line usage
returns nonzero. A fixed-only diagnostic explicitly prints **cMD source
UNVERIFIED**. The submission entry point cannot downgrade to that diagnostic.

## What is checked

| Scope | Requirements |
| --- | --- |
| Both stages | `ntf=1`, `barostat=1`, `irest=0`, `ntx=1`, `tempi=temp0`; the fixed thermostat, integration, boost, output-format, and ligand settings in `COMMON` |
| System inheritance | `temp0`, `ntp`, `taup` match the explicitly identified conventional MD (cMD) source; surface-tension keys match when present in either input |
| Topology/time | Read NATOM from the target `step3_input.parm7`; `ntave>=4*NATOM` in both stages; positive integral counts/indices and finite positive temperatures, sigma, and contact distance |
| Equil only | `irest_gamd=0`, `ntcmd=10*ntave`, both preparation windows `2*ntave`, positive `nteb` divisible by `ntave`, `nstlim=ntcmd+nteb` |
| Production only | `irest_gamd=1`, `ntcmd=nteb=ntcmdprep=ntebprep=0`, `nstlim=50000000`, `ntpr=ntwx=500` |
| Submission file gate | One stage-appropriate launch script, required topology/restart/boost files, supported literal launch flags, no checked output aliasing a checked input |

The Equil timing multipliers do **not** apply to Production. Instruction
summaries that group these timing expressions under “both stages” are ambiguous;
use the two explicit rows above. These are the current **lab profile**, not a
claim that all AMBER or LiGaMD configurations must use this profile.

The original parameter correction follows the group's LiGaMD3-Tutorial-2024
(pp. 9–14, fixed switches/new-velocity starts) and the lab's Equil timing and
100 ns Production conventions. This patch enforces those existing requirements;
it does not establish their scientific validity through new simulations.

### Parsing and launch restrictions

Exactly one line-start `&cntrl` group terminated with `/` is required. The parser
accepts case-insensitive names, scalar assignments, quoted strings, Fortran
double-quote escaping, `!` comments, and E/D numeric exponents. Duplicate keys,
nonfinite numbers, missing terminators, arrays, and unsupported syntax fail
closed. Titles and other namelists cannot supply missing parameters.

The launch check supports one literal `pmemd.cuda` command (line continuations
are allowed), `-O`, and exactly one each of `-i`, `-p`, `-c`, `-r`, `-o`, `-x`,
and `-gamd` using the conventional stage filenames. `command -v pmemd.cuda` is
allowed. Dynamic filenames, wrappers such as `srun`, extra flags, and multiple
launches are rejected pending an explicitly supported template. This is a
conservative static flag check, **not** a shell interpreter or a proof that
arbitrary earlier shell code cannot modify a file or change directory.

## Source evidence and remaining gates

An input having the same temperature as another file does not prove that the
other file belongs to the right system. The staging/review record must identify
the exact completed cMD lineage, topology, and seed. Do not pick a convenient
source just to obtain a PASS. A target `md.in`, or a GaMD input, is not a cMD
source. `LIGAMD3_TEMP`, if supplied, is an additional check, not a replacement
for cMD evidence.

**Missing source parameters must be resolved, not guessed.** Some generated
cMD inputs omit `taup`. The checker deliberately does not assume an AMBER
default, copy a value from another system, or silently normalize it to the
solution template. Resolve the actually effective cMD setting and the
applicable tutorial policy before integrating such a source. This release
does not parse effective runtime settings from AMBER output. Do not edit a
finished/frozen cMD input or manufacture an “explicit” source to get past this
restriction. Such a job is blocked by this gate until the evidence interface
and any necessary scientific decision are resolved.

Separate checks remain mandatory for:

- force-field/ligand identity, atom ordering, the physical contact pair and
  `dblig`, and a topology that is genuinely valid (NATOM/file size is not enough);
- complete Equil evidence, a still-bound exact seed and the authorized sigma
  boundary; Production's exact-seed inheritance and boost/restart provenance;
- reviewed launch-script behavior, permissions/ownership, frozen artifacts and
  changes between validation, submission, and actual execution;
- live queue/accounting reconciliation and retained submission intents.

This gate no longer queries `squeue` or prints “no existing jobs” when a query
fails. It never establishes queue state. The action layer must reconcile exact
WorkDirs/receipts before submission; an unknown scheduler response is not
permission to retry. An existing `safe_submit.sh` caller can still invoke this
validator with one directory, but now needs the explicit recorded cMD source.
Its independent review and submission-intent protections must remain in place.

## Deployment boundary

This PR is a **review candidate, not a live rollout**. It adds a self-contained
version of two previously untracked operational tools. It does not update a
running automation, rewrite a job, replace a remote shared tool, or submit a
simulation. The existing rule/skill copies and source-staging conventions must
be reconciled before activation; the missing-source behavior above is an
intentional compatibility break, not something to bypass.

After review, stage a versioned tool release, run the tests on the execution
host, validate representative exact new job artifacts in read-only mode, and
record which entry point/version the automation actually calls. Coordinate
shared-runtime changes with other operators. Do not mass-edit frozen inputs or
resubmit old work as part of deploying a checker. A return to an older release
must not silently re-enable the known false-PASS paths.

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_ligamd3_parameter_gate.py' -v
bash -n _scripts/validate_before_submit.sh
```

Fixtures are synthetic, intentionally not usable simulations. Tests exercise
fixed-key deletions/mutations, historical wrong switches, parser bypasses,
stage/time rules, cMD inheritance, missing tools/files, and the shell entry
point. They demonstrate these validation behaviors, not AMBER execution,
independent scientific review, or correctness of existing trajectories.
