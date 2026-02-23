---
description: How to prepare ligand MOL2 and complex PDB structures for CHARMM-GUI using PyMOL
---

# Ligand Preparation for CHARMM-GUI

This workflow standardizes the preparation of protein-ligand crystal structures (CIF/PDB) into clean, Antechamber-compatible files for CHARMM-GUI. 

## The Core Problem
PyMOL's native `cmd.h_add` fails silently or corrupts the topology of non-standard ligands extracted directly from CIF/PDB files because those formats lack explicit bond orders (e.g. single/double/aromatic bonds).
* **Symptom 1:** Zero hydrogens get added.
* **Symptom 2:** PyMOL exports `C.2` atom types instead of `C.ar` for aromatic rings, causing CHARMM-GUI Antechamber to reject the MOL2 file. CHARMM-GUI then falls back to generating a SMILES string, which completely changes the atom numbering (e.g., `O1, O2` instead of the original crystal `C7, O11`), resulting in a fatal `Mismatch in Ligand Atom Order` error.

## The Standard Execution Pipeline

To bypass these issues, the workflow **must** automatically execute the following 4-step process via a Python/PyMOL script (`process_all.py`):

### 1. Structure Cleanup & Altloc Detection
* Load the `.cif` or `.pdb`.
* Remove `solvent` and common ions (`NA+CL+K+MG+CA+ZN+FE+MN+CU+NI+CO`).
* Detect if the ligand has multiple alternate locations (Altloc overlap). If true, strictly keep only the primary conformation and delete the rest to avoid duplicate atoms.

### 2. Universal RCSB MOL2 Download
* **NEVER** extract the ligand directly from the CIF.
* **ALWAYS** download the official, ideal `.mol2` file directly from the RCSB ModelServer API:
  `https://models.rcsb.org/v1/<pdb_id>/ligand?auth_asym_id=<chain>&auth_seq_id=<resi>&encoding=mol2`
* This raw MOL2 contains the perfect Tripos bond topology (e.g., `C.ar`, `N.am`) but lacks hydrogens.

### 3. Topology Extraction & PyMOL Hydrogenation
* Read the raw ModelServer `.mol2` text file using native Python to extract and memorize a mapping of every atom name to its perfect Tripos type (e.g., `C1` -> `C.ar`, `N2` -> `N.am`).
* Load the raw MOL2 into PyMOL.
* Execute `cmd.h_add()` — this will succeed because the bond orders are present.
* Align the residue name, chain ID, and residue sequence number to match the original crystal complex.
* Save the output as `[PDBID]_ligand_H.mol2`.

### 4. Topology Patching (The "C.ar" Fix)
* PyMOL will corrupt the saved file by writing aromatic carbons as `C.2`. 
* Use native Python to post-process the saved `[PDBID]_ligand_H.mol2`.
* Inject the memorized Tripos types from Step 3 back into the respective lines in the `@<TRIPOS>ATOM` block.
* Save the finalized, perfect `.mol2` file and an optional `.sdf` file.
* Delete the intermediate raw MOL2 file.

## Execution Requirements
* All Python scripts controlling PyMOL should be executed in headless mode: `/Applications/PyMOL.app/Contents/MacOS/PyMOL -cq <script.py>`
* Verify structural outputs with a secondary script confirming the exact match between the complex PDB `HETATM` block and the MOL2 residue identifiers.
