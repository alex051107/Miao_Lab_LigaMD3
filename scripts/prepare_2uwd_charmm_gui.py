#!/usr/bin/env python3
"""Prepare a corrected CHARMM-GUI input set for 2UWD.

This follows the older, more stable ligand workflow:
1. Keep the current coordinates from the locally prepared `2UWD_ligand_H.mol2`
2. Download the RCSB ModelServer MOL2 for the native ligand topology
3. Patch the local MOL2 heavy-atom Tripos types with the ModelServer types
4. Mirror the final files into `new_systems/2UWD/charmm_gui_ready/`
"""

from __future__ import annotations

import re
import shutil
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path("/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures")
SYSTEM_DIR = PROJECT_ROOT / "new_systems" / "2UWD"
READY_DIR = SYSTEM_DIR / "charmm_gui_ready"

COMPLEX_PDB = SYSTEM_DIR / "2UWD_complex.pdb"
SOURCE_MOL2 = SYSTEM_DIR / "2UWD_ligand_H.mol2"
CIF_FILE = SYSTEM_DIR / "2UWD.cif"
RAW_MOL2 = READY_DIR / "2UWD_downloaded_ligand.mol2"
FIXED_MOL2 = READY_DIR / "2UWD_ligand_H.mol2"
FIXED_MOL2_NOH = READY_DIR / "2UWD_ligand_noH.mol2"
READY_COMPLEX = READY_DIR / "2UWD_complex.pdb"
READY_CIF = READY_DIR / "2UWD.cif"

MODEL_SERVER_URL = (
    "https://models.rcsb.org/v1/2uwd/ligand"
    "?auth_asym_id=A&auth_seq_id=1228&encoding=mol2"
)


def parse_mol2_types(path: Path) -> dict[str, str]:
    types: dict[str, str] = {}
    in_atoms = False
    for line in path.read_text().splitlines():
        if line.startswith("@<TRIPOS>ATOM"):
            in_atoms = True
            continue
        if line.startswith("@<TRIPOS>BOND"):
            break
        if in_atoms and line.strip():
            parts = line.split()
            if len(parts) >= 6:
                types[parts[1]] = parts[5]
    return types


def patch_mol2_types(template_types: dict[str, str], source_path: Path, out_path: Path) -> list[str]:
    changed: list[str] = []
    patched_lines: list[str] = []
    in_atoms = False
    for line in source_path.read_text().splitlines(keepends=True):
        if line.startswith("@<TRIPOS>ATOM"):
            in_atoms = True
            patched_lines.append(line)
            continue
        if line.startswith("@<TRIPOS>BOND"):
            in_atoms = False
            patched_lines.append(line)
            continue
        if in_atoms and line.strip():
            parts = line.split()
            if len(parts) >= 6:
                atom_name = parts[1]
                old_type = parts[5]
                new_type = template_types.get(atom_name)
                if new_type and new_type != old_type:
                    pattern = (
                        r"^(\s*\S+\s+" + re.escape(atom_name) +
                        r"\s+[-.\d]+\s+[-.\d]+\s+[-.\d]+\s+)\S+(.*)$"
                    )
                    line = re.sub(pattern, r"\g<1>" + new_type + r"\g<2>", line)
                    changed.append(f"{atom_name}: {old_type} -> {new_type}")
        patched_lines.append(line)
    out_path.write_text("".join(patched_lines))
    return changed


def strip_hydrogens_from_mol2(source_path: Path, out_path: Path) -> None:
    lines = source_path.read_text().splitlines()
    out_lines: list[str] = []
    atom_lines: list[str] = []
    bond_lines: list[str] = []
    atom_map: dict[int, int] = {}
    atom_is_h: dict[int, bool] = {}

    section = None
    for line in lines:
        if line.startswith("@<TRIPOS>ATOM"):
            section = "ATOM"
            out_lines.append(line)
            continue
        if line.startswith("@<TRIPOS>BOND"):
            section = "BOND"
            continue
        if line.startswith("@<TRIPOS>SUBSTRUCTURE"):
            section = "SUBSTRUCTURE"
            out_lines.append("@<TRIPOS>BOND")
            out_lines.extend(bond_lines)
            out_lines.append(line)
            continue

        if section == "ATOM" and line.strip():
            parts = line.split()
            old_idx = int(parts[0])
            atom_name = parts[1]
            atom_type = parts[5]
            is_h = atom_type == "H" or atom_name.strip().startswith("H")
            atom_is_h[old_idx] = is_h
            if not is_h:
                new_idx = len(atom_lines) + 1
                atom_map[old_idx] = new_idx
                parts[0] = str(new_idx)
                atom_lines.append("\t".join(parts))
            continue

        if section == "BOND" and line.strip():
            parts = line.split()
            old_a = int(parts[1])
            old_b = int(parts[2])
            if atom_is_h.get(old_a, False) or atom_is_h.get(old_b, False):
                continue
            parts[0] = str(len(bond_lines) + 1)
            parts[1] = str(atom_map[old_a])
            parts[2] = str(atom_map[old_b])
            bond_lines.append(" ".join(parts))
            continue

        if section == "SUBSTRUCTURE" or section is None:
            out_lines.append(line)

    final_lines: list[str] = []
    molecule_header_seen = False
    counts_updated = False
    i = 0
    while i < len(out_lines):
        line = out_lines[i]
        final_lines.append(line)
        if line.startswith("@<TRIPOS>MOLECULE"):
            molecule_header_seen = True
        elif molecule_header_seen and not counts_updated and line.strip():
            # line after molecule name is atom/bond/substructure counts
            if i + 2 < len(out_lines):
                final_lines.append(f"{len(atom_lines)} {len(bond_lines)} 1")
                final_lines.append(out_lines[i + 2])
                final_lines.append(out_lines[i + 3])
                i += 3
                counts_updated = True
        elif line.startswith("@<TRIPOS>ATOM"):
            final_lines.extend(atom_lines)
        i += 1

    out_path.write_text("\n".join(final_lines) + "\n")


def main() -> None:
    READY_DIR.mkdir(exist_ok=True)

    urllib.request.urlretrieve(MODEL_SERVER_URL, RAW_MOL2)
    true_types = parse_mol2_types(RAW_MOL2)
    changed = patch_mol2_types(true_types, SOURCE_MOL2, FIXED_MOL2)
    strip_hydrogens_from_mol2(FIXED_MOL2, FIXED_MOL2_NOH)

    shutil.copy2(COMPLEX_PDB, READY_COMPLEX)
    shutil.copy2(CIF_FILE, READY_CIF)

    print("Prepared 2UWD CHARMM-GUI input set:")
    print(f"  {READY_COMPLEX}")
    print(f"  {FIXED_MOL2}")
    print(f"  {FIXED_MOL2_NOH}")
    print(f"  {READY_CIF}")
    if changed:
        print("Patched atom types:")
        for item in changed:
            print(f"  - {item}")
    else:
        print("No atom-type changes were needed.")


if __name__ == "__main__":
    main()
