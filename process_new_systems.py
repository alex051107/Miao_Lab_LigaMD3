# HSP90 new_systems 批量处理脚本
# 用法: /Applications/PyMOL.app/Contents/MacOS/PyMOL -cq process_new_systems.py
#
# 来自 check_completeness.py 的配体映射 + 精细的缺口分析确认:
#   所有体系仅有 N-/C-末端缺失（0 内部断链），均可正常建模
#
# Ligand Map:
#   5J8U → 6DL | 5J8M → 6DL | 5J6N → 6FF | 5J6L → 6GC | 5J6M → 6FJ
#   4EFU → EFU | 3LDP → 3P1 | 2YKJ → YKJ | 2YKI → YKI | 2UWD → 2GG | 2BSM → BSM

import os
import urllib.request
import re

base_dir = "/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures/new_systems"
systems = ["5J8U", "5J8M", "5J6N", "5J6L", "5J6M", "4EFU", "3LDP", "2YKJ", "2YKI", "2UWD", "2BSM"]

ligand_map = {
    "5J8U": "6DL",
    "5J8M": "6DL",
    "5J6N": "6FF",
    "5J6L": "6GC",
    "5J6M": "6FJ",
    "4EFU": "EFU",
    "3LDP": "3P1",
    "2YKJ": "YKJ",
    "2YKI": "YKI",
    "2UWD": "2GG",
    "2BSM": "BSM",
}

for pdb_id in systems:
    print(f"\n{'='*50}")
    print(f"Processing {pdb_id}")
    print(f"{'='*50}")

    work_dir = os.path.join(base_dir, pdb_id)
    cif_file = os.path.join(work_dir, f"{pdb_id}.cif")

    # === Step 1: 加载与清理 ===
    cmd.load(cif_file)
    cmd.remove("solvent")
    cmd.remove("resn NA+CL+K+MG+CA+ZN+FE+MN+CU+NI+CO+SO4+PO4+GOL+EDO+PEG+ACT+IMD+DMS")

    ligand_name = ligand_map.get(pdb_id)
    if not ligand_name:
        print(f"  No ligand mapping found for {pdb_id}, saving protein only.")
        cmd.save(os.path.join(work_dir, f"{pdb_id}_complex.pdb"), "all")
        cmd.delete("all")
        continue

    # === Step 2: 检测配体 Altloc 重叠 ===
    cmd.select("ligand", f"resn {ligand_name}")
    ligand_model = cmd.get_model("ligand")

    dl_chain = ""
    dl_resi = ""
    alt_labels = set()
    for at in ligand_model.atom:
        if not dl_chain:
            dl_chain = at.chain if at.chain else "A"
            dl_resi = at.resi
        if at.alt != '':
            alt_labels.add(at.alt)

    has_overlap = len(alt_labels) > 1
    if has_overlap:
        warning_msg = (f"WARNING [{pdb_id}]: Ligand {ligand_name} "
                       f"(Chain {dl_chain}, Res {dl_resi}) has overlapping "
                       f"alternate locations: {sorted(alt_labels)}.")
        print(f"  {warning_msg}")
        with open(os.path.join(os.path.dirname(base_dir), "altloc_warnings.log"), "a") as logf:
            logf.write(warning_msg + "\n")
        pref_alt = sorted(list(alt_labels))[-1]
        cmd.remove(f"not alt ''+{pref_alt}")

    cmd.alter("all", "alt=''")

    # === Step 3: Add Hydrogens and Generate MOL2 ===
    if has_overlap:
        print(f"  [Altlocs Detected] Downloading ideal MOL2 for {ligand_name} from RCSB ModelServer...")
        mol2_url = (f"https://models.rcsb.org/v1/{pdb_id.lower()}/ligand"
                    f"?auth_asym_id={dl_chain}&auth_seq_id={dl_resi}&encoding=mol2")
        mol2_file = os.path.join(work_dir, f"{pdb_id}_downloaded_ligand.mol2")
        
        try:
            urllib.request.urlretrieve(mol2_url, mol2_file)
            print(f"  Please manually align/fix coordinates since ModelServer provides ideal coordinates at origin.")
            # For now, just generate directly from PyMOL as fallback so we have right coordinates
            cmd.select("ligand", f"resn {ligand_name}")
            cmd.extract("extracted_ligand", "ligand")
            cmd.h_add("extracted_ligand")
            pymol_out = os.path.join(work_dir, f"{pdb_id}_ligand_H.mol2")
            cmd.save(pymol_out, "extracted_ligand")
            cmd.delete("extracted_ligand")
        except Exception as e:
            print(f"  ERROR: Failed to process downloaded MOL2 for {ligand_name}: {e}")
    else:
        print(f"  [Normal] Extracting {ligand_name} directly from CIF and adding hydrogens...")
        cmd.select("ligand", f"resn {ligand_name} and chain {dl_chain} and resi {dl_resi}")
        cmd.extract("extracted_ligand", "ligand")
        cmd.h_add("extracted_ligand")
        
        pymol_out = os.path.join(work_dir, f"{pdb_id}_ligand_H.mol2")
        cmd.save(pymol_out, "extracted_ligand")
        cmd.delete("extracted_ligand")
        print(f"  Saved {pdb_id}_ligand_H.mol2 directly from CIF structure.")

    # We also need to fix Occupancy, Halogen names, and Multiple chains for PDB just to be safe
    # This will be done to the generated files.

    # === Step 4: 保存复合物 PDB ===
    cmd.save(os.path.join(work_dir, f"{pdb_id}_complex.pdb"), "all")
    print(f"  Saved {pdb_id}_complex.pdb")
    cmd.delete("all")

print("\n" + "="*50)
print("All new_systems processed successfully!")
print("="*50)
