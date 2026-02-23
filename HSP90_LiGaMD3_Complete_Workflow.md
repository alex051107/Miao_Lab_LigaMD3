# HSP90 LiGaMD3 蛋白-配体解离模拟：完整操作流程指南

## 文档说明

本文档整合了以下所有信息源，形成一份可复现的端到端操作手册：

- 2026年2月13日实验室会议录音转录
- 实验室 PPT 截图（LiGaMD3 参数配置 + CHARMM-GUI 设置）
- PyMOL 操作截图（polar contacts 查找）
- 此前积累的操作笔记与流程文档

适用体系：HSP90 蛋白与不同小分子配体的 LiGaMD3 增强采样模拟。

**已完成体系**：5OCI, 5OD7, 5ODX
**待配置体系**：5J86, 5J82, 5J64, 5J2X, 5J27, 5J20

---

## 全流程概览

```
PDB 下载 → PyMOL 预处理 → CHARMM-GUI 建模 → 上传 Longleaf
    → cMD 运行 → PyMOL 定位相互作用 + Amber 编号映射
    → LiGaMD3 参数配置 → Sigma 优化 → Production Run → 数据分析
```

---

## 第一步：PDB 结构下载与 PyMOL 预处理

### 1.1 下载 PDB 结构

从 RCSB PDB 网站下载 CIF 格式文件：

```
https://www.rcsb.org/structure/[PDB_ID]
```

例如 `https://www.rcsb.org/structure/5OCI`。

### 1.2 PyMOL 加载与清理

```
5J20
```

### 1.3 给配体加氢

配体在 PDB 晶体结构中通常缺少氢原子，必须手动补充：

```
PyMOL> h_add [配体选区]
```

或通过菜单：选中配体 → **Action → Hydrogens → Add**。

### 1.4 导出配体文件（mol2 格式）

用 PDB 中配体的残基名称来选中配体，然后保存为 mol2 文件：

```
# 以 5OCI 为例，配体名称为 9R8
PyMOL> select ligand, resn 9R8
PyMOL> save ligand.mol2, ligand
```

> **注意**：不同 PDB 体系的配体残基名称不同，需在 PDB 网站或结构文件中确认。

### 1.5 导出复合物 PDB 文件

将加氢后的蛋白-配体复合物整体保存为 PDB 文件：

```
PyMOL> save complex.pdb, all
```

### 1.6 修改 PDB 编号（文本编辑器操作）

用文本编辑器打开 `complex.pdb`，进行以下检查和修改：

- 检查配体和蛋白部分的残基编号是否连续、无冲突
- 配体的残基编号需要与蛋白部分衔接（不能重叠）
- 确保原子编号从 1 开始连续编排

> **为什么要做这一步**：CHARMM-GUI 和后续 Amber 工具依赖正确的编号进行拓扑构建。编号冲突会导致力场分配错误或模拟崩溃。

### 1.7 [CRITICAL] CHARMM-GUI 报错排雷指南（基于11个HSP90新体系的血泪教训）

在上传 `complex.pdb` 和配体 `_ligand_H.mol2` 后，如果在后续步骤遇到以下报错，请务必核对这三大巨坑：

**坑一：配体力场报错 (Antechamber Failed)**
* **症状**：在 CHARMM PDB 页面，勾选生成拓扑后报错 `Ligand FF parameterization failed` 或 `Antechamber Failed`。
* **原因**：配体中含有卤素原子（如氯原子/溴原子）。PyMOL 从 CIF 或 RCSB 获取时，会把这些元素强制写成大写 `CL` 或 `BR`。GAFF2 力场引擎**严格区分大小写**，根本不认识大写的卤素，从而导致参数化直接崩溃！
* **解决**：打开 PDB 检查元素列（第 77-78 列），将大写的 `CL` 或 `BR` 改为 `Cl` 或 `Br`。如果 MOL2 中的 Tripos 类型列（第 6 列）也是大写，同样需要改过来（纯 CIF 提取的 MOL2 通常是对的，但 PDB 元素列必定是错的大写）。

**坑二：异常终止，无坐标 (Undefined coordinates)**
* **症状**：Step 1 PDB Reader 完成后能量爆炸，或在 PBC Setup 阶段报错 `ABNORMAL TERMINATION: Undefined coordinates`。
* **原因 A（RCSB 坐标漂移）**：你贪图方便直接用 `rcsb.org` 或 API 下载了配体的 ideal MOL2！注意：官网下载的配体坐标是以 `[0.0, 0.0, 0.0]` 为原点的，并不是三维晶体口袋里的真实坐标！当你把蛋白口袋和原点处的配体组合上传给 CHARMM-GUI 时，系统全乱套了。
* **原因 B（Altlocs 重叠）**：直接从 PDB 导出了带有多构象（如 altA 和 altB）的复合体，导致同一个氨基酸有两个互相重叠的坐标，CHARMM-GUI 直接读取到重复原子从而崩溃（绝不是因为 occupancy < 1.0 的问题，合法的非 1 占有率只要不重叠其实是能过的）。
* **唯一正确的操作流**：**绝对不要从外部下载配体坐标！** 永远只能从下载的 `.cif` 或 `.pdb` 复合物中（剔除次要 altloc 后）选定配体，原位运行 `cmd.extract` 和 `cmd.h_add`，这样切出来的配体才是在原生蛋白口袋里的。

**坑三：读取到多余链，配体错位**
* **症状**：PDB Reader 读出四五条链（如 PROA, PROB 和 HETA, HETB 等），或者后续构象全错。
* **原因**：原始晶体的非对称单元本来就包含了多个多聚体。
* **解决**：必须在 PyMOL 中明确提取一对单链（如 `select chain A and ...`），将其他无用的多聚链彻底删除后再导出。

---

## 第二步：CHARMM-GUI 建模（含具体参数）

### 2.1 进入 CHARMM-GUI

网址：`https://www.charmm-gui.org/`

选择 **Solution Builder**。

### 2.2 PDB Info 页面

上传处理好的 PDB 文件（`complex.pdb`）。CHARMM-GUI 会自动识别：

- **Title**: 对应的 PDB ID（如 5OCI_FINAL）
- **PDB ID**: 5OCI_FINAL
- **Type**: Protein

### 2.3 CHARMM PDB 页面 — 配体处理（关键配置）

这是整个 CHARMM-GUI 流程中最需要注意的页面。以 5OCI 的配体 9R8 为例：

**Reading Hetero Chain Residues 部分**：

| 设置项                           | 值                                                    | 说明                                                  |
| -------------------------------- | ----------------------------------------------------- | ----------------------------------------------------- |
| ☑ Reading Hetero Chain Residues | 勾选                                                  | 启用配体识别                                          |
| 9R8 → Rename to                 | `9R8`                                               | 保持配体残基名不变                                    |
| 配体处理方式                     | ● Use Antechamber to generate CHARMM top & par files | **选这个**，用 Antechamber 自动生成配体力场参数 |
| 配体文件来源                     | ● the MOL2 file uploaded from →`9R8.mol2`         | **上传之前 PyMOL 导出的 mol2 文件**             |
| atom type                        | `gaff2`                                             | GAFF2 原子类型（通用有机分子力场）                    |
| charge method                    | `AM1-BCC`                                           | AM1-BCC 电荷计算方法                                  |

**Terminal group patching 部分**：

| 设置项          | 值     |
| --------------- | ------ |
| PROA First      | ACE    |
| PROA Last       | CT3    |
| Cyclic peptide? | 不勾选 |

> **为什么选 Antechamber + GAFF2 + AM1-BCC**：这是 Amber 力场体系下处理小分子配体的标准组合。GAFF2 是通用原子力场第二代，AM1-BCC 是快速且准确度可接受的原子电荷计算方法。

### 2.4 Solvator 页面 — 溶剂化设置

**Waterbox Size Options**：

| 设置项              | 值                                   | 说明                       |
| ------------------- | ------------------------------------ | -------------------------- |
| 选择方式            | ● Fit Waterbox Size to Protein Size | 根据蛋白大小自动适配水盒子 |
| Waterbox type       | Rectangular                          | 矩形水盒子                 |
| Enter Edge Distance | `10.0` Å                          | 蛋白到盒子边缘的最小距离   |

**Add Ions**：

| 设置项             | 值              | 说明                    |
| ------------------ | --------------- | ----------------------- |
| ☑ Include Ions    | 勾选            | 添加离子                |
| Ion Placing Method | Monte-Carlo     | 蒙特卡洛放置法          |
| ☑ Basic Ion Types | 勾选            |                         |
| 离子类型           | NaCl            | 氯化钠                  |
| Concentration      | `0.15` M      | 0.15 M NaCl（生理浓度） |
| 模式               | ● Neutralizing | 中和体系净电荷          |

> **5OCI 体系的离子数结果**：Na⁺ = 38，Cl⁻ = 31（CHARMM-GUI 自动计算）。

### 2.5 PBC Setup 页面

此页面自动处理周期性边界条件。关键生成文件包括：

- `step2_solvator.pdb` — 溶剂化后的 PDB 结构
- `step3_pbcsetup.pdb` — PBC 设置后的最终结构（**可在这里 view structure 确认**）
- `checkfft.py` — FFT 网格检查脚本

### 2.6 Input Generator 页面 — 力场与输出格式（关键配置）

**Force Field Options**：

| 设置项   | 值              | 说明         |
| -------- | --------------- | ------------ |
| 力场类型 | **AMBER** | 必须选 AMBER |

**AMBER Force Fields（各组分的力场选择）**：

| 组分    | 力场             | 说明                            |
| ------- | ---------------- | ------------------------------- |
| Protein | **FF14SB** | Amber 蛋白质力场（标准选择）    |
| DNA     | OL15             | DNA 力场（本体系不涉及）        |
| RNA     | OL3              | RNA 力场（本体系不涉及）        |
| Glycan  | GLYCAM_06j       | 糖力场（本体系不涉及）          |
| Lipid   | Lipid21          | 脂质力场（本体系不涉及）        |
| Water   | **TIP3P**  | TIP3P 水模型（Amber 标准配对）  |
| Ligand  | **GAFF2**  | 配体使用 GAFF2（与 2.3 节对应） |

**其他选项**：

| 设置项                       | 值     |
| ---------------------------- | ------ |
| Hydrogen mass repartitioning | 不勾选 |
| 12-6-4 ion                   | 不勾选 |

**Input Generation Options**：

| 设置项                                     | 值                 |
| ------------------------------------------ | ------------------ |
| ☑ AMBER                                   | **必须勾选** |
| GROMACS / OpenMM / NAMD / GENESIS / Tinker | 不勾选             |

**Equilibration Input Generation Options**：

| 设置项          | 值             |
| --------------- | -------------- |
| ● NVT Ensemble | 平衡阶段用 NVT |

**Dynamics Input Generation Options**：

| 设置项          | 值             |
| --------------- | -------------- |
| ● NPT Ensemble | 生产阶段用 NPT |
| Temperature     | `300` K      |

### 2.7 下载 CHARMM-GUI 输出

生成的输出目录结构：

```
charmm-gui-XXXXXXX/
├── amber/
│   ├── step3_input.parm7          ← 拓扑文件（★ 关键文件）
│   ├── step3_input.rst7           ← 初始坐标（★ 关键文件）
│   ├── step3_input.pdb            ← PDB 格式坐标（用于后续 PyMOL 查看）
│   ├── step4.0_minimization.mdin  ← 最小化输入
│   ├── step4.1_equilibration.mdin ← 平衡输入
│   ├── step5_production.mdin      ← 生产运行输入
│   ├── README                     ← 需要改名为 run-cmd.csh
│   └── ...
├── 9R8/                           ← 配体参数文件（以 5OCI 的 9R8 为例）
│   ├── 9r8/9r8.rtf                ← 配体拓扑
│   ├── 9r8/9r8_g.rtf              ← 配体拓扑（另一种格式）
│   └── 9r8/9r8.prm               ← 配体力场参数
└── ...
```

---

## 第三步：上传到 Longleaf 并运行 cMD

### 3.1 目录结构

```
/users/l/i/liualex/Miao_lab/HSP90_new/
├── [PDB_ID]/
│   ├── cMD/
│   │   └── charmm-gui-XXXXXXX/
│   │       └── amber/          ← CHARMM-GUI 下载的文件
│   ├── equilibration/          ← LiGaMD3 equilibration（后续）
│   └── production/             ← Production run（后续）
```

### 3.2 上传文件

```bash
scp -r charmm-gui-XXXXXXX/ liualex@longleaf.unc.edu:/users/l/i/liualex/Miao_lab/HSP90_new/[PDB_ID]/cMD/
```

### 3.3 ★ 核心格式修正：PDB4Amber 转化坐标

这是避免后续坐标残基读取错乱的**最关键步骤**！CHARMM-GUI 吐出的 `step3_input.pdb` 往往带有非标准标识，我们必须利用 AMBER 套件将其清洗重排：

```bash
cd /users/l/i/liualex/Miao_lab/HSP90_new/[PDB_ID]/cMD/charmm-gui-XXXXXXX/amber/

# 必须加载 amber22 环境（加载较新版本可能会报 Shape mismatch 或者缺失库错误）
source /proj/ymiaolab/software/amber22/amber.sh

# 运行转换，生成纯净正统的 amber.pdb
pdb4amber -i step3_input.pdb -o amber.pdb
```

> **排坑说明**：程序会自动清洗非标准格式，并生成连续统一的原生原子序号。**之后所有查看体系相互作用的操作，都必须绝对依赖这个新生成的 `amber.pdb`！**

### 3.4 两处 CUDA 配置（都必须做）

| 位置                   | 作用                                  |
| ---------------------- | ------------------------------------- |
| **sub-cmd.slum** | 加载 CUDA 模块 + 确认 pmemd.cuda 可用 |
| **run-cmd.csh**  | 脚本开头添加 `which pmemd.cuda`     |

### 3.5 创建 `sub-cmd.slum`（Slurm 提交脚本）

在 `amber/` 目录下创建（**只改 job-name**）：

```bash
#!/bin/bash

#SBATCH --job-name=cMD-5J86         # ← 改为对应体系名称
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G                   # ← 重点：这里用 16G 可以避免 L40 显卡部分兼容性报错
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
```

### 3.6 修改 `run-cmd.csh` 执行脚本 → run-cmd.csh

```bash
# 改名
mv README run-cmd.csh
chmod +x run-cmd.csh
```

在 `run-cmd.csh` 开头（`#!/bin/csh` 之后）添加一行：

```csh
#!/bin/csh
which pmemd.cuda          # ← 添加这一行
#
# Generated by CHARMM-GUI ...
```

**⚠️ 并且一定要修改 `set amber` 这一行，去掉任何多余空格，严格保持如下格式（参考学长截图）：**

```csh
set amber = pmemd.cuda# set amber = "mpirun -np 4 pmemd.MPI"
```

**run-cmd.csh 会自动按顺序执行**：

1. step4.0_minimization — 能量最小化
2. step4.1_equilibration — 系统平衡
3. step5_1 ~ step5_10 — 10 轮 production（共 200 ns cMD）

### 3.7 提交 cMD 任务

```bash
cd /users/l/i/liualex/Miao_lab/HSP90_new/[PDB_ID]/cMD/charmm-gui-XXXXXXX/amber/
sbatch sub-cmd.slum
```

### 3.8 检查 cMD 是否完成

```bash
squeue -u liualex                # 查看任务状态
ls -la step5_10.rst7             # 存在 = cMD 完成
cat mdinfo                       # 查看模拟进度（完成百分比和剩余时间）
```

---

## 第四步：PDB → Amber 格式编号核对（★ 关键步骤）

这一步是整个流程中最容易出错、也是录音中反复强调的环节。

### 4.1 为什么需要编号核对

从原始 PDB 到 Amber 的转换过程中，**原子编号（atom serial）和残基编号（residue number）会发生变化**。LiGaMD3 的输入参数需要的是 Amber 编号体系中的原子序号，不是原始 PDB 的编号。

> **来自录音**（Zhenpeng 解释）：
> "因为这个蛋白质的残基具体序号是七十八号位的……然后这个具体的原子数……这个是在 Amber 里面的具体原子序号……这个是残基的序列数字。78 还是在后面，但是我们要的是这个（原子序号）。"

### 4.2 残基编号 vs 原子编号：两套不同的编号体系

| 概念                                 | 含义                           | 示例                                     |
| ------------------------------------ | ------------------------------ | ---------------------------------------- |
| **残基编号（Residue Number）** | 蛋白序列中氨基酸的位置编号     | ASP**78** = 第 78 号残基是天冬氨酸 |
| **原子编号（Atom Serial）**    | Amber 文件中每个原子的连续序号 | OD2 的 atom serial =**1251**       |

**一个残基包含多个原子**，所以残基号 78 下面可能有十几个不同的原子，每个原子有自己唯一的 atom serial。

> **来自录音**（Li 的疑问和 Zhenpeng 的回答）：
> Li: "等一下，这两个东西它为什么会不一样？它不应该一样才对吗？"
> Dharma: "这个是残基的序列数字。78 还是在后面，但是我们要的是这个。"
> Dharma: "所以我是提前记录下，OD2，1251，是吧？78，1251。"

### 4.3 打开 Amber PDB 文件，核对三个关键数字

**重要提醒**：使用文本编辑器打开我们刚才在 3.3 步生成的 **`amber.pdb`** 文件（**绝对不要**看 `step3_input.pdb` 或 `complex.pdb`，因为那里的原子编号没有重排），确认以下三个体系规模参数：

| 参数                       | 含义                     | 如何获取                                    | 5OCI 示例值     |
| -------------------------- | ------------------------ | ------------------------------------------- | --------------- |
| **End protein atom** | 纯蛋白的最后一个原子序号 | 在 amber.pdb 中找蛋白最后一行的 atom serial | **3267**  |
| **natoms**           | 蛋白 + 配体的总原子数    | 蛋白最后原子 + 配体原子数                   | **3329**  |
| **natoms_max**       | 整个体系总原子数         | amber.pdb 拉到最后一行的 atom serial        | **36200** |

> **来自录音**：
> "你看这个拉到最后，因为这总共是三万六千二百零五行。"
> "3267 是吧……这个就是单纯的蛋白的 end protein atom number。"
> "这个 and atoms 的是整个的就是蛋白和配体他们两个加起来总共有多少个。"

---

## 第五步：用 PyMOL 定位蛋白-配体关键相互作用（★ 核心环节）

**目标**：在 PyMOL 中可视化蛋白-配体的极性接触/氢键，确定要监控的原子对，然后把这些原子映射到 Amber 编号体系中，最终写入 LiGaMD3 参数。

**这就是录音中说的"CHARMM-GUI 产物 → PyMOL 参考 → 回填到 LiGaMD3 的 cMD 参数"的整条链路。**

### 5.1 从服务器下载并加载 `amber.pdb` 到本地 PyMOL

**关键提醒**：您需要在 cMD 准备阶段，将刚刚生成的 `amber.pdb` 从服务器下载到您自己的本地电脑中用 PyMOL 打开！不能用旧格式 PDB！

```
PyMOL> load amber.pdb
```

### 5.2 查找 Polar Contacts（对应 PyMOL 截图操作）

操作路径：

1. 在 PyMOL 右侧面板中选中配体（或整个 selection）
2. 点击 **Action → Find → polar contacts**
3. 在弹出的子菜单中选择：
   - **to other atoms in object** — 查找配体与蛋白之间的极性接触
   - **to others excluding solvent** — 排除溶剂的极性接触
   - **to any atoms** / **to any excluding solvent** — 更广泛的搜索
4. PyMOL 会用黄色虚线显示所有检测到的极性接触/氢键

### 5.3 选择要监控的关键相互作用对

从 PyMOL 显示的所有 polar contacts 中，**挑选一条最关键、最稳定、最能代表结合状态的相互作用**。

**选择标准**（实验室可复用的规则）：

- 配体上功能团参与的直接氢键（优先于水桥介导的）
- 与催化残基或关键口袋残基的相互作用
- 几何上接近"锚点"的相互作用（不容易因构象变化而丢失）

> "如果很重要的话我们就监控它。如果这个你只监控 RMSD 也一样，因为你 RMSD 很大的话……这个距离也会大。"

### 5.3.5 进阶技巧：配合“鼠标点击找氢键”的 ASP 专注过滤法（Sequence 视图法）

如果你更习惯用完全纯图形界面（GUI）的操作来找特定的 ASP 残基，这里有一个非常直观、所见即所得的“点点点”工作流：

**1. 载入与初始清理：**

- 将 `amber.pdb` 拽入 PyMOL。
- 在右下角命令行输入并执行（或通过右侧菜单点击 Hide）：`hide everything`
- `show cartoon, polymer`
- `show sticks, organic`

**2. 寻找极性接触：**

- 在右侧菜单点击配体（通常叫 organic）的 **A (Action) → Find → polar contacts → to others excluding solvent**。
- 这时屏幕上会产生黄色的相互作用虚线（可能连到了很多残基）。

**3. 通过 Sequence 视图精准提取目标 ASP：**

- 点击 PyMOL 右下角的 **"S"**（或者顶部菜单的 Display → Sequence），在屏幕上方调出氨基酸序列条。
- 在序列条中滑动，找到你要监控的关键位置（比如对应你的 `ASP 79`）。
- **用鼠标左击**拖拽选中序列上的 `79` 号和 `80` 号残基（或者直接点 `79`）。
- 此时右侧会多出一个 `(sele)` 的选区。点击 `(sele)` 旁边的 **S (Show) → sticks**。
- 现在，你的视野里就明确出现了这根 ASP 79 的氨基酸侧链，并且你能清楚地看到刚才生成的极性虚线是否连在它上面！

> **⚠️ 注意一个小细节（关于你点的 CG 原子）：**
> 你刚刚在 PyMOL 点击了 ASP 79 的 `CG`（Gamma 碳原子）。但在实际跑 MD 监控氢键时，通常我们监控的是**直接参与氢键的氧原子**（也就是 `OD1` 或 `OD2`），而不是碳原子。所以最好用鼠标点一下连着黄线的那颗**红色的氧原子**。

### 5.4 将 PyMOL 看到的原子映射到 Amber 原子序号

完全正确！你在 PyMOL 里看到并确认了它们是哪个残基的哪个原子后，**下一步就是打开 `amber.pdb` 文本文件去找它对应的行数（确切地说是 Atom Serial），然后去修改 `md.in`**。

**这是最关键的映射步骤**。PPT 截图右下角明确标注了映射关系：

```
蛋白侧：ASP/78 — OD2 — 1251    （残基 78 的 OD2 氧原子，Amber 原子序号 1251）
配体侧：9R8/210 — O2 — 31      （配体残基 210 的 O2 氧原子，配体内原子序号 31）
```

#### 5.4.1 获取蛋白侧原子序号（atom_p）

在 amber.pdb 文件中搜索目标残基和原子名：

```
ATOM   1261  OD2 ASP    79      xx.xxx  yy.yyy  zz.zzz  ...
           ↑                                ← 这个 1261 就是你要写入 LiGaMD3 的 atom_p（绝对序号）
```

**⚠️ 关键陷阱**：你不能把 "79" 写成 atom_p。79 是残基号，1261 才是原子序号。

> **来自录音**（Dharma 强调）：
> "就记住，P 是 protein，L 是 ligand。"
> "这个OD2是吧，这个的话你就得记录这前面的序号就OK。"

#### 5.4.2 获取配体侧原子序号（atom_l）

`atom_l` 是目标原子在配体内部的**相对序号**，不是 PDB 文件的绝对序号。

**计算公式**：`atom_l = 目标原子绝对序号 − 配体第一个原子绝对序号 + 1`

**操作步骤**：

1. 在 `amber.pdb` 中找配体第一个原子的序号（开头那行的第 2 列数字）
2. 找目标氧原子的绝对序号
3. 相减加 1 得到相对序号

**5OCI 的验证**：

- 配体 9R8 第一个原子 = 3268，O2 原子 = 3298 → `atom_l = 3298 - 3268 + 1 = 31` ✅

**注意**：如果目标氧原子恰好是配体的第一个原子（如 5J2X 的 6DL O2），则 `atom_l = 1`。

#### 5.4.3 记录格式（建议养成习惯）

每次做完映射后，用以下格式记录：

```
体系: 5OCI
蛋白侧: ASP/78 — OD2 — atom_p = 1251
配体侧: 9R8/210 — O2 — atom_l = 31（相对序号）
距离阈值: dblig = 2.6 Å
```

#### 5.4.4 各新体系汇总（2026-02-22）

| 体系 | 配体   | atom_p           | atom_l   | 说明                     |
| ---- | ------ | ---------------- | -------- | ------------------------ |
| 5J20 | 6FJ O1 | 1261 (ASP79 OD2) | 28       | O1=3305, 配体第一=3278   |
| 5J2X | 6DL O2 | 1261 (ASP79 OD2) | 1        | O2 就是配体第一个原子    |
| 5J64 | 6G7 O2 | 1266 (ASP79 OD2) | 1        | O2 就是配体第一个原子    |
| 5J82 | 6GV O2 | 1266 (ASP79 OD2) | 28       | O2=3310, 配体第一=3283   |
| 5J86 | 6GW O1 | 1266 (ASP79 OD2) | 28       | O1=3310, 配体第一=3283   |
| 5J27 | 6FF ?? | 待 PyMOL         | 待 PyMOL | 配体 301，edpro2atm=3304 |

---

## 第六步：LiGaMD3 参数配置（★ 核心参数详解）

这一节对应 PPT 截图中"LiGaMD3 for HSP-5OCI"的所有参数，按功能分组详细解释。

### 6.1 体系规模相关参数

这些参数来自第四步的编号核对结果：

| 参数           | 值（5OCI）      | 含义                               | 是否需要改       |
| -------------- | --------------- | ---------------------------------- | ---------------- |
| `natoms`     | 3329            | 蛋白 + 配体原子数                  | 换体系时要核对   |
| `natoms_max` | 36200           | 整个体系总原子数                   | 换体系时要核对   |
| `ntwx`       | 1000            | 轨迹输出频率（每多少步写一次坐标） | 通常不变         |
| `ntwprt`     | = natoms = 3329 | 写轨迹时输出的复合物原子数范围     | 跟 natoms 一起改 |
| `igamd`      | 28              | GaMD 模式参数（默认值）            | **不变**   |

### 6.2 时间/步数相关参数 — "取大"策略

这是实验室模板的核心设计思想：**用体系规模（natoms_max）推导出一个保守的时间基准（ntave），然后所有时间参数都按 ntave 的倍数计算。**

**推导链条**（PPT 截图中完整展示）：

```
ntave = 4 × natoms_max = 4 × 36200 = 144800 ≈ 取大到 200000
```

> **来自录音**（Zhenpeng 解释"取大"逻辑）：
> "它会得到一个数，然后我们把它取大。其实你跑的所有体系里面应该都是这个数。"
> "这是不变的。"
> "因为你想想我这已经取大很多，它体积只要低于五万个或者五万多一点都没关系，我们都不变这个。所以导致这些参数都是不变的。"

**基于 ntave 推导的各个时间参数**：

| 参数          | 公式                           | 计算结果           | 含义                     | 是否需要改                     |
| ------------- | ------------------------------ | ------------------ | ------------------------ | ------------------------------ |
| `ntave`     | 4 × natoms_max → 取大        | **200000**   | 统计平均窗口（时间基准） | **通常不变**（取大策略） |
| `ntcmd`     | 5 × ntave × 2 = 10 × 200000 | **2000000**  | cMD 统计收集步数         | 不变                           |
| `ntcmdprep` | 2 × ntave = 2 × 200000       | **400000**   | cMD 准备步数             | 不变                           |
| `ntebprep`  | 2 × ntave = 2 × 200000       | **400000**   | GaMD 平衡准备步数        | 不变                           |
| `nteb`      | 45~100 × ntave                | **20000000** | GaMD 平衡步数            | 不变                           |
| `nstlim`    | nteb + ntcmd                   | **22000000** | 总步数                   | 不变（equilibration阶段）      |

**换算到物理时间**：nstlim = 22000000，dt = 0.002 ps，总时间 = 22000000 × 0.002 / 1000 = **44 ns**。

> **来自录音**（Zhenpeng 反复强调"取大后不用改"）：
> "因为你想想我这已经取大很多……所以导致这些参数都是不变的。所以这就是为什么说折 shell 改结构就 OK。"
> "这个就等于是……你就不管，这个不变。这个的话其实我们这是大差不差都是不变的。"
> "其实这个是 cMD 跑的时长。"

**但是**，如果换到体系规模差异很大的蛋白（如 natoms_max 远超 50000），这些参数需要根据新的 ntave 重新计算。对于 HSP90 这一系列体系，由于蛋白相同、只是配体不同，体系规模大差不差，所以这些参数基本都不用改。

### 6.3 蛋白范围与配体 Mask 参数

| 参数          | 值（5OCI） | 含义                            | 是否需要改                                 |
| ------------- | ---------- | ------------------------------- | ------------------------------------------ |
| `Bgpro2atm` | 1          | 蛋白区域起始原子序号            | **不变**（永远从 1 开始）            |
| `Edpro2atm` | 3267       | 蛋白区域结束原子序号            | **可能变**（蛋白末端原子号）         |
| `Timask1`   | ':210'     | 配体的 Amber mask（残基号 210） | **可能变**（不同体系配体残基号不同） |
| `Scmask1`   | ':210'     | 配体的 soft core mask（同上）   | **可能变**（与 Timask1 一致）        |

> **来自录音**（关于 mask 的解释）：
> Zhenpeng: "蛋白质相当于是残基数嘛，然后这个蛋白……它是一个蛋白，所以它肯定不可能变。它变的只能是它原子的位置。"
> "你就像你看这上面一个残基……所以它就指定就是你所有的这就指定一个它就是一个整体一个配体。"

**Timask1 和 Scmask1 的含义**：

- `Timask1 = ':210'` — 指定配体在 Amber 体系中的残基号为 210，用于 thermodynamic integration 计算
- `Scmask1 = ':210'` — 指定使用 soft core 势函数描述的配体原子（用 ambmask 格式）

**⚠️ 换体系时注意**：配体的残基号不一定还是 210，需要在 amber.pdb 中确认配体的实际 resid。

### 6.4 蛋白-配体相互作用监控参数（★ 最重要的部分）

这些参数直接来自第五步 PyMOL 定位的结果：

| 参数       | 值（5OCI）     | 含义                               | 是否需要改                           |
| ---------- | -------------- | ---------------------------------- | ------------------------------------ |
| `ibblig` | 1              | 配体索引（模板固定）               | **不变**                       |
| `nlig`   | 1              | 配体数量                           | **不变**（单配体体系）         |
| `atom_p` | **1251** | 蛋白侧监控原子的 Amber 序号        | **★ 必须根据 PyMOL 结果更新** |
| `atom_l` | **31**   | 配体侧监控原子的 Amber 序号        | **★ 必须根据 PyMOL 结果更新** |
| `dblig`  | **3.0**  | 距离阈值（Å），判定接触存在的标准 | 可微调（一般 2.5-3.5）               |

> **来自录音**（关于 dblig 的灵活性）：
> Dharma: "没有这个你其实这个你可以变大一点也无所谓就不用那么节俭。"
> "这一行完全是可以不要的。但对于监控 RMSD 就 OK。"

**这组参数的作用**：cMD/GaMD 运行时，程序会实时输出 atom_p 和 atom_l 之间的距离随时间的变化。你可以用这个距离判断：

- 结合是否保持（距离稳定在 dblig 附近）
- 是否发生解离（距离急剧增大）
- 是否出现关键构象变化

### 6.5 参数变化总结：换体系时需要核对什么

对于 HSP90 同一系列不同配体的体系，切换时需要重新确认的参数分为三类：

**第一类：一定会变的（每个体系都必须重新确认）**

| 参数                      | 原因                                       |
| ------------------------- | ------------------------------------------ |
| `atom_p`                | 不同配体可能与不同蛋白残基形成关键相互作用 |
| `atom_l`                | 不同配体的原子编号不同                     |
| `Timask1` / `Scmask1` | 配体残基号可能不同                         |

**第二类：可能会变的（需要核对，但同系列通常不变）**

| 参数                        | 原因                           |
| --------------------------- | ------------------------------ |
| `Edpro2atm`               | 蛋白末端原子号可能因链不同而变 |
| `natoms` / `natoms_max` | 配体大小不同导致微小差异       |
| `dblig`                   | 不同相互作用的典型距离可能不同 |

**第三类：不需要改的（"取大"策略保障）**

所有基于 ntave 推导的时间参数（ntave, ntcmd, nteb, ntcmdprep, ntebprep, nstlim）、igamd、ntwx、Bgpro2atm、ibblig、nlig。

> **来自录音**（Dharma 总结）：
> "这些可能是不一样的，这个可能不一样，这跟我们可能在不同的里面要稍微改一下。然后其余的这些其实都是为了计算这些的，但是这些的话基本都不用。"

---

## 第七步：LiGaMD3 Equilibration

### 7.1 创建目录并复制文件

```bash
cd /users/l/i/liualex/Miao_lab/HSP90_new/[PDB_ID]/
mkdir -p equilibration/e1_166211

# 从 cMD 复制关键文件
cp cMD/charmm-gui-XXXXXXX/amber/step3_input.parm7 equilibration/e1_166211/
cp cMD/charmm-gui-XXXXXXX/amber/step5_10.rst7 equilibration/e1_166211/
```

### 7.2 创建 md.in

**注意**：最后的 `/` 结束符不能漏，否则会报 `Fortran runtime error: End of file`。

```
 &cntrl
    imin = 0, irest = 1, ntx = 5,
    nstlim = 22000000,
    dt = 0.002,
    ntc = 2, ntf = 2,
    ntt = 3, gamma_ln = 1.0, temp0 = 310.15,
    ntb = 2, ntp = 1, barostat = 2,
    ntwx = 5000, ntwr = 5000, ntpr = 5000,
    cut = 9.0,
    igamd = 28,
    irest_gamd = 0,
    ntcmd = 2000000,
    nteb = 20000000,
    ntave = 200000,
    sigma0P = 2.5,         # ← 需要优化的关键参数
    sigma0D = 6.0,
    sigma0B = 6.0,
    iEP = 2, iED = 1, iEB = 1,
    ibblig = 1, nlig = 1,
    atom_p = 1251,         # ← 根据体系调整（来自 PyMOL 映射）
    atom_l = 31,           # ← 根据体系调整（来自 PyMOL 映射）
    dblig = 2.9
 /
```

### 7.3 创建 run-equil.pbs

```bash
#!/bin/bash

#SBATCH --job-name=5J86-e2.5        # ← 修改体系名和 sigma 值
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=96:00:00
#SBATCH --partition=l40-gpu
#SBATCH --output=log.%x.%j
#SBATCH --gres=gpu:1
#SBATCH --qos=gpu_access

workfolder=$(pwd)

module purge
module load gcc/11.2.0 cuda/11.8

source /proj/ymiaolab/software/amber24/amber.sh

module purge
module load amber/24p3

cd "$workfolder"

which pmemd.cuda

pmemd.cuda -O -i md.in -p step3_input.parm7 -c step5_10.rst7 -o md-1.out -x md-1.nc -r gamd-1.rst -gamd gamd-1.log
```

> **来自录音**（关于复用 equilibration）：
> Dharma: "因为你之前我也你有几个文件是吧，你后面你新准备的过后你跑完 cMD 过后你就把之前的这些 equilibrium copy 过去，然后你就改这几个具体的参数。"
> Herbert: "其实你基本上改不了几个参数，我上次跟你说的你改那几个就 OK。"

---

## 第八步：Sigma_OP 参数优化

### 8.1 并行测试多个 sigma_OP

```bash
cd /users/l/i/liualex/Miao_lab/HSP90_new/[PDB_ID]/equilibration/

for sigma in 1.0 1.5 2.0 2.5 3.0 3.5 4.0; do
    cp -r e1_166211 e1_sigma${sigma}
    # 修改 e1_sigma${sigma}/md.in 中 sigma0P = ${sigma}
    # 修改 e1_sigma${sigma}/run-equil.pbs 中 job-name
    # 确保 md.in 末尾有 /
    cd e1_sigma${sigma} && sbatch run-equil.pbs && cd ..
done
```

### 8.2 选择最优 sigma_OP

**核心原则**：选 equilibration 中**不解离**的最大 sigma_OP。

- 让解离发生在 production run 中，才能捕捉完整的解离过程数据
- 如果 equilibration 就解离了，production 就捕捉不到完整事件了

| 现象                                    | 判断                               |
| --------------------------------------- | ---------------------------------- |
| RMSD 低、distance 稳定                  | sigma 不够大，可以增大             |
| **RMSD 稳定（最大的这个 sigma）** | **★ 选这个值跑 production** |
| RMSD 剧增、distance 增大                | sigma 太大，equilibration 已解离   |

**已确定的值**：

- 5OCI: **sigma_OP = 2.5**（3.0 时 equilibration 末期已解离）
- 5ODX: **sigma_OP = 3.5**（4.0 时 equilibration 中期已解离）

---

## 第九步：Production Run

### 9.1 核心原则

- Production 的 md.in 和 equilibration **大部分参数相同**
- 区别仅在于：不同目录 + 不同 job-name + `ig=-1` 自动产生不同随机种子
- 每个体系跑 **6 个 replica**，最终筛选 3 个有解离事件的用于分析
- 目录命名：`[sigma]_[replica编号]`，如 `2.5_1`、`3.5_3`

### 9.2 Production md.in 与 Equilibration 的 8 个参数差异

| 参数           | Equilibration    | Production                  | 原因                             |
| -------------- | ---------------- | --------------------------- | -------------------------------- |
| `nstlim`     | 22000000 (44 ns) | **50000000 (100 ns)** | 更长采样时间                     |
| `irest_gamd` | 0                | **1**                 | 重启 GaMD，使用已有的 boost 参数 |
| `ntcmd`      | 2000000          | **0**                 | 跳过 cMD 统计                    |
| `nteb`       | 20000000         | **0**                 | 跳过 GaMD 平衡                   |
| `ntcmdprep`  | 400000           | **0**                 | 无需准备阶段                     |
| `ntebprep`   | 400000           | **0**                 | 无需准备阶段                     |
| `ntpr`       | 5000             | **500**               | 能量输出更频繁（每 1 ps）        |
| `ntwx`       | 5000             | **500**               | 轨迹输出更频繁（每 1 ps）        |

其余参数（sigma0P、softcore、配体 mask、atom_p、atom_l 等）保持与 equilibration 一致。

### 9.3 需要复制的 6 个文件

从 equilibration 的最优 sigma 目录复制到每个 production replica：

| 文件                  | 是否修改                            | 说明                                      |
| --------------------- | ----------------------------------- | ----------------------------------------- |
| `md.in`             | **改 8 个参数**（见 9.2）     | Production 跳过 GaMD 平衡                 |
| `run-equil.pbs`     | **改 job-name + `-c` 参数** | `-c` 改为 `gamd-1.rst`                |
| `step3_input.parm7` | 不改                                | 拓扑文件                                  |
| `step5_10.rst7`     | 不改                                | cMD 坐标（备用）                          |
| `gamd-1.rst`        | 不改                                | equilibration 终点坐标 → production 起始 |
| `gamd-restart.dat`  | 不改                                | GaMD boost 参数，`irest_gamd=1` 读取    |

### 9.4 创建目录并复制

以 5OCI（最优 sigma_OP = 2.5）为例：

```bash
cd /users/l/i/liualex/Miao_lab/HSP90_new/5OCI/
SRC=equilibration/e1_sigma2.5

for i in 1 2 3 4 5 6; do
    mkdir -p production/2.5_${i}
    cp ${SRC}/md.in production/2.5_${i}/
    cp ${SRC}/step3_input.parm7 production/2.5_${i}/
    cp ${SRC}/step5_10.rst7 production/2.5_${i}/
    cp ${SRC}/gamd-1.rst production/2.5_${i}/
    cp ${SRC}/gamd-restart.dat production/2.5_${i}/
done

# 然后修改每个 replica 的 md.in（见 9.2 的 8 个参数变更）
# 以及修改 run-equil.pbs 的 job-name 和 -c 参数
```

### 9.5 Production run-equil.pbs

每个 replica 只需修改 **job-name**，**`-c` 用 gamd-1.rst**：

```bash
#!/bin/bash

#SBATCH --job-name=5OCI-2.5_1      # ← 格式: [PDB_ID]-[sigma]_[replica]
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=96:00:00
#SBATCH --partition=l40-gpu
#SBATCH --output=log.%x.%j
#SBATCH --gres=gpu:1
#SBATCH --qos=gpu_access

workfolder=$(pwd)

module purge
module load gcc/11.2.0 cuda/11.8

source /proj/ymiaolab/software/amber24/amber.sh

module purge
module load amber/24p3

cd "$workfolder"

which pmemd.cuda

pmemd.cuda -O -i md.in -p step3_input.parm7 -c gamd-1.rst -o md-1.out -x md-1.nc -r gamd-1.rst -gamd gamd-1.log
```

**注意**：`-c gamd-1.rst`（不是 `step5_10.rst7`），从 equilibration 终点坐标启动。

### 9.6 提交前检查清单

- [ ] 每个目录下有 6 个文件
- [ ] `md.in` 末尾有 `/` 结束符
- [ ] `md.in` 中 `irest_gamd=1`、`ntcmd=0`、`nteb=0`、`nstlim=50000000`
- [ ] `run-equil.pbs` 的 job-name 正确（每个 replica 不同）
- [ ] `run-equil.pbs` 中 `-c gamd-1.rst`
- [ ] `gamd-restart.dat` 存在于目录中
- [ ] 文件 owner 是 liualex
- [ ] 只提交一次（避免重复写同一目录）

### 9.7 提交任务

```bash
for i in 1 2 3 4 5 6; do
    cd /users/l/i/liualex/Miao_lab/HSP90_new/5OCI/production/2.5_${i}
    sbatch run-equil.pbs
done

squeue -u liualex    # 确认任务状态
```

### 9.8 Equilibration vs Production 本质区别总结

|                        | Equilibration               | Production                   |
| ---------------------- | --------------------------- | ---------------------------- |
| **目的**         | 参数探索：确定最优 sigma_OP | 数据收集：捕获解离事件       |
| **irest_gamd**   | 0（从头开始 GaMD）          | 1（读取已有 boost 参数）     |
| **ntcmd / nteb** | 非零（收集统计）            | 0（跳过，100% 时间用于生产） |
| **时长**         | 44 ns                       | 100 ns                       |
| **输出频率**     | 每 10 ps                    | 每 1 ps（更精细）            |
| **关键产出**     | gamd-restart.dat            | 解离轨迹 + GaMD 能量日志     |

---

## 第十步：数据分析

- 提取 PLIF（Protein-Ligand Interaction Fingerprints）特征
- 计算解离时间、相互作用
- 准备 ML 训练数据（约 40 万帧）

---

## 常见问题与故障排除

### 模拟相关

| 问题                                   | 原因                   | 解决                                          |
| -------------------------------------- | ---------------------- | --------------------------------------------- |
| `Fortran runtime error: End of file` | md.in 缺少结束符 `/` | 在最后一行添加 `/`                          |
| `illegal memory access` GPU 错误     | GPU 兼容性             | 改 `--mem=16G` 或 `--partition=volta-gpu` |
| `step5_10.rst7` 不存在               | cMD 中途失败           | 检查 mdout 是否能量爆炸                       |
| 文件 owner 是 nobody                   | 跨系统复制             | `cp -r` 重新复制                            |

### PyMOL 相关

> **来自录音**（Li 的问题和讨论）：
> Li: "我 PyMOL 为什么它不跟我登了？我今天用了教育版它都过期了。"
> Dharma: "这个本来就是免费的，你只要申请就是免费。"
> Li: "我一 skip 他就只要每一次我丢完一个新的文件以后他就会自动闪退。"
> Dharma: "实在不行你那个你就自己截屏……"

| 问题                            | 原因             | 解决                                                                     |
| ------------------------------- | ---------------- | ------------------------------------------------------------------------ |
| PyMOL 教育版 license 过期       | License 到期     | 去官网重新申请免费教育版 license                                         |
| 加载新文件后闪退                | 内存或兼容性问题 | 不要点红色关闭按钮（那是直接退出），点最小化；或者用截屏方式保存关键信息 |
| PyMOL 显示的编号与 Amber 不一致 | 编号体系不同     | 必须用 amber.pdb 文件中的编号，不能直接用 PyMOL 显示值                   |

> **来自录音**（Dharma 解释 PyMOL 关闭问题）：
> "你把它关了干啥？……你点那个红的是吧，那个闪退，那它肯定没了。"
> "小化，最小化是中间这个。"

---

## Longleaf 常用命令速查

```bash
sbatch script.pbs           # 提交任务
squeue -u liualex            # 查看任务状态
scancel [JOB_ID]             # 取消任务
module load amber            # 加载 AMBER
cpptraj -i analysis.in       # 运行分析
cat mdinfo                   # 查看模拟进度
```

---

## 待配置体系清单

| PDB ID | 状态                                             |
| ------ | ------------------------------------------------ |
| 5OCI   | ✅ Production 已提交（sigma_OP=2.5, 6 replicas） |
| 5ODX   | ✅ Production 已准备（sigma_OP=3.5, 6 replicas） |
| 5OD7   | ❌ cMD 失败，暂跳过                              |
| 5J86   | ⬜ 待配置                                        |
| 5J82   | ⬜ 待配置                                        |
| 5J64   | ⬜ 待配置                                        |
| 5J2X   | ⬜ 待配置                                        |
| 5J27   | ⬜ 待配置                                        |
| 5J20   | ⬜ 待配置                                        |
