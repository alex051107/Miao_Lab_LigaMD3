import re

with open('HSP90_LiGaMD3_Complete_Workflow.md', 'r') as f:
    content = f.read()

new_section = """
### 1.7 [CRITICAL] CHARMM-GUI 报错排雷指南
在上传 `complex.pdb` 和配体 `ligand_H.mol2` 到 CHARMM-GUI 之前，强烈建议排查以下晶体学坑：

#### 🔴 坑1：晶体解析中的多链冗余 (Multiple Chains in Asymmetric Unit)
* **表现:** CHARMM-GUI 选链界面出现 `PROA, PROB, PROC` 和 `HETA, HETB`，一堆重复的复合物。
* **原因:** 晶格不对称单元中包含同源二聚体/多聚体。（如 3LDP, 5J8U）
* **解决:** 在保存 `complex.pdb` 前，确保只选取 Chain A 的蛋白和配体：
  `PyMOL> save complex.pdb, chain A and (polymer or resn LIG)`

#### 🔴 坑2：配体卤素大小写导致 Antechamber 崩溃
* **报错:** PDB Reader 阶段提示 `ANTECHAMBER failed to parameterize force field` 或在 PBC Setup 提示 `Ligand FF parameterization failed`.
* **原因:** RCSB 官方下载的 mol2 文件或部分生成器，会将卤素完全大写（如 `CL`, `BR`），Antechamber 的 Tripos/GAFF2 匹配器不认识这个元素（认为是一种未知的碳同位素）。
* **解决:** 用文本编辑器打开配体 `.mol2` 文件，找到 `@<TRIPOS>ATOM` 部分，**手动将原子类型列（第6列）的 `CL` 改为 `Cl`，`BR` 改为 `Br`**。

#### 🔴 坑3：占有率 < 1.0 导致坐标丢失
* **报错:** `ABNORMAL TERMINATION: Undefined coordinates`。
* **原因:** 蛋白质（如 2YKI）存在部分残基原子占有率（occupancy）为 0.5 等非 1.0 的情况。一旦低于 1，CHARMM 就标记为坐标缺失。
* **解决:** 文本编辑器打开 `_complex.pdb`，将第 55~60 列的所有数字强行替换/修正为 `  1.00`。

#### 🔴 坑4：配体 MOL2 与 PDB 空间坐标不匹配
* **报错:** `ABNORMAL TERMINATION: Undefined coordinates` (发生在建膜时)。
* **原因:** 从 RCSB 官网 `models.rcsb.org/.../ligand` 单加下载的理想 mol2，其三维坐标是在原点 (0,0,0) 生成的，并没有跟 PDB 中的口袋坐标对齐！
* **解决:** **必须**从已经与蛋白对齐的 CIF/PDB 晶体文件中直接将配体 extract 出来加氢并导出 mol2。**不要**轻易使用外部纯粹化学坐标下载的模版，除非经过严格的坐标对齐操作。
"""

pattern = re.compile(r'(### 1.6 修改 PDB 编号.*?)(## 第二步：CHARMM-GUI 网页操作)', re.DOTALL)
new_content = re.sub(pattern, r'\g<1>\n' + new_section + r'\n\g<2>', content)

with open('HSP90_LiGaMD3_Complete_Workflow.md', 'w') as f:
    f.write(new_content)

print("Workflow updated successfully")
