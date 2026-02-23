"""
check_completeness.py — 检查 new_systems/ 下各体系 CIF 文件的结构完整性

检查内容：
  1. _pdbx_unobs_or_zero_occ_residues — CIF 标准"缺失残基"表
  2. SEQRES vs ATOM 残基数量比较（通过 _pdbx_poly_seq_scheme）
  3. 链内残基编号断开处（gap > 1）
  4. 配体提取（_chem_comp_bond / HETATM）

输出：
  - 每个系统的完整性评估
  - 配体残基名（供后续 process_all.py 使用）
"""

import os, sys, re
from collections import defaultdict

base_dir = "/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures/new_systems"
systems = ["5J8U", "5J8M", "5J6N", "5J6L", "5J6M", "4EFU", "3LDP", "2YKJ", "2YKI", "2UWD", "2BSM"]

def parse_cif_loop(cif_text, category):
    """Extract a loop block for a given mmCIF category (e.g. _pdbx_unobs_or_zero_occ_residues)."""
    # Find the loop block containing the category
    pattern = r'loop_\s+((?:_' + re.escape(category.lstrip('_')) + r'\.\S+\s*)+)((?:(?!loop_|#).)+)'
    # More robust: find loops that contain the category key
    blocks = re.split(r'loop_', cif_text)
    results = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
        # Find header keys
        keys = []
        data_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('_'):
                keys.append(stripped.split()[0].lower())
                data_start = i + 1
            elif keys:
                data_start = i
                break
        if not any(category.lower() in k for k in keys):
            continue
        # Parse data rows
        data_lines = []
        for line in lines[data_start:]:
            s = line.strip()
            if not s or s.startswith('#') or s.startswith('_') or s == 'loop_':
                break
            data_lines.append(s)
        # Tokenize (handle quoted strings)
        tokens = []
        for dl in data_lines:
            toks = re.findall(r"'[^']*'|\"[^\"]*\"|\S+", dl)
            tokens.extend([t.strip("'\"") for t in toks])
        if not keys or not tokens:
            continue
        n = len(keys)
        rows = []
        for i in range(0, len(tokens) - n + 1, n):
            row = dict(zip(keys, tokens[i:i+n]))
            rows.append(row)
        results.extend(rows)
    return results


def get_single_value(cif_text, key):
    """Get a single key-value pair (non-loop) from mmCIF."""
    pattern = rf'^{re.escape(key)}\s+(.+)$'
    m = re.search(pattern, cif_text, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip().strip("'\"")
    return None


def analyze_system(pdb_id):
    cif_path = os.path.join(base_dir, pdb_id, f"{pdb_id}.cif")
    if not os.path.exists(cif_path):
        return {"pdb_id": pdb_id, "error": "CIF file not found"}

    with open(cif_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    result = {"pdb_id": pdb_id, "issues": [], "ligands": [], "complete": True}

    # ── 1. Missing residues from _pdbx_unobs_or_zero_occ_residues ──
    missing_rows = parse_cif_loop(text, "_pdbx_unobs_or_zero_occ_residues")
    # Filter to polymer only (exclude hetero)
    poly_missing = [r for r in missing_rows
                    if r.get("_pdbx_unobs_or_zero_occ_residues.polymer_flag", "Y").upper() == "Y"
                    or "polymer_flag" not in " ".join(r.keys())]
    
    # Count missing residues
    poly_missing_clean = []
    for r in poly_missing:
        # Key format may vary, try different forms
        flag_key = next((k for k in r if "polymer_flag" in k), None)
        chain_key = next((k for k in r if "auth_asym_id" in k or "asym_id" in k), None)
        resname_key = next((k for k in r if "mon_id" in k or "comp_id" in k), None)
        seqnum_key = next((k for k in r if "seq_id" in k or "auth_seq_id" in k), None)
        
        if flag_key and r.get(flag_key, "Y").upper() != "Y":
            continue  # skip non-polymer
        poly_missing_clean.append({
            "chain": r.get(chain_key, "?") if chain_key else "?",
            "resname": r.get(resname_key, "?") if resname_key else "?",
            "seqnum": r.get(seqnum_key, "?") if seqnum_key else "?"
        })

    if poly_missing_clean:
        n = len(poly_missing_clean)
        # Show first few
        examples = poly_missing_clean[:5]
        ex_str = ", ".join([f"{e['chain']}:{e['resname']}{e['seqnum']}" for e in examples])
        if n > 5:
            ex_str += f"... (+{n-5} more)"
        result["issues"].append(f"⚠️  {n} missing residue(s) in CIF: {ex_str}")
        if n > 10:
            result["complete"] = False

    # ── 2. Chain gaps from _pdbx_poly_seq_scheme ──
    scheme_rows = parse_cif_loop(text, "_pdbx_poly_seq_scheme")
    if scheme_rows:
        # Group by chain
        chain_data = defaultdict(list)
        for r in scheme_rows:
            chain_key = next((k for k in r if "pdb_strand_id" in k or "auth_mon_id" in k or "asym_id" in k), None)
            seqnum_key = next((k for k in r if "pdb_seq_num" in k or "auth_seq_num" in k), None)
            mon_key = next((k for k in r if "mon_id" in k or "pdb_mon_id" in k), None)
            ins_key = next((k for k in r if "pdb_ins_code" in k), None)
            
            if not chain_key or not seqnum_key:
                continue
            chain = r.get(chain_key, "?")
            seqnum_str = r.get(seqnum_key, "?")
            if seqnum_str in ("?", "."):
                continue
            try:
                seqnum = int(seqnum_str)
                chain_data[chain].append(seqnum)
            except ValueError:
                pass
        
        gaps = []
        for chain, nums in sorted(chain_data.items()):
            nums_sorted = sorted(set(nums))
            for i in range(1, len(nums_sorted)):
                gap = nums_sorted[i] - nums_sorted[i-1]
                if gap > 1:
                    gaps.append(f"Chain {chain}: gap {nums_sorted[i-1]}→{nums_sorted[i]} (missing {gap-1} res)")
        
        if gaps:
            result["issues"].append(f"⚠️  Chain gap(s) detected: " + "; ".join(gaps[:3]) + 
                                     ("..." if len(gaps) > 3 else ""))

    # ── 3. Extract ligands (non-standard residues) ──
    # From _pdbx_nonpoly_scheme or _struct_conn / HETATM lines
    np_rows = parse_cif_loop(text, "_pdbx_nonpoly_scheme")
    ligand_names = set()
    for r in np_rows:
        mon_key = next((k for k in r if "mon_id" in k or "comp_id" in k), None)
        if mon_key:
            val = r.get(mon_key, "")
            if val and val not in ("HOH", "WAT", "NA", "CL", "K", "MG", "CA", "ZN", "SO4", "PO4", "GOL", "EDO", "PEG"):
                ligand_names.add(val)
    
    # Also scan _chem_comp table
    comp_rows = parse_cif_loop(text, "_chem_comp")
    for r in comp_rows:
        id_key = next((k for k in r if k.endswith(".id")), None)
        type_key = next((k for k in r if "type" in k), None)
        if id_key and type_key:
            comp_type = r.get(type_key, "").upper()
            comp_id = r.get(id_key, "")
            if ("NON-POLYMER" in comp_type or "LIGAND" in comp_type) and comp_id:
                if comp_id not in ("HOH", "WAT", "NA", "CL", "K", "MG", "CA", "ZN", "SO4", "PO4", "GOL", "EDO"):
                    ligand_names.add(comp_id)

    result["ligands"] = sorted(ligand_names)

    # ── 4. Resolution ──
    res_val = get_single_value(text, "_reflns.d_resolution_high") or \
              get_single_value(text, "_refine.ls_d_res_high")
    if res_val:
        try:
            res_float = float(res_val)
            result["resolution"] = res_float
            if res_float > 3.0:
                result["issues"].append(f"⚠️  Low resolution: {res_float:.2f} Å (>3.0 Å)")
        except ValueError:
            pass

    return result


# ─── Main ───
print("=" * 70)
print("HSP90 new_systems — Structure Completeness Report")
print("=" * 70)

complete_systems = []
incomplete_systems = []

for pdb_id in systems:
    r = analyze_system(pdb_id)
    
    status = "✅ COMPLETE" if r.get("complete", False) and not r.get("issues") else (
             "⚠️  MINOR ISSUES" if r.get("complete", True) and r.get("issues") else
             "❌ INCOMPLETE")
    
    res_str = f"  Resolution: {r.get('resolution', 'N/A'):.2f} Å" if "resolution" in r else ""
    lig_str = f"  Ligands: {', '.join(r.get('ligands', ['(none found)']))}"
    
    print(f"\n{'─'*60}")
    print(f"{pdb_id}  [{status}]")
    if res_str:
        print(res_str)
    print(lig_str)
    if r.get("issues"):
        for issue in r["issues"]:
            print(f"  {issue}")
    
    if not r.get("issues"):
        complete_systems.append(pdb_id)
    else:
        incomplete_systems.append(pdb_id)

print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"✅ Clean (no issues): {complete_systems}")
print(f"⚠️  Has issues:        {incomplete_systems}")
print(f"\nLigand map for process_all.py:")
for pdb_id in systems:
    r = analyze_system(pdb_id)
    ligs = r.get("ligands", [])
    print(f'    "{pdb_id}": "{ligs[0] if ligs else "???"}",')
