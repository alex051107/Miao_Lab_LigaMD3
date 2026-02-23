#!/bin/bash
# Description: Automates the entire process of uploading CHARMM-GUI results to Longleaf
# and configuring the Amber MD inputs.

set -e

PDB_ID=$1
LONGLEAF_USER="liualex"
LOCAL_HSP90_DIR="/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures"
REMOTE_BASE="/users/l/i/liualex/Miao_lab/HSP90_new"

if [ -z "$PDB_ID" ]; then
    echo "Usage: ./upload_and_setup.sh <PDB_ID>"
    echo "Example: ./upload_and_setup.sh 2YKJ"
    exit 1
fi

SYSTEM_DIR="${LOCAL_HSP90_DIR}/new_systems/${PDB_ID}"
if [ ! -d "$SYSTEM_DIR" ]; then
    echo "Error: Directory ${SYSTEM_DIR} not found!"
    exit 1
fi

# Step 1: Handle charmm-gui.tgz extraction
TGZ_FILE=$(find "$SYSTEM_DIR" -maxdepth 1 -name "charmm-gui*.tgz" | head -n 1)
CG_DIR=$(find "$SYSTEM_DIR" -maxdepth 1 -type d -name "charmm-gui-*" | head -n 1)

if [ -n "$TGZ_FILE" ]; then
    echo "Found CHARMM-GUI archive: $(basename "$TGZ_FILE")"
    if [ -z "$CG_DIR" ]; then
        echo "Extracting archive..."
        tar -xzf "$TGZ_FILE" -C "$SYSTEM_DIR"
        CG_DIR=$(find "$SYSTEM_DIR" -maxdepth 1 -type d -name "charmm-gui-*" | head -n 1)
    else
        echo "Archive is already extracted to: $(basename "$CG_DIR")"
    fi
elif [ -n "$CG_DIR" ]; then
    echo "Found extracted CHARMM-GUI folder: $(basename "$CG_DIR")"
else
    echo "Error: No charmm-gui*.tgz or extracted charmm-gui-* folder found in ${SYSTEM_DIR}"
    exit 1
fi

# Step 2: Prompt user for upload confirmation
echo ""
read -p "Do you want to upload this CHARMM-GUI setup to Longleaf and run Amber config now? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Upload aborted by user."
    exit 0
fi

CG_FOLDER_NAME=$(basename "$CG_DIR")
REMOTE_TARGET="${REMOTE_BASE}/${PDB_ID}/cMD"

echo "=========================================="
echo "Step 1: Uploading CHARMM-GUI data to Longleaf..."
echo "Target: ${REMOTE_TARGET}"
echo "=========================================="

# Create remote directory and upload
ssh ${LONGLEAF_USER}@longleaf.unc.edu "mkdir -p ${REMOTE_TARGET}"
scp -r "${CG_DIR}" ${LONGLEAF_USER}@longleaf.unc.edu:${REMOTE_TARGET}/

echo ""
echo "=========================================="
echo "Step 2: Configuring Amber on Longleaf..."
echo "=========================================="

ssh ${LONGLEAF_USER}@longleaf.unc.edu << EOF
    set -e
    cd ${REMOTE_TARGET}/${CG_FOLDER_NAME}/amber

    echo "  -> Running pdb4amber..."
    source /proj/ymiaolab/software/amber22/amber.sh
    pdb4amber -i step3_input.pdb -o amber.pdb

    echo "  -> Patching run-cmd.csh..."
    mv README run-cmd.csh
    chmod +x run-cmd.csh
    
    # Insert 'which pmemd.cuda' after #!/bin/csh
    sed -i 's|#!/bin/csh|#!/bin/csh\nwhich pmemd.cuda|g' run-cmd.csh
    
    # Fix 'set amber' to exactly 'set amber = pmemd.cuda# set amber = "mpirun -np 4 pmemd.MPI"'
    sed -i 's|^set amber =.*|set amber = pmemd.cuda# set amber = "mpirun -np 4 pmemd.MPI"|g' run-cmd.csh

    echo "Done patching run-cmd.csh!"
EOF

echo ""
echo "=========================================="
echo "Step 3: Downloading amber.pdb to local Mac..."
echo "=========================================="

# Download the cleaned amber.pdb back to the local system directory
scp ${LONGLEAF_USER}@longleaf.unc.edu:${REMOTE_TARGET}/${CG_FOLDER_NAME}/amber/amber.pdb "${SYSTEM_DIR}/amber_${PDB_ID}.pdb"

echo ""
echo "✅ Finished setup for ${PDB_ID}!"
echo "---------------------------------------------------------"
echo "NEXT CRITICAL STEP:"
echo "1. Open PyMOL and load: new_systems/${PDB_ID}/amber_${PDB_ID}.pdb"
echo "2. Find the polar contacts and record atom_p and atom_l."
echo "3. Then SSH into Longleaf, create your sub-cmd.slum and md.in,"
echo "   and submit your equilibration/production runs!"
echo "---------------------------------------------------------"
