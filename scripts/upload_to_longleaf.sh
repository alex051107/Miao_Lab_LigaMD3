#!/bin/bash
# Description: Automates the entire process of uploading CHARMM-GUI results to Longleaf
# and configuring the Amber MD inputs.

set -e

PDB_ID=$1
LONGLEAF_USER="liualex"
LOCAL_HSP90_DIR="/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures"
REMOTE_BASE="/users/l/i/liualex/Miao_lab/HSP90_new"

if [ $# -eq 0 ]; then
    echo "Usage: ./upload_and_setup.sh <PDB_ID_1> <PDB_ID_2> ..."
    echo "Example: ./upload_and_setup.sh 2YKJ 5J8U 2BSM"
    exit 1
fi

# Step 1: Prompt user for upload confirmation for the whole batch
echo "You are about to process the following systems: $@"
read -p "Do you want to upload these CHARMM-GUI setups to Longleaf and run Amber config now? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Upload aborted by user."
    exit 0
fi

for PDB_ID in "$@"; do
    echo "---------------------------------------------------------"
    echo "🚀 Starting processing for system: ${PDB_ID}"
    echo "---------------------------------------------------------"

    SYSTEM_DIR="${LOCAL_HSP90_DIR}/new_systems/${PDB_ID}"
    if [ ! -d "$SYSTEM_DIR" ]; then
        echo "Error: Directory ${SYSTEM_DIR} not found! Skipping..."
        continue
    fi

    # Prefer an already extracted successful CHARMM-GUI run with amber/.
    CG_DIR=$(find "$SYSTEM_DIR" -maxdepth 1 -type d -name "charmm-gui-*" | while read -r d; do
        [ -d "$d/amber" ] && echo "$d"
    done | sort | tail -n 1)

    # Otherwise, search the newest archive that actually contains amber/.
    TGZ_FILE=""
    if [ -z "$CG_DIR" ]; then
        TGZ_FILE=$(find "$SYSTEM_DIR" -maxdepth 1 -type f -name "charmm-gui*.tgz" -print0 | while IFS= read -r -d '' f; do
            if tar -tzf "$f" | grep -q '/amber/'; then
                stat -f "%m %N" "$f"
            fi
        done | sort -n | tail -n 1 | cut -d' ' -f2-)
    fi

    if [ -n "$CG_DIR" ]; then
        echo "Found extracted CHARMM-GUI folder: $(basename "$CG_DIR")"
    elif [ -n "$TGZ_FILE" ]; then
        echo "Found valid CHARMM-GUI archive: $(basename "$TGZ_FILE")"
        echo "Extracting archive..."
        tar -xzf "$TGZ_FILE" -C "$SYSTEM_DIR"
        CG_DIR=$(find "$SYSTEM_DIR" -maxdepth 1 -type d -name "charmm-gui-*" | while read -r d; do
            [ -d "$d/amber" ] && echo "$d"
        done | sort | tail -n 1)
    else
        echo "Error: No successful CHARMM-GUI archive/folder with amber/ found in ${SYSTEM_DIR}. Skipping..."
        continue
    fi

    if [ -z "$CG_DIR" ] || [ ! -d "$CG_DIR/amber" ]; then
        echo "Error: Could not locate a usable amber/ directory for ${PDB_ID}. Skipping..."
        continue
    fi

    AMBER_DIR="${CG_DIR}/amber"
    REQUIRED_FILES=("step3_input.pdb" "step3_input.parm7" "step3_input.rst7" "README")
    LOCAL_OK="YES"
    for f in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "${AMBER_DIR}/${f}" ]; then
            echo "Error: Local amber directory is missing ${f} for ${PDB_ID}. Skipping..."
            LOCAL_OK="NO"
        fi
    done
    if [ "$LOCAL_OK" != "YES" ]; then
        continue
    fi

    CG_FOLDER_NAME=$(basename "$CG_DIR")
    REMOTE_TARGET="${REMOTE_BASE}/${PDB_ID}"

    echo "=========================================="
    echo "Step 1: Setting up Longleaf directory structure..."
    echo "Target: ${REMOTE_TARGET}"
    echo "=========================================="

    # Create the master directory structure on Longleaf
    ssh ${LONGLEAF_USER}@longleaf.unc.edu << EOF
        mkdir -p "${REMOTE_TARGET}/cMD"
        
        # Create equilibration folders for different sigma values
        for sigma in 1.5 1.8 2.0 2.2 2.5 2.8 3.0 3.2 3.5; do
            mkdir -p "${REMOTE_TARGET}/equilibration/e1_sigma\${sigma}"
        done
        
        # Create production placeholder
        mkdir -p "${REMOTE_TARGET}/production"
EOF
    echo "✅ Directory structure created."

    echo ""
    echo "=========================================="
    echo "Step 2: Uploading CHARMM-GUI data to Longleaf..."
    echo "=========================================="

    # Check if the remote amber folder is complete. If not, force re-upload.
    REMOTE_CG_DIR="${REMOTE_TARGET}/cMD/${CG_FOLDER_NAME}"
    REMOTE_OK=$(ssh ${LONGLEAF_USER}@longleaf.unc.edu "\
        if [ -d \"${REMOTE_CG_DIR}/amber\" ] && \
           [ -f \"${REMOTE_CG_DIR}/amber/step3_input.pdb\" ] && \
           [ -f \"${REMOTE_CG_DIR}/amber/step3_input.parm7\" ] && \
           [ -f \"${REMOTE_CG_DIR}/amber/step3_input.rst7\" ] && \
           [ -f \"${REMOTE_CG_DIR}/amber/README\" ]; then \
            echo 'YES'; \
        else \
            echo 'NO'; \
        fi")

    if [ "$REMOTE_OK" == "YES" ]; then
        echo "⚡ Bypassing upload: ${CG_FOLDER_NAME}/amber already exists on Longleaf."
    else
        echo "Uploading ${CG_FOLDER_NAME}/amber to ${REMOTE_TARGET}/cMD/ ..."
        ssh ${LONGLEAF_USER}@longleaf.unc.edu "mkdir -p \"${REMOTE_CG_DIR}\""
        ssh ${LONGLEAF_USER}@longleaf.unc.edu "rm -rf \"${REMOTE_CG_DIR}/amber\""
        scp -r "${CG_DIR}/amber" ${LONGLEAF_USER}@longleaf.unc.edu:"${REMOTE_CG_DIR}/"
    fi

    echo ""
    echo "=========================================="
    echo "Step 3: Configuring Amber on Longleaf..."
    echo "=========================================="

    ssh ${LONGLEAF_USER}@longleaf.unc.edu << EOF
        set -e
        cd "${REMOTE_TARGET}/cMD/${CG_FOLDER_NAME}/amber"

        if [ ! -f step3_input.pdb ]; then
            echo "ERROR: step3_input.pdb is missing in \$(pwd)"
            ls -la
            exit 1
        fi

        echo "  -> Running pdb4amber..."
        source /proj/ymiaolab/software/amber22/amber.sh
        pdb4amber -i step3_input.pdb -o amber.pdb
EOF

    echo ""
    echo "=========================================="
    echo "Step 4: Downloading amber.pdb to local Mac..."
    echo "=========================================="

    # Download the cleaned amber.pdb back to the local system directory
    scp ${LONGLEAF_USER}@longleaf.unc.edu:"${REMOTE_TARGET}/cMD/${CG_FOLDER_NAME}/amber/amber.pdb" "${SYSTEM_DIR}/amber_${PDB_ID}.pdb"

    echo ""
    echo "✅ Finished setup for ${PDB_ID}!"
    echo ""
done

echo "---------------------------------------------------------"
echo "ALL SYSTEMS PROCESSED SUCCESSFULLY!"
echo "NEXT CRITICAL STEPS:"
echo "1. On Longleaf, run your batch script to submit all cMD jobs."
echo "2. Locally, open PyMOL and load the downloaded amber_<ID>.pdb files."
echo "3. Find the polar contacts and record atom_p and atom_l for Equil."
echo "---------------------------------------------------------"
