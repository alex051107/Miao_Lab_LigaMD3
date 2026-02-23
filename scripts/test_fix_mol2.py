import re

def fix_mol2_types(raw_mol2, pymol_mol2, out_mol2):
    # Extracts types from raw mol2
    type_map = {}
    with open(raw_mol2) as f:
        in_atom = False
        for line in f:
            if line.startswith("@<TRIPOS>ATOM"):
                in_atom = True
                continue
            if line.startswith("@<TRIPOS>BOND"):
                break
            if in_atom and line.strip():
                parts = line.split()
                if len(parts) >= 6:
                    name = parts[1]
                    t_type = parts[5]
                    type_map[name] = t_type

    print("Extracted Types:", type_map)

    # Patch pymol mol2
    out_lines = []
    with open(pymol_mol2) as f:
        in_atom = False
        for line in f:
            if line.startswith("@<TRIPOS>ATOM"):
                in_atom = True
                out_lines.append(line)
                continue
            if line.startswith("@<TRIPOS>BOND"):
                in_atom = False
            
            if in_atom and line.strip():
                parts = line.split()
                if len(parts) >= 6:
                    name = parts[1]
                    if name in type_map:
                        true_type = type_map[name]
                        # Replace the 6th column exactly
                        # PyMOL formats: `1         C1    0.172   36.969  24.466  C.2     1       6FJ301`
                        # We use regex to replace the type field.
                        line = re.sub(r'(\s+'+name+r'\s+[\-\.\d]+\s+[\-\.\d]+\s+[\-\.\d]+\s+)[A-Za-z0-9\.]+(\s+)', r'\g<1>' + true_type + r'\g<2>', line)
            
            out_lines.append(line)
            
    with open(out_mol2, "w") as f:
        f.writelines(out_lines)
    print("Fixed MOL2 created.")

fix_mol2_types("5J20/5J20_downloaded_ligand.mol2", "5J20/5J20_ligand_H.mol2", "5J20/5J20_ligand_H_fixed.mol2")
