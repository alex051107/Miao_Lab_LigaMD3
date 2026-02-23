# HSP90 批量处理脚本
# 用法: /Applications/PyMOL.app/Contents/MacOS/PyMOL -cq process_all.py
#
# 工作流程:
#   1. 加载 CIF 晶体结构
#   2. 去水、去杂离子
#   3. 检测配体是否存在 Altloc 重叠 (若有，清理 complex.pdb 中的多余构象，并生成警告日志)
#   4. 统一从 RCSB ModelServer 下载单构象且自带拓扑的 MOL2
#   5. 对下载的 MOL2 执行 h_add 加氢，重命名连锁信息后保存为 ligand.mol2
#   6. 输出干净的 单一构象 complex.pdb

import os
import urllib.request

base_dir = "/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures"
systems = ["5J86", "5J82", "5J64", "5J2X", "5J27", "5J20"]

# 映射每个体系对应的配体残基名称
ligand_map = {
    "5J86": "6GW", "5J82": "6GV", "5J64": "6G7",
    "5J2X": "6DL", "5J27": "6FF", "5J20": "6FJ"
}

for pdb_id in systems:
    print(f"\nProcessing {pdb_id}")
    
    work_dir = os.path.join(base_dir, pdb_id)
    cif_file = os.path.join(work_dir, f"{pdb_id}.cif")
    
    # === Step 1: 加载与清理 ===
    cmd.load(cif_file)
    cmd.remove("solvent")
    cmd.remove("resn NA+CL+K+MG+CA+ZN+FE+MN+CU+NI+CO")
    
    ligand_name = ligand_map.get(pdb_id)
    if not ligand_name:
        print(f"  No ligand mapping found for {pdb_id}, skipping ligand processing.")
        cmd.save(os.path.join(work_dir, f"{pdb_id}_complex.pdb"), "all")
        cmd.delete("all")
        continue
    
    # === Step 2: 检测配体 Altloc 重叠 ===
    cmd.select("ligand", f"resn {ligand_name}")
    ligand_model = cmd.get_model("ligand")
    
    # 动态提取配体的链名和残基编号
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
        # ─── 有重叠：写警告并清理复合物 ───
        warning_msg = (f"WARNING [ {pdb_id} ]: Ligand {ligand_name} "
                       f"(Chain {dl_chain}, Res {dl_resi}) has overlapping "
                       f"alternate locations: {sorted(alt_labels)}.")
        print(f"  {warning_msg}")
        
        # 写警告日志
        with open(os.path.join(base_dir, "altloc_warnings.log"), "a") as logf:
            logf.write(warning_msg + "\n")
        
        # 清理复合物中的多余构象 (保留字母顺序最后一个，通常占据率较高)
        pref_alt = sorted(list(alt_labels))[-1]
        cmd.remove(f"not alt ''+{pref_alt}")
        
    cmd.alter("all", "alt=''")
        
    # === Step 3: 始终从 RCSB 下载单构象 MOL2 以确保加氢成功 ===
    mol2_url = (f"https://models.rcsb.org/v1/{pdb_id.lower()}/ligand"
                f"?auth_asym_id={dl_chain}&auth_seq_id={dl_resi}&encoding=mol2")
    mol2_file = os.path.join(work_dir, f"{pdb_id}_downloaded_ligand.mol2")
    
    try:
        print(f"  Downloading ideal MOL2 for {ligand_name} from RCSB ModelServer...")
        urllib.request.urlretrieve(mol2_url, mol2_file)
        
        # --- NEW: Extract correct Tripos atom types (e.g., C.ar, O.co2) from raw ModelServer MOL2 ---
        true_types = {}
        with open(mol2_file, 'r') as f:
            in_atoms = False
            for line in f:
                if line.startswith("@<TRIPOS>ATOM"):
                    in_atoms = True
                    continue
                if line.startswith("@<TRIPOS>BOND"):
                    break
                if in_atoms and line.strip():
                    parts = line.split()
                    if len(parts) >= 6:
                        true_types[parts[1]] = parts[5]
                        
        # 加载下载的纯净 MOL2 并加氢
        cmd.load(mol2_file, "clean_ligand")
        cmd.h_add("clean_ligand")
        
        # 统一残基信息 (保持与 PDB 一致)
        cmd.alter("clean_ligand", f"resn='{ligand_name}'")
        cmd.alter("clean_ligand", f"chain='{dl_chain}'")
        cmd.alter("clean_ligand", f"resi='{dl_resi}'")
        
        pymol_out = os.path.join(work_dir, f"{pdb_id}_ligand_H.mol2")
        cmd.save(pymol_out, "clean_ligand")
        cmd.delete("clean_ligand")
        
        # --- NEW: Patch the PyMOL output MOL2 with the true Tripos atom types ---
        patched_lines = []
        with open(pymol_out, 'r') as f:
            in_atoms = False
            for line in f:
                if line.startswith("@<TRIPOS>ATOM"):
                    in_atoms = True
                    patched_lines.append(line)
                    continue
                if line.startswith("@<TRIPOS>BOND"):
                    in_atoms = False
                
                if in_atoms and line.strip():
                    parts = line.split()
                    if len(parts) >= 6:
                        name = parts[1]
                        if name in true_types:
                            # PyMOL typically formats column 6 at a specific visual offset, using a regex to replace just the type
                            import re
                            # Match the first 5 columns, capture the whitespace, replace the type, leave the rest
                            pat = r'^(\s*\S+\s+' + re.escape(name) + r'\s+[\-\.\d]+\s+[\-\.\d]+\s+[\-\.\d]+\s+)\S+(.*)$'
                            true_t = true_types[name]
                            line = re.sub(pat, r'\g<1>' + true_t + r'\g<2>', line)
                
                patched_lines.append(line)
                
        with open(pymol_out, 'w') as f:
            f.writelines(patched_lines)
        
        # 删除原始下载的无氢 MOL2 留下干净的文件夹
        if os.path.exists(mol2_file):
            os.remove(mol2_file)
            
        print(f"  Saved {pdb_id}_ligand_H.mol2 (with correct C.ar topologies patched in!).")
        
    except Exception as e:
        print(f"  ERROR: Failed to process MOL2 for {ligand_name}: {e}")
        cmd.save(os.path.join(work_dir, f"{pdb_id}_ligand_H.mol2"), "ligand")
    
    # === Step 4: 保存复合物 PDB ===
    cmd.save(os.path.join(work_dir, f"{pdb_id}_complex.pdb"), "all")
    cmd.delete("all")

print("\nDone!")
