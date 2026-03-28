#!/usr/bin/env python3
"""
为完整的 HIV protease dimer 体系直接准备 CHARMM-GUI 输入。

特点:
  - 不走 AlphaFold / SWISS-MODEL
  - 直接从 RCSB 下载原始 PDB 与 CIF
  - 保留两条蛋白链 A/B
  - 将目标配体统一改为链 C，但保留原始残基号
  - 生成每个体系自己的 PyMOL 脚本与 charmm_gui_ready/ 输出

输出目录:
  new_systems/[PDB_ID]/
    - [PDB_ID].pdb
    - [PDB_ID].cif
    - prepare_[PDB_ID]_hiv_dimer_charmm_gui.pml
    - [PDB_ID]_final_complex.pdb
    - charmm_gui_ready/
        - [PDB_ID].cif
        - [PDB_ID]_complex.pdb
        - [PDB_ID]_ligand_H.mol2
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEW_SYSTEMS_DIR = PROJECT_ROOT / "new_systems"
PYMOL_BIN = Path("/Applications/PyMOL.app/Contents/MacOS/PyMOL")

HIV_DIMER_LIGANDS = {
    "3EKX": "1UN",
    "3EKV": "478",
    "1QBS": "DMP",
    "1HXW": "RIT",
    "1HIV": "1ZK",
    "1EC1": "BEE",
    "1EBZ": "BEC",
    "1EBY": "BEB",
    "1D4I": "BEG",
    "1D4H": "BEH",
}

# CHARMM-GUI can misclassify some three-letter ligand residue names as built-in lipid types.
# Keep the native crystal ligand name for extraction, but rename the exported ligand to a safe alias.
OUTPUT_LIGAND_NAMES = {
    "1D4H": "H4X",
}

RCSB_PDB_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"
RCSB_CIF_URL = "https://files.rcsb.org/download/{pdb_id}.cif"


def quote_pymol_path(path: Path) -> str:
    return '"' + str(path) + '"'


def download_text(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read()
    dest.write_bytes(data)


def ensure_raw_files(pdb_id: str, system_dir: Path) -> tuple[Path, Path]:
    pdb_path = system_dir / f"{pdb_id}.pdb"
    cif_path = system_dir / f"{pdb_id}.cif"

    if not pdb_path.exists():
        download_text(RCSB_PDB_URL.format(pdb_id=pdb_id), pdb_path)
    if not cif_path.exists():
        download_text(RCSB_CIF_URL.format(pdb_id=pdb_id), cif_path)

    return pdb_path, cif_path


def get_original_ligand_id(pdb_path: Path, ligand_name: str) -> tuple[str, str]:
    hits = []
    with pdb_path.open() as handle:
        for line in handle:
            if not line.startswith("HETATM"):
                continue
            resn = line[17:20].strip()
            if resn != ligand_name:
                continue
            chain = line[21].strip() or "_"
            resi = line[22:26].strip()
            key = (chain, resi)
            if key not in hits:
                hits.append(key)

    if len(hits) != 1:
        raise RuntimeError(f"{pdb_path.stem}: 无法唯一确定 {ligand_name} 的原始链/残基号: {hits}")

    return hits[0]


def build_pymol_script(
    ligand_name: str,
    output_ligand_name: str,
    ligand_chain: str,
    ligand_resi: str,
    cif_path: Path,
    final_complex_path: Path,
    complex_path: Path,
    ligand_mol2_path: Path,
) -> str:
    return f"""reinitialize

load {quote_pymol_path(cif_path)}, complex

remove complex and solvent
remove complex and resn HOH+WAT+ACE+NME+NH2+ACT+GOL+EDO+DMS+SO4+PO4+MES+TRS+NA+CL+K+MG+CA+ZN
remove complex and not ((polymer.protein and (chain A or chain B)) or (resn {ligand_name} and chain {ligand_chain} and resi {ligand_resi}))

cmd.extract("ligand", "complex and resn {ligand_name} and chain {ligand_chain} and resi {ligand_resi}")
h_add ligand
select ligand, ligand

alter complex and polymer.protein and chain A, chain='A'
alter complex and polymer.protein and chain B, chain='B'
alter ligand, resn='{output_ligand_name}'
alter ligand, chain='C'
alter ligand, resi='{ligand_resi}'
alter ligand, segi=''
sort

cmd.copy_to("complex", "ligand", zoom=0, quiet=0)

cmd.save({quote_pymol_path(final_complex_path)}, "complex", format="pdb")
cmd.save({quote_pymol_path(complex_path)}, "complex", format="pdb")
cmd.save({quote_pymol_path(ligand_mol2_path)}, "ligand", format="mol2")

quit
"""


def run_pymol_script(script_text: str) -> None:
    if not PYMOL_BIN.exists():
        raise FileNotFoundError(f"找不到 PyMOL 可执行文件: {PYMOL_BIN}")

    with tempfile.NamedTemporaryFile("w", suffix=".pml", delete=False) as handle:
        handle.write(script_text)
        script_path = Path(handle.name)

    try:
        subprocess.run(
            [str(PYMOL_BIN), "-cq", str(script_path)],
            check=True,
            cwd=str(PROJECT_ROOT),
        )
    finally:
        script_path.unlink(missing_ok=True)


def collect_het_residues(pdb_path: Path):
    het_res = []
    for line in pdb_path.read_text(errors="replace").splitlines():
        if line.startswith("HETATM"):
            resn = line[17:20].strip()
            chain = line[21].strip()
            resi = line[22:26].strip()
            key = (resn, chain, resi)
            if key not in het_res:
                het_res.append(key)
    return het_res


def collect_protein_chains(pdb_path: Path):
    chains = set()
    for line in pdb_path.read_text(errors="replace").splitlines():
        if line.startswith("ATOM"):
            chains.add(line[21].strip() or "_")
    return sorted(chains)


def validate_outputs(
    pdb_id: str,
    complex_path: Path,
    ligand_mol2_path: Path,
    output_ligand_name: str,
    ligand_resi: str,
) -> None:
    protein_chains = collect_protein_chains(complex_path)
    if protein_chains != ["A", "B"]:
        raise RuntimeError(f"{pdb_id}: 蛋白链不是 A/B: {protein_chains}")

    hets = collect_het_residues(complex_path)
    target = [x for x in hets if x[0] == output_ligand_name]
    if len(target) != 1:
        raise RuntimeError(f"{pdb_id}: 目标配体数量异常: {target}")

    ligand = target[0]
    if ligand[1] != "C":
        raise RuntimeError(f"{pdb_id}: 目标配体链名不是 C: {ligand}")
    if ligand[2] != ligand_resi:
        raise RuntimeError(f"{pdb_id}: 目标配体残基号不是原始值 {ligand_resi}: {ligand}")

    mol2_text = ligand_mol2_path.read_text(errors="replace")
    if "@<TRIPOS>MOLECULE" not in mol2_text or "@<TRIPOS>ATOM" not in mol2_text:
        raise RuntimeError(f"{pdb_id}: ligand_H.mol2 格式不完整")


def prepare_one_system(pdb_id: str) -> None:
    pdb_id = pdb_id.upper()
    ligand_name = HIV_DIMER_LIGANDS.get(pdb_id)
    if not ligand_name:
        raise ValueError(f"未配置 {pdb_id} 的目标配体")
    output_ligand_name = OUTPUT_LIGAND_NAMES.get(pdb_id, ligand_name)

    system_dir = NEW_SYSTEMS_DIR / pdb_id
    system_dir.mkdir(parents=True, exist_ok=True)

    pdb_path, cif_path = ensure_raw_files(pdb_id, system_dir)
    ligand_chain, ligand_resi = get_original_ligand_id(pdb_path, ligand_name)

    local_ready_dir = system_dir / "charmm_gui_ready"
    local_ready_dir.mkdir(parents=True, exist_ok=True)

    final_complex_path = system_dir / f"{pdb_id}_final_complex.pdb"
    complex_path = local_ready_dir / f"{pdb_id}_complex.pdb"
    ligand_mol2_path = local_ready_dir / f"{pdb_id}_ligand_H.mol2"
    pml_path = system_dir / f"prepare_{pdb_id}_hiv_dimer_charmm_gui.pml"

    script_text = build_pymol_script(
        ligand_name=ligand_name,
        output_ligand_name=output_ligand_name,
        ligand_chain=ligand_chain,
        ligand_resi=ligand_resi,
        cif_path=cif_path,
        final_complex_path=final_complex_path,
        complex_path=complex_path,
        ligand_mol2_path=ligand_mol2_path,
    )
    pml_path.write_text(script_text)
    run_pymol_script(script_text)

    if not final_complex_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 final_complex")
    if not complex_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 complex.pdb")
    if not ligand_mol2_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 ligand_H.mol2")

    validate_outputs(pdb_id, complex_path, ligand_mol2_path, output_ligand_name, ligand_resi)

    shutil.copy2(cif_path, local_ready_dir / cif_path.name)

    print(f"✅ {pdb_id}")
    print(f"   Native ligand: {ligand_name}")
    print(f"   Output ligand: {output_ligand_name}")
    print(f"   Original ligand id: {ligand_chain} {ligand_resi}")
    print(f"   Raw PDB: {pdb_path}")
    print(f"   Raw CIF: {cif_path}")
    print(f"   CHARMM-GUI folder: {local_ready_dir}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    args = [arg.upper() for arg in sys.argv[1:]]
    if args == ["ALL"]:
        pdb_ids = list(HIV_DIMER_LIGANDS)
    else:
        pdb_ids = args

    for pdb_id in pdb_ids:
        prepare_one_system(pdb_id)


if __name__ == "__main__":
    main()
