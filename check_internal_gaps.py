"""
check_internal_gaps.py — 区分 N-末端缺失 vs 内部链断


对每个体系的每条链：
- 统计 N-末端缺失（从第1个canonical残基开始，连续缺失）
- 统计 C-末端缺失（从最后1个canonical残基开始，连续缺失）
- 检测内部 gap（跳过N-/C-末端后仍有不连续编号）
"""

import os, re
from collections import defaultdict

base_dir = "/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures/new_systems"
systems = ["5J8U", "5J8M", "5J6N", "5J6L", "5J6M", "4EFU", "3LDP", "2YKJ", "2YKI", "2UWD", "2BSM"]

SOLVENT = {"HOH","WAT","NA","CL","K","MG","CA","ZN","SO4","PO4","GOL","EDO","PEG","ACT","IMD","DMS"}

def parse_cif_loop(cif_text, category):
    blocks = re.split(r'loop_', cif_text)
    results = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
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
        data_lines = []
        for line in lines[data_start:]:
            s = line.strip()
            if not s or s.startswith('#') or s.startswith('_') or s == 'loop_':
                break
            data_lines.append(s)
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


def analyze_gaps(pdb_id):
    cif_path = os.path.join(base_dir, pdb_id, f"{pdb_id}.cif")
    with open(cif_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    # Get missing residues
    missing_rows = parse_cif_loop(text, "_pdbx_unobs_or_zero_occ_residues")
    
    # Build per-chain list of missing residue sequence numbers
    chain_missing = defaultdict(list)
    for r in missing_rows:
        # find relevant keys
        flag_key = next((k for k in r if "polymer_flag" in k), None)
        if flag_key and r.get(flag_key, "Y").upper() != "Y":
            continue
        chain_key = next((k for k in r if "auth_asym_id" in k), None) or \
                    next((k for k in r if "asym_id" in k), None)
        seqnum_key = next((k for k in r if "auth_seq_id" in k or "pdb_seq_num" in k), None) or \
                     next((k for k in r if "seq_id" in k), None)
        mon_key = next((k for k in r if "mon_id" in k or "comp_id" in k), None)
        
        chain = r.get(chain_key, "?") if chain_key else "?"
        mon = r.get(mon_key, "") if mon_key else ""
        if mon.upper() in SOLVENT:
            continue
        try:
            seqnum = int(r.get(seqnum_key, "?") if seqnum_key else "?")
            chain_missing[chain].append((seqnum, mon))
        except ValueError:
            pass

    # Get observed residues from _pdbx_poly_seq_scheme
    scheme_rows = parse_cif_loop(text, "_pdbx_poly_seq_scheme")
    chain_observed = defaultdict(list)
    for r in scheme_rows:
        chain_key = next((k for k in r if "pdb_strand_id" in k), None) or \
                    next((k for k in r if "auth_asym_id" in k), None)
        seqnum_key = next((k for k in r if "pdb_seq_num" in k or "auth_seq_num" in k), None)
        mon_key = next((k for k in r if "pdb_mon_id" in k or "mon_id" in k), None)
        
        if not chain_key or not seqnum_key:
            continue
        chain = r.get(chain_key, "?")
        try:
            seqnum = int(r.get(seqnum_key, "?") if seqnum_key else "?")
            chain_observed[chain].append(seqnum)
        except ValueError:
            pass

    internal_gaps = []
    nterm_missing_total = 0
    cterm_missing_total = 0

    for chain, missing_residues in sorted(chain_missing.items()):
        obs = sorted(set(chain_observed.get(chain, [])))
        miss_nums = sorted([m[0] for m in missing_residues])
        
        if not obs or not miss_nums:
            continue
        
        obs_min = min(obs)
        obs_max = max(obs)
        
        # N-terminal: missing residues before the first observed
        nterm = [m for m in miss_nums if m < obs_min]
        # C-terminal: missing residues after the last observed  
        cterm = [m for m in miss_nums if m > obs_max]
        # Internal: everything else
        internal = [m for m in miss_nums if obs_min <= m <= obs_max]
        
        nterm_missing_total += len(nterm)
        cterm_missing_total += len(cterm)
        
        if internal:
            internal_gaps.append(f"Chain {chain}: {len(internal)} INTERNAL missing → {internal[:5]}{'...' if len(internal)>5 else ''}")

    return {
        "pdb_id": pdb_id,
        "nterm": nterm_missing_total,
        "cterm": cterm_missing_total,
        "internal_gaps": internal_gaps
    }


print("=" * 70)
print("Internal Gap Analysis (N-terminal miss is NORMAL for HSP90 NTD)")
print("=" * 70)

for_processing = []

for pdb_id in systems:
    r = analyze_gaps(pdb_id)
    internal = r["internal_gaps"]
    
    if not internal:
        status = "✅ OK for simulation"
        for_processing.append(pdb_id)
    else:
        status = "❌ INTERNAL BREAKS — check before CHARMM-GUI"
    
    print(f"\n{pdb_id}  [{status}]")
    print(f"  N-terminal missing: {r['nterm']}  |  C-terminal missing: {r['cterm']}")
    if internal:
        for g in internal:
            print(f"  ⛔ {g}")
    else:
        print(f"  → All missing residues are at termini (expected for crystal structures)")

print(f"\n{'='*70}")
print(f"Can proceed to PyMOL processing: {for_processing}")
print(f"{'='*70}")
