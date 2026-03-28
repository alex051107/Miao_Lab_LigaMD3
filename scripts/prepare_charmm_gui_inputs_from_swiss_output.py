#!/usr/bin/env python3
"""
直接使用 SWISS-MODEL 输出中自带的 ligand 生成一套独立的 CHARMM-GUI 输入。

这是一条单独的对照 workflow，不覆盖现有的 `charmm_gui_ready/`。

输入:
  - new_systems/[PDB_ID]/[PDB_ID]_swissmodel_output.pdb
    或 [PDB_ID]_swiss_prepared_model.pdb

输出:
  - new_systems/[PDB_ID]/charmm_gui_ready_from_swiss_output/
    - [PDB_ID]_swissmodel_output.pdb
    - [PDB_ID]_complex.pdb
    - [PDB_ID]_ligand_H.mol2

逻辑:
  1. 从 SWISS 输出里取蛋白 chain A
  2. 从同一个 SWISS 输出里直接提取目标 ligand
  3. 对 ligand 执行 h_add
  4. 统一 ligand 的 chain/resi 为 A/301
  5. 导出新的 complex.pdb 和 ligand_H.mol2
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEW_SYSTEMS_DIR = PROJECT_ROOT / "new_systems"
PYMOL_BIN = Path("/Applications/PyMOL.app/Contents/MacOS/PyMOL")

LIGAND_MAP = {
    "4FKO": "20K",
    "4FKP": "LS5",
    "4FKR": "45K",
    "4FKS": "46K",
    "4FKT": "48K",
    "4FKU": "60K",
    "4FKV": "61K",
    "4FKW": "62K",
}


def quote_pymol_path(path: Path) -> str:
    return '"' + str(path) + '"'


def get_system_dir(pdb_id: str) -> Path:
    return NEW_SYSTEMS_DIR / pdb_id


def get_swiss_output_path(pdb_id: str) -> Path | None:
    system_dir = get_system_dir(pdb_id)
    candidates = [
        system_dir / f"{pdb_id}_swissmodel_output.pdb",
        system_dir / f"{pdb_id}_swiss_prepared_model.pdb",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def build_pymol_script(
    ligand_name: str,
    swiss_path: Path,
    final_complex_path: Path,
    complex_path: Path,
    ligand_mol2_path: Path,
) -> str:
    return f"""reinitialize

load {quote_pymol_path(swiss_path)}, swiss_raw

create swiss_protein, swiss_raw and polymer.protein and chain A
create ligand_obj, swiss_raw and resn {ligand_name} and not polymer.protein

remove swiss_protein and solvent
remove ligand_obj and solvent
remove ligand_obj and resn HOH+WAT+ACE+NME+NH2+GOL+ACT+NA+CL+K+MG+CA+ZN

h_add ligand_obj
select ligand_all, ligand_obj
alter ligand_all, chain='A'
alter ligand_all, resi='301'
alter ligand_all, segi=''
sort

create complex, swiss_protein or ligand_all
remove complex and solvent
remove complex and resn HOH+WAT+ACE+NME+NH2+GOL+ACT+NA+CL+K+MG+CA+ZN

cmd.save({quote_pymol_path(Path(final_complex_path.name))}, "complex", format="pdb")
cmd.save({quote_pymol_path(Path(complex_path.name))}, "complex", format="pdb")
cmd.save({quote_pymol_path(Path(ligand_mol2_path.name))}, "ligand_all", format="mol2")

quit
"""


def run_pymol_script_in_dir(script_text: str, workdir: Path) -> None:
    if not PYMOL_BIN.exists():
        raise FileNotFoundError(f"找不到 PyMOL 可执行文件: {PYMOL_BIN}")

    with tempfile.NamedTemporaryFile("w", suffix=".pml", delete=False) as handle:
        handle.write(script_text)
        script_path = Path(handle.name)

    try:
        subprocess.run(
            [str(PYMOL_BIN), "-cq", str(script_path)],
            check=True,
            cwd=str(workdir),
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


def validate_outputs(
    pdb_id: str,
    final_complex_path: Path,
    complex_path: Path,
    ligand_mol2_path: Path,
    ligand_name: str,
) -> None:
    banned = {"ACE", "NME", "HOH", "WAT", "GOL", "ACT", "NA", "CL", "K", "MG", "CA", "ZN"}

    final_hets = collect_het_residues(final_complex_path)
    complex_hets = collect_het_residues(complex_path)

    for label, hets in [("final_complex", final_hets), ("complex", complex_hets)]:
        bad = [x for x in hets if x[0] in banned]
        target = [x for x in hets if x[0] == ligand_name]
        if bad:
            raise RuntimeError(f"{pdb_id}: {label} 中仍有不应保留的 HETATM: {bad}")
        if len(target) != 1:
            raise RuntimeError(f"{pdb_id}: {label} 中目标配体数量异常: {target}")

    mol2_text = ligand_mol2_path.read_text(errors="replace")
    if "@<TRIPOS>MOLECULE" not in mol2_text or "@<TRIPOS>ATOM" not in mol2_text:
        raise RuntimeError(f"{pdb_id}: ligand_H.mol2 格式不完整")


def prepare_one_system(pdb_id: str) -> None:
    pdb_id = pdb_id.upper()
    ligand_name = LIGAND_MAP.get(pdb_id)
    if not ligand_name:
        raise ValueError(f"未配置 {pdb_id} 的配体名称")

    system_dir = get_system_dir(pdb_id)
    if not system_dir.is_dir():
        raise FileNotFoundError(f"找不到体系目录: {system_dir}")

    swiss_path = get_swiss_output_path(pdb_id)
    if swiss_path is None:
        raise FileNotFoundError(f"{pdb_id} 缺少 SWISS 输出文件")

    alt_ready_dir = system_dir / "charmm_gui_ready_from_swiss_output"
    alt_ready_dir.mkdir(parents=True, exist_ok=True)

    final_complex_path = alt_ready_dir / f"{pdb_id}_final_complex_from_swiss_output.pdb"
    complex_path = alt_ready_dir / f"{pdb_id}_complex.pdb"
    ligand_mol2_path = alt_ready_dir / f"{pdb_id}_ligand_H.mol2"

    script_text = build_pymol_script(
        ligand_name=ligand_name,
        swiss_path=swiss_path,
        final_complex_path=final_complex_path,
        complex_path=complex_path,
        ligand_mol2_path=ligand_mol2_path,
    )
    run_pymol_script_in_dir(script_text, alt_ready_dir)

    if not final_complex_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 final_complex 文件")
    if not complex_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 complex 文件")
    if not ligand_mol2_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 ligand_H.mol2 文件")

    validate_outputs(pdb_id, final_complex_path, complex_path, ligand_mol2_path, ligand_name)

    shutil.copy2(swiss_path, alt_ready_dir / swiss_path.name)

    print(f"✅ {pdb_id}")
    print(f"   SWISS source: {swiss_path}")
    print(f"   Alt folder: {alt_ready_dir}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    args = [arg.upper() for arg in sys.argv[1:]]
    if args == ["ALL"]:
        pdb_ids = sorted(LIGAND_MAP)
    else:
        pdb_ids = args

    for pdb_id in pdb_ids:
        prepare_one_system(pdb_id)


if __name__ == "__main__":
    main()
