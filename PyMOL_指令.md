# PyMOL 手动处理指令（通用版）

每个体系执行相同命令：
```
load [PDB_ID].cif
remove solvent
remove resn NA+CL+K+MG+CA+ZN
select ligand, organic
h_add ligand
save ligand.mol2, ligand
save complex.pdb, all
delete all
```

`organic` 会自动选择配体（小分子有机物），无需知道具体残基名。
