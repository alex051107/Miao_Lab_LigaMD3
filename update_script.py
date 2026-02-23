import re
with open('process_new_systems.py', 'r') as f:
    content = f.read()

new_logic = """
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
"""

# Replace the old step 3 block
pattern = re.compile(r'# === Step 3:.*?# === Step 4: 保存复合物 PDB ===', re.DOTALL)
new_content = re.sub(pattern, new_logic.strip() + '\n\n    # === Step 4: 保存复合物 PDB ===', content)

with open('process_new_systems_fixed.py', 'w') as f:
    f.write(new_content)
