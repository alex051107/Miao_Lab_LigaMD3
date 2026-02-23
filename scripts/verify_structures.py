import os

base_dir = "/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures"
systems = ["5J86", "5J82", "5J64", "5J2X", "5J27", "5J20"]

def get_pdb_chains_and_ligands(pdb_file):
    protein_chains = set()
    ligands = {}
    missing_gaps = []
    
    last_res_num = {}
    
    with open(pdb_file, 'r') as f:
        for line in f:
            if line.startswith("ATOM  "):
                res_name = line[17:20].strip()
                chain = line[21]
                res_num = int(line[22:26].strip())
                
                protein_chains.add(chain)
                
                if chain in last_res_num:
                    if res_num - last_res_num[chain] > 1:
                        missing_gaps.append(f"Chain {chain}: gap between {last_res_num[chain]} and {res_num}")
                
                if res_name not in ["HOH"]: # ignoring water, not strictly needed as it's removed
                    last_res_num[chain] = res_num
                    
            elif line.startswith("HETATM"):
                res_name = line[17:20].strip()
                chain = line[21]
                if res_name not in ligands:
                    ligands[res_name] = set()
                ligands[res_name].add(chain)
                
    return protein_chains, ligands, missing_gaps

def get_mol2_ligand_name(mol2_file):
    # parse mol2 for molecule name or substructure name
    # typically in @<TRIPOS>MOLECULE or @<TRIPOS>ATOM
    with open(mol2_file, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith("@<TRIPOS>ATOM"):
                parts = lines[i+1].split()
                if len(parts) >= 8:
                    return parts[7].strip() # usually the 8th column is substructure name
    return None

for pdb_id in systems:
    print(f"\n--- System: {pdb_id} ---")
    work_dir = os.path.join(base_dir, pdb_id)
    complex_file = os.path.join(work_dir, f"{pdb_id}_complex.pdb")
    mol2_file = os.path.join(work_dir, f"{pdb_id}_ligand_H.mol2")
    
    if os.path.exists(complex_file) and os.path.exists(mol2_file):
        chains, ligands, gaps = get_pdb_chains_and_ligands(complex_file)
        mol2_ligand = get_mol2_ligand_name(mol2_file)
        
        print(f"Protein Chains: {', '.join(chains)}")
        print(f"Ligands in PDB (HETATM): {ligands}")
        print(f"Ligand in MOL2: {mol2_ligand}")
        if gaps:
            print(f"Missing residue gaps detected (Top 3):")
            for g in gaps[:3]:
                print(f"  - {g}")
            if len(gaps) > 3:
                print(f"  ... and {len(gaps) - 3} more gaps")
    else:
        print("Missing output files!")

