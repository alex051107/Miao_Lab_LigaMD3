import os
import math

def calc_dist(a1, a2):
    return math.sqrt((a1[0]-a2[0])**2 + (a1[1]-a2[1])**2 + (a1[2]-a2[2])**2)

def check_pdb(filepath):
    missing_residues = False
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    for line in lines:
        if line.startswith("REMARK 465"):
            # Often indicates missing residues
            missing_residues = True
            break
            
    # Also check structural gaps by distance between successive CA atoms
    ca_atoms = []
    for line in lines:
        if line.startswith("ATOM  ") and line[12:16].strip() == "CA":
            chain = line[21]
            resnum = int(line[22:26].strip())
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            ca_atoms.append((chain, resnum, (x, y, z)))
            
    gaps = []
    for i in range(1, len(ca_atoms)):
        p1 = ca_atoms[i-1]
        p2 = ca_atoms[i]
        # Only check within the same chain
        if p1[0] == p2[0]:
            dist = calc_dist(p1[2], p2[2])
            # CA-CA distance is normally ~3.8 Angstroms. Allow some flexibility.
            if dist > 4.5:
                gaps.append((p1[0], p1[1], p2[1], dist))
                
    return missing_residues, gaps

base_dir = "/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures/new_systems"
sys_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

for sys in sorted(sys_dirs):
    pdb_file = os.path.join(base_dir, sys, f"{sys}_complex.pdb")
    if not os.path.exists(pdb_file):
        # Maybe lowercase
        pdb_file = os.path.join(base_dir, sys, f"{sys.lower()}_complex.pdb")
        
    if os.path.exists(pdb_file):
        missing, gaps = check_pdb(pdb_file)
        print(f"System: {sys}")
        print(f"  Missing residues indicated in header (REMARK 465)? {'Yes' if missing else 'No'}")
        if len(gaps) > 0:
            print(f"  Found {len(gaps)} structural gaps (CA-CA dist > 4.5 A):")
            for g in gaps:
                print(f"    Chain {g[0]}: Res {g[1]} to Res {g[2]} -> {g[3]:.2f} A gap")
        else:
            print("  No internal structural gaps detected (chain continuity looks good).")
        print("-" * 50)
    else:
        print(f"System: {sys} - PDB file not found.")
