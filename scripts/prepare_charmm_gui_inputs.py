#!/usr/bin/env python3
"""
从 SWISS-MODEL 输出自动生成 CHARMM-GUI 需要的输入文件。

当前脚本采用的逻辑，尽量贴近组里原来的 PyMOL 手工 workflow：

1. 读取 SWISS 输出，只保留补全后的蛋白链 A
2. 读取原始实验结构，优先使用原始 CIF 作为参考
3. 将 SWISS 蛋白对齐到原始实验结构的蛋白链 A
4. 从原始实验结构里复制目标配体到同一个 complex object
5. 在这个完整 complex object 上执行去水、去无关小分子、给 ligand `h_add`
6. 直接从该 complex object 导出 `*_complex.pdb` 和 `*_ligand_H.mol2`

为什么优先用 CIF:
  - 原始 mmCIF 比 PDB 更容易保留配体化学拓扑信息
  - 对需要导出 mol2 的配体更稳，能减少 PyMOL 自行猜测键型导致的
    `antechamber` 价态报错

需要的输入文件:
  1. new_systems/[PDB_ID]/[PDB_ID]_swissmodel_output.pdb
     或 [PDB_ID]_swiss_prepared_model.pdb
  2. new_systems/[PDB_ID]/[PDB_ID].cif
     - 优先作为配体来源与参考结构
  3. 如果缺少 CIF，则回退到 new_systems/[PDB_ID]/[PDB_ID].pdb

输出:
  1. new_systems/[PDB_ID]/[PDB_ID]_final_complex.pdb
     - SWISS 补全蛋白 + 从原始实验结构复制回来的目标配体

  2. new_systems/[PDB_ID]/charmm_gui_ready/
     - [PDB_ID].cif
     - [PDB_ID]_complex.pdb
     - [PDB_ID]_ligand_H.mol2

  3. charmm_gui_ready/[PDB_ID]/
     - 与各体系子目录内 `charmm_gui_ready/` 相同的镜像副本，便于批量查看

依赖:
  - macOS PyMOL: /Applications/PyMOL.app/Contents/MacOS/PyMOL

用法:
  python3 scripts/prepare_charmm_gui_inputs.py 4FKO
  python3 scripts/prepare_charmm_gui_inputs.py 4FKO 4FKP 4FKR
  python3 scripts/prepare_charmm_gui_inputs.py all
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEW_SYSTEMS_DIR = PROJECT_ROOT / "new_systems"
CHARMM_GUI_READY_DIR = PROJECT_ROOT / "charmm_gui_ready"
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


def get_reference_structure_path(pdb_id: str) -> Path:
    system_dir = get_system_dir(pdb_id)
    candidates = [
        system_dir / f"{pdb_id}.cif",
        system_dir / f"{pdb_id}.pdb",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"{pdb_id} 缺少原始参考结构文件（.cif 或 .pdb）")


def get_original_pdb_path(pdb_id: str) -> Path:
    path = get_system_dir(pdb_id) / f"{pdb_id}.pdb"
    if not path.exists():
        raise FileNotFoundError(f"{pdb_id} 缺少原始 PDB 文件，无法判定目标配体副本")
    return path


def choose_target_ligand_instance(pdb_id: str, ligand_name: str) -> tuple[str, str]:
    """Choose the ligand copy closest to protein chain A in the native crystal PDB."""
    pdb_path = get_original_pdb_path(pdb_id)
    protein_atoms: list[tuple[float, float, float]] = []
    ligand_atoms: dict[tuple[str, str], list[tuple[float, float, float]]] = {}

    for line in pdb_path.read_text(errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        x = float(line[30:38])
        y = float(line[38:46])
        z = float(line[46:54])
        chain = line[21].strip() or "_"
        resi = line[22:26].strip()
        resn = line[17:20].strip()

        if line.startswith("ATOM") and chain == "A":
            protein_atoms.append((x, y, z))
            continue

        if line.startswith("HETATM") and resn == ligand_name and chain == "A":
            ligand_atoms.setdefault((chain, resi), []).append((x, y, z))

    if not ligand_atoms:
        raise RuntimeError(f"{pdb_id}: 原始 PDB 中未找到 {ligand_name} 的链 A 配体")

    if len(ligand_atoms) == 1:
        return next(iter(ligand_atoms))

    def min_distance(coords: list[tuple[float, float, float]]) -> float:
        best = float("inf")
        for x1, y1, z1 in coords:
            for x2, y2, z2 in protein_atoms:
                dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                if dist < best:
                    best = dist
        return best

    ranked = sorted(
        ((min_distance(coords), chain, resi) for (chain, resi), coords in ligand_atoms.items()),
        key=lambda item: (item[0], item[2]),
    )
    _, chain, resi = ranked[0]
    return chain, resi


def build_pymol_script(
    pdb_id: str,
    ligand_name: str,
    ligand_chain: str,
    ligand_resi: str,
    swiss_path: Path,
    reference_structure: Path,
    final_complex_path: Path,
    complex_path: Path,
    ligand_mol2_path: Path,
) -> str:
    return f"""reinitialize

load {quote_pymol_path(swiss_path)}, swiss_raw
load {quote_pymol_path(reference_structure)}, original_raw

create swiss_protein, swiss_raw and polymer.protein and chain A
align swiss_protein and name CA, original_raw and polymer.protein and chain A and name CA

create complex, swiss_protein
create ligand_ref, original_raw and resn {ligand_name} and chain {ligand_chain} and resi {ligand_resi}
cmd.copy_to("complex", "ligand_ref", zoom=0, quiet=0)

remove complex and solvent
remove complex and resn HOH+WAT+ACE+NME+NH2+GOL+ACT+NA+CL+K+MG+CA+ZN

select ligand, complex and resn {ligand_name} and resi {ligand_resi}
h_add ligand
select ligand, complex and resn {ligand_name} and resi {ligand_resi}
alter ligand, chain='A'
alter ligand, resi='{ligand_resi}'
alter ligand, segi=''
sort

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

    original_cif = system_dir / f"{pdb_id}.cif"
    reference_structure = get_reference_structure_path(pdb_id)
    ligand_chain, ligand_resi = choose_target_ligand_instance(pdb_id, ligand_name)
    final_complex_path = system_dir / f"{pdb_id}_final_complex.pdb"

    local_ready_dir = system_dir / "charmm_gui_ready"
    local_ready_dir.mkdir(parents=True, exist_ok=True)
    summary_ready_dir = CHARMM_GUI_READY_DIR / pdb_id
    summary_ready_dir.mkdir(parents=True, exist_ok=True)

    complex_path = local_ready_dir / f"{pdb_id}_complex.pdb"
    ligand_mol2_path = local_ready_dir / f"{pdb_id}_ligand_H.mol2"

    script_text = build_pymol_script(
        pdb_id=pdb_id,
        ligand_name=ligand_name,
        ligand_chain=ligand_chain,
        ligand_resi=ligand_resi,
        swiss_path=swiss_path,
        reference_structure=reference_structure,
        final_complex_path=final_complex_path,
        complex_path=complex_path,
        ligand_mol2_path=ligand_mol2_path,
    )
    run_pymol_script(script_text)

    if not final_complex_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 final_complex 文件")
    if not complex_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 CHARMM-GUI complex 文件")
    if not ligand_mol2_path.exists():
        raise RuntimeError(f"{pdb_id}: 未生成 ligand_H.mol2 文件")

    validate_outputs(pdb_id, final_complex_path, complex_path, ligand_mol2_path, ligand_name, ligand_resi)

    if original_cif.exists():
        shutil.copy2(original_cif, local_ready_dir / original_cif.name)

    for path in [complex_path, ligand_mol2_path]:
        shutil.copy2(path, summary_ready_dir / path.name)
    if original_cif.exists():
        shutil.copy2(original_cif, summary_ready_dir / original_cif.name)

    print(f"✅ {pdb_id}")
    print(f"   SWISS: {swiss_path}")
    print(f"   Reference: {reference_structure}")
    print(f"   Selected ligand copy: {ligand_name} {ligand_chain} {ligand_resi}")
    print(f"   Final complex: {final_complex_path}")
    print(f"   Local CHARMM-GUI folder: {local_ready_dir}")
    print(f"   Summary CHARMM-GUI folder: {summary_ready_dir}")


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
    ligand_resi: str,
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
        if target[0][2] != ligand_resi:
            raise RuntimeError(f"{pdb_id}: {label} 中目标配体残基号应为 {ligand_resi}，实际为 {target[0]}")

    mol2_text = ligand_mol2_path.read_text(errors="replace")
    if "@<TRIPOS>MOLECULE" not in mol2_text or "@<TRIPOS>ATOM" not in mol2_text:
        raise RuntimeError(f"{pdb_id}: ligand_H.mol2 格式不完整")


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
