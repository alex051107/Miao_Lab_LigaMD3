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

# Find the unzipped charmm-gui folder
CG_DIR=$(find "$SYSTEM_DIR" -maxdepth 1 -type d -name "charmm-gui-*" | head -n 1)

if [ -z "$CG_DIR" ]; then
    echo "Error: No extracted charmm-gui-* folder found in ${SYSTEM_DIR}"
    exit 1
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

    echo "  -> Creating sub-cmd.slum..."
    cat << 'SLURM' > sub-cmd.slum
#!/bin/bash

#SBATCH --job-name=cMD-${PDB_ID}
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --partition=l40-gpu
#SBATCH --output=log.%x.%j
#SBATCH --gres=gpu:1
#SBATCH --qos=gpu_access
#SBATCH --constraint=rhel8

module load gcc/11.2.0 cuda/11.8

source /proj/ymiaolab/software/amber24/amber.sh

module purge
module load amber/24p3

which pmemd.cuda

chmod +x run-cmd.csh

./run-cmd.csh
SLURM

    echo "Done for ${PDB_ID}! Configuration files ready."
    echo "To submit, SSH into Longleaf, cd to ${REMOTE_TARGET}/${CG_FOLDER_NAME}/amber, and run 'sbatch sub-cmd.slum'"
EOF

echo ""
echo "✅ Finished! Run this script for the next systems as they finish."
