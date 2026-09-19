# Decision: one parameter parser before submission

## Incident: parameter validation can falsely pass

The operational input generator previously copied conventional-MD dynamics
switches into LiGaMD3. Correcting the generator and checking those switches
was necessary, but did not close the whole validation path.

A read-only self-audit of the local and remote checker found four reproducible
false-PASS cases. These are validation defects, not evidence that all four
occurred in actual submitted jobs:

| Synthetic input | Prior checker exit | Revised submission gate exit |
| --- | --- | --- |
| Valid Equil with matching explicit cMD source | 0 | 0 |
| Historical combination `ntf=2`, `barostat=2`, `irest=1`, `ntx=5` | 1 | 1 |
| Valid first `ntf`, conflicting duplicate later in the same group | 0 | 1 |
| Required `ntf` absent from `&cntrl`, present in a later group | 0 | 1 |
| Target temperature differs from explicit cMD source | 0 | 1 |
| Production `ntave=0` | 0 | 1 |

The prior checker already rejected the historical four-switch combination.
The new defects arise from first-match regex parsing beyond the group end,
presence-only temperature validation, and a stage-specific omission. The old
shell validator also duplicated parsing and gated the tutorial check on yet
another regex; its queue check could report absence on a failed query.

## Change

Use one strict parser/profile checker, called unconditionally by a thin shell
entry point. Distinguish fixed-only diagnostics from source-checked submission
validation. Keep required file/restart/launch checks without pretending they
prove provenance or scientific eligibility. Reject unknown stage names rather
than interpreting any non-Equil name as Production. Do not add another
campaign-specific monitor or scheduler retry script.

## Validation and unresolved risk

The synthetic regression suite and shell syntax check pass locally. No AMBER
job was run for this patch. No simulation input, source result, queue job, or
active automation was changed. The live checker is still the prior version
until a coordinated, reviewed deployment occurs.

Actual source inputs can omit inherited parameters. That is not permission to
assume defaults or rewrite scientific history. The source-evidence integration
must be resolved before deployment, as explained in
[the usage/deployment guide](../parameter-validation.md). Shared review-gate
freshness/binding, exact seed inheritance, and scheduler idempotency remain
separate action-layer checks; this patch is not an end-to-end submission
certification. Private campaign records and raw molecular data are excluded.
