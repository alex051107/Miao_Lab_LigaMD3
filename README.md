# Miao_Lab_LigaMD3

This repository contains the complete computational pipeline for preparing HSP90-ligand complexes for LiGaMD3 enhanced sampling molecular dynamics simulations on the UNC Longleaf cluster.

## LiGaMD3 parameter checks

For new Equilibration or Production inputs, start with the
[parameter validation guide](docs/parameter-validation.md). It explains the
stage-specific tutorial/lab profile, explicit cMD source requirement, and
read-only checks. Historical examples below are not current submission rules.
Passing a parameter check does not establish a bound seed, a valid sigma
boundary, scientific correctness, or permission to submit. The new gate is a
review candidate; live deployment and missing source settings remain separate.

## 📁 Repository Structure

*   **/new_systems/**: Contains the curated, error-free initial structures for CHARMM-GUI. Each subfolder contains strictly 3 files:
    *   `*.cif`: The native crystal structure downloaded from RCSB.
    *   `*_complex.pdb`: The cleaned protein-ligand complex with unified atom/chain numbering and occupancy fixed.
    *   `*_ligand_H.mol2`: Natively extracted ligand from the CIF with ideal protonation (via PyMOL `h_add`) and correct `Cl`/`Br` GAFF2 typing.
*   **/prepared_systems/**: Contains previously successful system setups (like 5OCI) that have already passed CHARMM-GUI and/or equilibration stages.
*   **/scripts/**: Contains Python automation scripts for processing CIFs, checking breaks, and verifying structures automatically via PyMOL.
*   **HSP90_LiGaMD3_Complete_Workflow.md**: The master human-readable guide detailing the entire pipeline from PDB download to LiGaMD3 production runs, including highly critical troubleshooting steps for CHARMM-GUI.
*   **.ai_instruction.md**: System instructions for AI agents working in this repository, strictly enforcing rules against RCSB ModelServer downloads and enforcing pure CIF extraction.

## 🚀 Key Pipeline Steps

1.  **Preparation (Local)**: Raw `.cif` → PyMOL in-place extraction (`cmd.extract`) → `complex.pdb` & `ligand_H.mol2` (must use scripts to fix halogen capitalization to `Cl`/`Br`).
2.  **CHARMM-GUI Solution Builder (Web)**: Upload the processed files, use Antechamber (gaff2 + AM1-BCC) for the ligand, configure waterbox (fit + 10Å), and select Amber outputs (FF14SB + TIP3P + GAFF2) with NVT eq and NPT prod.
3.  **Coordinate Sanitization (Longleaf)**: CRITICAL: Use `pdb4amber` on the output to homogenize the Amber atom numbering before touching anything else.
4.  **PyMOL Recalibration (Local)**: Analyze the `amber.pdb` to find target contact distances (e.g., ASP79 OD2) and map their absolute `atom_p` and relative `atom_l` indices for GaMD.
5.  **cMD & Equilibration (Longleaf)**: Follow the approved system-specific cMD duration and sigma-search plan. Generate new inputs from reviewed sources and run the parameter gate; do not hand-edit frozen inputs or treat a historical sigma range as a universal default.
6.  **Production (Longleaf)**: Launch 6 replicas of 100 ns production runs based on the optimal `sigma0P` equilibration frame.

## 🛑 Maintenance

*   Changes to the pipeline should be reflected in `HSP90_LiGaMD3_Complete_Workflow.md` and `.ai_instruction.md`.
*   A Github commit should be made daily to preserve workflow refinements and newly processed `.mol2`/`.pdb` structures.
