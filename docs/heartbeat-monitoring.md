# State-driven monitoring

A useful monitoring round identifies changed evidence and advances the next
authorized step. It should not rebuild every previous analysis or rewrite the
same classifier in a timestamped script.

## Round contract

1. Resolve ownership and current lineages from the campaign, not a broad glob.
2. Reconcile the complete managed manifest, receipts and unresolved targets with
   live job IDs/WorkDirs. Include older terminals with missing analysis and
   completed analyses that were never classified or recorded.
3. For pending jobs with no trajectory, report queued. For running jobs without
   new complete frames, reuse the previous snapshot. For new frames, analyze the
   complete captured prefix separately from terminal outputs. For unchanged
   validated terminal series, reuse results; a classifier-only change needs
   reclassification, not a new trajectory calculation.
4. Use one versioned paired classifier. Failures, incomplete terminal coverage
   and unknown scheduler state do not supply seed or departure evidence. A
   running prefix cannot become a final clean seed or a Production confirmation.
   The Equil stage may accept a complete captured prefix as upper-boundary
   evidence after its separate structural/source review. Retain per-replica differences.
5. Apply the campaign's authorized search/replication plan and the stage's seed
   and adjacent-boundary requirements. A pending scientific choice blocks that
   target, not independent work elsewhere. Do not re-ask settled choices without
   material new evidence affecting their basis.
6. Before a queue action, preserve scientific/source review, exact parameter and
   launch checks, review of the real artifacts, duplicates/withdrawn-plan checks,
   and a submission intent. Reconcile an ambiguous reply; never blindly retry.
7. Record each target as acting, waiting for a known job/analysis, handling a
   diagnosed fault, awaiting a specific decision, or finished. An omitted row is
   not a state. Report meaningful changes; no new evidence means no reanalysis.

This is an operator contract, not an autonomous scheduler. The accompanying
classifier handles screening, not sigma authorization or final scientific
confirmation. Pressure-policy ambiguity, membrane dissociation definitions,
sampling-window duration and exhausted experiment budgets need explicit
decisions; they cannot be resolved by adding a broad automatic fallback.
When consolidating prompts, preserve their still-applicable authorizations and
exact experiment limits in the maintained contract. Shortening a prompt must not
silently discard an approved exception or turn a permissive exception into a
mandatory action over an unresolved artifact review.

## Paired classifier

```sh
python3 _scripts/classify_paired.py \
  --distance JOB_DIR/dis-ligand.dat --rmsd JOB_DIR/rmsd-ligand.dat \
  --mdin JOB_DIR/md.in --stage equil --state COMPLETED --captured-frames 3000
```

The filenames and captured frame count are explicit and must come from the
actual registered analysis/trajectory. Distance and RMSD must contain exactly
two columns, contiguous frame IDs starting at 1, and the same number of finite
values. A bad row is an error, not something to skip. The tool reads `dt`,
`ntwx`, `nstlim` and the target topology to check the input and derive time;
there is no default 30.1 ns and no caller flag to skip parameter validation.

The current campaign screening rule uses both metrics: clean Equil requires
both maxima below 10 Å; 10–13 Å is edge and ≥13 Å excludes a seed. A departure
candidate requires both series to exceed 14 Å with at least 80% of each observed
post-onset segment above that threshold. Late, weak excursions remain
undetermined; a single post-onset observation has no measured sustained duration.
Support frame counts and durations are reported, not hidden. These are screening
conventions, not an independently established universal dissociation definition.

Production output is never called an Equil seed. Its first-ten-frame check is
per replica and remains incomplete until ten frames exist. A single passing
replica cannot certify a group. All classification output has
`scientifically_confirmed=false`; source identity and structural review remain
separate. Failed/stopped trajectories are retained as observations but cannot
supply current promotion evidence through this tool.

Use a reviewed Equil reference for exact replica or Production inheritance:

```sh
bash _scripts/validate_before_submit.sh JOB_DIR equil --reference-equil REVIEWED_EQUIL_DIR
LIGAMD3_REFERENCE_EQUIL=REVIEWED_EQUIL_DIR bash _scripts/safe_submit.sh JOB_DIR
```

The second command belongs to the existing cluster action layer, which is not
bundled here. It must still enforce its ownership, scientific review and
idempotency gates. This option checks the reference's fixed tutorial parameters,
the allowed per-stage input differences and exact topology/coordinate/boost
identity. It preserves the reference's already reviewed original cMD transition;
it does not retrospectively certify that transition or let an arbitrary
reference replace approval. First-time cMD-to-Equil preparation still requires
its own explicit source review.
