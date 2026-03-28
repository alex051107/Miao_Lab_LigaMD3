# HSP90 cMD 模拟操作记录

## 项目信息

一定要记住

- **项目路径**: `/users/l/i/liualex/Miao_lab/HSP90_new/`
- **三个体系**: 5OCI, 5OD7, 5ODX (HSP90 + 不同配体)
- **模拟类型**: cMD (常规分子动力学)，为后续 LiGaMD3 做准备

---

## 2026-01-29

### 17:30 - 首次提交作业失败

- **问题**: 作业提交后 1 秒内失败，ExitCode 0:53
- **原因**: 文件 owner 是 `nobody`（师兄从其他系统复制过来），`liualex` 没有写权限
- **解决**: 用户自己重新 `cp -r` 复制文件，新文件 owner 变成 `liualex`

### 17:34 - 第二次提交作业

- **Job IDs**: 28988389 (5OCI), 28988390 (5OD7), 28988391 (5ODX)
- **状态**: 5OD7 开始运行，但遇到 GPU 错误

### 17:35 - GPU 内存错误

- **错误信息**:
  ```
  Error: an illegal memory access was encountered launching kernel kNLSkinTest
  Unit 9 Error on OPEN: step4.1_equilibration.rst7
  ```
- **分析**:
  - 这是 GPU 内存访问错误，不是 CPU 内存问题
  - 可能原因：L40 GPU 与 AMBER/CUDA 版本不兼容
- **尝试方案**:
  1. 方案 A: 换成 `volta-gpu` 分区（V100 GPU，更稳定）
  2. 方案 B: 调整 CUDA 版本

### 17:45 - 创建多个测试版本

创建了三个版本的脚本文件，用于对比测试：

| 文件名                    | GPU 分区  | 内存 | 说明     |
| ------------------------- | --------- | ---- | -------- |
| `sub-cmd.slum.original` | l40-gpu   | 32G  | 原始配置 |
| `sub-cmd.slum.mem16g`   | l40-gpu   | 16G  | 只改内存 |
| `sub-cmd.slum.volta`    | volta-gpu | 32G  | 只改 GPU |

### 18:00 - 同时测试两个方案

- **方案 A**: `sub-cmd.slum.mem16g` (l40-gpu + 16G) - 测试是否是内存问题
- **方案 B**: `sub-cmd.slum.volta` (volta-gpu + 32G) - 测试是否是 GPU 兼容性问题

### 18:08 - 测试结果

- **两个方案都成功了！**
- 原始配置 (l40-gpu + 32G) 失败的原因可能是内存分配问题
- 解决方案：使用 `sub-cmd.slum.mem16g` (l40-gpu + 16G)

### 18:15 - 提交剩余体系

- 5OD7: Job 28994896 (l40-gpu + 16G)
- 5ODX: Job 28994897 (l40-gpu + 16G)
- 使用 mem16g 方案

---

## 重要提醒

### 禁止使用的命令

- ❌ `rm -rf` - 使用 `mv` 重命名代替删除

### 文件权限检查

- 每次操作前用 `ls -ld` 检查目录 owner
- 如果 owner 不是 `liualex`，需要重新复制

### 关键文件位置

- 脚本: `*/amber/sub-cmd.slum`
- 日志: `*/amber/log.cMD-*.JobID`
- 输入: `*/amber/step3_input.parm7`, `step3_input.rst7`

---

## 2026-02-03

### cMD 运行状态检查

| 体系           | cMD 状态 | step5_10.rst7 | 问题                           |
| -------------- | -------- | ------------- | ------------------------------ |
| **5OCI** | ✅ 完成  | ✅ 有         | 无                             |
| **5OD7** | ❌ 失败  | ❌ 缺少       | step4.1_equilibration 能量爆炸 |
| **5ODX** | ✅ 完成  | ✅ 有         | 无                             |

### 5OD7 问题诊断

- **现象**: `step5_1` ~ `step5_10` 的 mdout 都报 `Unit 9 Error on OPEN: stepX.rst7`
- **根本原因**: `step4.1_equilibration` 在 NSTEP=1000 时能量发散（`*******`），未生成 `step4.1_equilibration.rst7`
- **证据**: `step4.1_equilibration.mdout` 第 288-293 行显示能量值全部溢出

### 从旧项目复制 equilibration 文件

学长在 `/users/l/i/liualex/Miao_lab/HSP90/` 准备了 LiGaMD3 equilibration 文件：

```bash
cp -r /users/l/i/liualex/Miao_lab/HSP90/5OCI/equilibration /users/l/i/liualex/Miao_lab/HSP90_new/5OCI/
cp -r /users/l/i/liualex/Miao_lab/HSP90/5OD7/equilibration /users/l/i/liualex/Miao_lab/HSP90_new/5OD7/
cp -r /users/l/i/liualex/Miao_lab/HSP90/5ODX/equilibration /users/l/i/liualex/Miao_lab/HSP90_new/5ODX/
```

### 复制后的文件状态

| 体系           | equilibration/e1_166211/ 内容                                   | 可否开始 LiGaMD3  |
| -------------- | --------------------------------------------------------------- | ----------------- |
| **5OCI** | md.in, run-equil.pbs, step3_input.parm7,**step5_10.rst7** | ✅ 可以           |
| **5OD7** | md.in, run-equil.pbs, step3_input.parm7 (缺 rst7)               | ❌ 需要先完成 cMD |
| **5ODX** | md.in, run-equil.pbs, step3_input.parm7,**step5_10.rst7** | ✅ 可以           |

### LiGaMD3 md.in 关键参数

```
igamd = 28              # LiGaMD3 模式
irest_gamd = 0          # 新的 GaMD 模拟
ntcmd = 2000000         # cMD 阶段：2M steps = 4 ns
nteb = 20000000         # equilibration 阶段：20M steps = 40 ns
sigma0P = 1, sigma0D = 6.0, sigma0B = 6.0  # 初始 sigma 值
nstlim = 22000000       # 总模拟长度：22M steps = 44 ns
```

### LiGaMD3 Sigma_OP 并行优化

- **目标**: 找临界 sigma_OP（1.0–4.0，间隔 0.5）
- **创建**: 5OCI、5ODX 各 7 个文件夹 `e1_sigma{1.0,1.5,2.0,2.5,3.0,3.5,4.0}/`
- **修改**: 各文件夹 `md.in` 中 `sigma0P`、`run-equil.pbs` 中 job-name（如 5OCI-e1.0）
- **修复**: 学长原始 md.in 缺 AMBER namelist 结束符 `/` → 全部补上，解决 `Fortran runtime error: End of file`
- **提交**: 5OCI Job 29400895, 29400931–29400936；5ODX 29400937–29400943（内存保持 32G）

### Analysis 设置

- **5OCI / 5ODX**: 将 `analysis/e1/` 下文件复制到每个 `e1_sigma*/analysis/`
- **修改**: 各 `analysis.in` 中 `trajin` 从 `../../e1_166211/md-1.nc` 改为 `../md-1.nc`
- **运行**: `cd [体系]/equilibration/e1_sigma[X]/analysis/` 后执行 `cpptraj -i analysis.in`

### 查看任务剩余时间

- 打开 `md-1.out` 看末尾，或直接看 `mdinfo`
- 示例（e1_sigma1.0）：`Completed: 18.5%`，`Estimated time remaining: 4.1 hours`

### Cursor 项目规则

- 创建 `.cursor/rules/hsp90-project.mdc`（alwaysApply: true）
- 约定：重要操作后更新 CHANGELOG；任务管理、分析路径与监控说明写入规则

### 下一步

1. 任务跑至 25%/50% 时用 cpptraj 看 RMSD、distance，找临界 sigma_OP
2. 5OD7 暂不跑 LiGaMD3（缺 cMD 的 step5_10.rst7）

---

## 2026-02-06

### 5OCI + 5ODX LiGaMD3 Production 准备与提交

#### 参考 CDK2 项目确认 production 方案

- CDK2 项目路径: `/users/l/i/liualex/Miao_lab/CDK2_LiGaMD3/CDK2/`
- CDK2 的 production (replicate) 的 md.in 和 equilibration **完全相同**
- 区别仅在于：不同目录 + 不同 job-name + `ig=-1` 自动产生不同随机种子
- CDK2 参数: nstlim=28M (56 ns), ntcmd=3M, nteb=25M
- HSP90 参数: nstlim=22M (44 ns), ntcmd=2M, nteb=20M（保持不变）

#### 创建 production 目录

**5OCI**（最优 sigma_OP = **2.5**）：

- 创建 6 个 replica: `production/2.5_{1-6}/`
- 每个 replica 文件:
  - `md.in` — 从 `equilibration/e1_sigma2.5/md.in` 复制（不修改）
  - `run-equil.pbs` — job-name: `5OCI-2.5_1` ~ `5OCI-2.5_6`
  - `step3_input.parm7`、`step5_10.rst7` — 从 equilibration 复制

**5ODX**（最优 sigma_OP = **3.5**）：

- 创建 6 个 replica: `production/3.5_{1-6}/`
- 每个 replica 文件:
  - `md.in` — 从 `equilibration/e1_sigma3.5/md.in` 复制（不修改）
  - `run-equil.pbs` — job-name: `5ODX-3.5_1` ~ `5ODX-3.5_6`
  - `step3_input.parm7`、`step5_10.rst7` — 从 equilibration 复制

#### 文件权限修复

- Cursor 创建的文件 owner 为 root → 在 Longleaf 终端 `cp -r` 修复为 liualex
- 修复后确认 `ls -la` 显示 owner 为 liualex

#### 提交与取消

- **5OCI** 提交 6 个 replica: Job 29671222-29671227（误重复提交 4 次，已 scancel 多余 24 个）
- **5ODX** 提交 6 个 replica: Job 29672374-29672379
- **全部取消**: 学长提醒 production md.in 需要修改参数，已 scancel 全部 12 个任务
  - `scancel 29671222-29671227`（5OCI）
  - `scancel 29672374-29672379`（5ODX）

#### 详细操作流程已更新到 `system_preparation_guide.md` 第六步

#### 学长确认 production md.in 参数修改

Production **不是**直接复制 equilibration 的 md.in，需要修改以下参数：

| 参数           | Equilibration    | Production                  | 原因                                            |
| -------------- | ---------------- | --------------------------- | ----------------------------------------------- |
| `nstlim`     | 22000000 (44 ns) | **50000000 (100 ns)** | 全部时间用于生产采样                            |
| `irest_gamd` | 0                | **1**                 | 从 equilibration 重启 GaMD，使用已有 boost 参数 |
| `ntcmd`      | 2000000          | **0**                 | 跳过 cMD 统计阶段                               |
| `nteb`       | 20000000         | **0**                 | 跳过 GaMD 平衡阶段                              |
| `ntcmdprep`  | 400000           | **0**                 | 无需准备阶段                                    |
| `ntebprep`   | 400000           | **0**                 | 无需准备阶段                                    |
| `ntpr`       | 5000             | **500**               | 输出更频繁（每 1 ps）                           |
| `ntwx`       | 5000             | **500**               | 轨迹输出更频繁（每 1 ps）                       |

额外需要从 equilibration 复制的文件：

- `gamd-restart.dat` — GaMD boost 参数（irest_gamd=1 读取）
- `gamd-1.rst` — equilibration 终点坐标（作为 production 起始坐标）

同时修改 `run-equil.pbs` 中 `-c step5_10.rst7` → `-c gamd-1.rst`

已完成修改：5OCI 6 个 replica + 5ODX 6 个 replica = 12 个目录全部更新

#### 重新提交 Production 任务

- **5OCI** (sigma_OP=2.5, 6 replicas): Job **29673934–29673939**
- **5ODX** (sigma_OP=3.5, 6 replicas): Job **29673940–29673945**
- 共 12 个任务，每个 100 ns production（irest_gamd=1，从 gamd-1.rst 启动）

### 下一步

1. 监控任务：`squeue -u liualex`
2. 跑完后用 cpptraj 分析解离事件，筛选 3 个有解离的 replica
3. 5OD7 暂跳过（cMD 失败）

---

## 2026-02-09

### Production 轨迹分析完成

- **操作**: 对 12 个 production 目录（5OCI 2.5*{1–6}、5ODX 3.5*{1–6}）运行 cpptraj 分析
- **方法**: 在各目录下执行 `cpptraj -i analysis.in`（需先有 `analysis.in`、`sys-protein.pdb`、`md-1.nc`）
- **结果**: 每个目录生成 `rmsd-9R8.dat` / `rmsd-9RZ.dat` 与 `dis-ASP_OD2-9R8_O2.dat` / `dis-ASP_OD2-9RZ_O2.dat`
- **脚本**: `batch_analysis_hsp90.sh` 可批量写入 analysis.in、拷贝 sys-protein.pdb 并运行 cpptraj

### 5ODX production 解离数据结论

- **结论**: 5ODX 之前跑的 production（sigma*OP=3.5，3.5*{1–6}）已经能够提取到足够的解离数据
- **参数**: sigma_OP=3.5 作为 5ODX 的 LiGaMD3 参数可行，无需再增跑其他 sigma_OP

### 5OCI production 情况与新增 2.6–2.9

- **2.5 结果**: sigma*OP=2.5 的 6 个 replica（2.5*{1–6}）均**未观测到解离**，6 个都没有发生 distance 的剧烈增加
- **新增**: 在 **production** 下新增 2.6、2.7、2.8、2.9 各 6 轮，共 24 个目录，用于对比更大 sigma_OP 是否出现解离

#### 修改与新增的文件/目录

| 类型 | 路径/文件                       | 说明                                                                                                                       |
| ---- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| 目录 | `5OCI/production/2.6_{1–6}/` | 6 个 replica，sigma0P=2.6                                                                                                  |
| 目录 | `5OCI/production/2.7_{1–6}/` | 6 个 replica，sigma0P=2.7                                                                                                  |
| 目录 | `5OCI/production/2.8_{1–6}/` | 6 个 replica，sigma0P=2.8                                                                                                  |
| 目录 | `5OCI/production/2.9_{1–6}/` | 6 个 replica，sigma0P=2.9                                                                                                  |
| 文件 | 各目录 `md.in`                | 仅改 `sigma0P` 为 2.6/2.7/2.8/2.9，其余与 2.5 production 一致（nstlim=50M, irest_gamd=1 等）                             |
| 文件 | 各目录 `run-equil.pbs`        | 仅改 `#SBATCH --job-name=` 为 `5OCI-2.6_1` … `5OCI-2.9_6`                                                           |
| 文件 | 各目录其余文件                  | 从 2.5_1 复制：step3_input.parm7, step5_10.rst7, gamd-1.rst, gamd-restart.dat, gamd-ligB.dat, sys-protein.pdb, analysis.in |

- **未**在 equilibration 下新建 e1_sigma2.6/2.7/2.8/2.9，production 沿用 e1_sigma2.5 的 gamd-1.rst、gamd-restart.dat 与相同 production 参数，仅改 sigma0P 与 job-name

#### 当前状态

- 24 个 production 任务已提交：Job ID **29927586–29927609**（2.6_1–6, 2.7_1–6, 2.8_1–6, 2.9_1–6）
- 查看队列：`squeue -u liualex`；查看历史：`sacct -u liualex`

---

## 2026-02-21

### 配置剩余 6 个新体系的 cMD 任务

- **背景**: 之前记录中最后提到的“6 个没有通过 CHARMM-GUI 的文件”现已由用户上传并建立好目录环境（分别为 `5J2X`、`5J20`、`5J64`、`5J27`、`5J82`、`5J86`）。
- **坐标修复 (PDB4Amber)**: 遵循学长指导，使用 `source /proj/ymiaolab/software/amber22/amber.sh` 环境，执行 `pdb4amber -i step3_input.pdb -o amber.pdb` 修复坐标文件。
- **Slurm 配置**: 为了防止 L40 GPU 环境的 32G 内存错误（参照 1月29日 经验），统一使用 `--partition=l40-gpu` 与 `--mem=16G` 配置生成 `sub-cmd.slum`。
- **脚本清洗 (`run-cmd.csh`)**: 统一去除了 `CHARMM-GUI` 默认模板中的并行 CPU 配置指令，并清洗了测试中循环覆盖错误导致的多余命令。在每条脚本首行加入 `which pmemd.cuda` 以确保正确寻址 GPU 计算。
- **提交状态**: 6 台服务器任务均已就绪并顺利进入 SLURM 计算队列。

| 体系名   | 作业类型 | Job ID             |
| -------- | -------- | ------------------ |
| `5J2X` | cMD      | **32419394** |
| `5J20` | cMD      | **32419395** |
| `5J64` | cMD      | **32419396** |
| `5J27` | cMD      | **32419397** |
| `5J82` | cMD      | **32419398** |
| `5J86` | cMD      | **32419399** |

### 下一步

1. **下载并核对坐标文件**: 在等待这 6 个体系完成 200ns 常规分子动力学模拟 (cMD) 的同时，将各个体系在 `amber/` 目录下刚生成的 `amber.pdb` 文件下载到本地电脑。
2. **PyMOL 分析相互作用位点**: 把本地的 `amber.pdb` 导入 PyMOL，去除水分子与离子干扰，使用 `polar contacts` 寻找蛋白与配体之间最关键且稳定的相互作用（氢键等）。确认后续 LiGaMD3 模拟监控确切需要的 `atom_p` (蛋白侧原子序号) 和 `atom_l` (配体端原子序号)。
3. **开启 Equilibration**: 等 cMD 跑完产出最后的 `step5_10.rst7` 坐标重启文件后，结合 PyMOL 中获取的原子序号更新 `md.in`，正式进入 `equilibration` 参数探索阶段。

---

## 2026-02-22

### LiGaMD3 Equilibration 准备 - 6 个新体系

所有 6 个新体系（5J20, 5J2X, 5J64, 5J82, 5J86, 5J27）的 cMD 均已跑完（`step5_10.rst7` + `step5_10.nc` 均存在）。

#### 完成工作

1. **PyMOL 极性接触分析**: 使用 PyMOL GUI `Action → Find → Polar Contacts` 找到各体系 ASP 79 与配体之间的关键相互作用；通过点击确定具体原子（优先 OD2 或 OD1）。
2. **md.in 参数确认方法论**:

   - `edpro2atm` = NME（蛋白 C-端保护基）最后一个原子的 PDB 序号
   - `ntwprt` = 配体最后一个原子的 PDB 序号（只存蛋白+配体，不含水/离子）
   - `atom_p` = ASP 79 OD1/OD2 的 PDB 绝对序号
   - `atom_l` = 配体目标氧原子的**相对序号**（绝对序号 − 配体第一原子绝对序号 + 1）
   - `dblig = 2.6`（距离监控阈值）
3. **equilibration 文件夹创建**: 在各体系下复制 5OCI 的 `md.in` 模板，修改系统特异参数，并从 cMD 目录复制 `step5_10.rst7` + `step3_input.parm7`。

#### 各体系 md.in 参数汇总

| 体系 | 配体     | timask | ntwprt | edpro2atm | atom_p           | atom_l              | dblig |
| ---- | -------- | ------ | ------ | --------- | ---------------- | ------------------- | ----- |
| 5J20 | 6FJ :211 | :211   | 3325   | 3277      | 1261 (ASP79 OD2) | 28 (O1)             | 2.6   |
| 5J2X | 6DL :212 | :212   | 3330   | 3299      | 1261 (ASP79 OD2) | 1 (O2，配体第1原子) | 2.6   |
| 5J64 | 6G7 :211 | :211   | 3314   | 3283      | 1266 (ASP79 OD2) | 1 (O2，配体第1原子) | 2.6   |
| 5J82 | 6GV :211 | :211   | 3330   | 3282      | 1266 (ASP79 OD2) | 28 (O2)             | 2.6   |
| 5J86 | 6GW :211 | :211   | 3333   | 3282      | 1266 (ASP79 OD2) | 28 (O1)             | 2.6   |
| 5J27 | 6FF :212 | :212   | 3352   | 3304      | 1266 (ASP79 OD2) | 28 (O2)             | 2.6   |

> **注意**：`amber.pdb`（由 pdb4amber 生成）将 6FF 残基号从 301 重编为 212，timask 以 `amber.pdb` 为准。

### Equilibration 任务提交

共 6 体系 × 9 个 sigma（1.0, 1.5, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.5）= **54 个任务**。

| 体系 | Job ID 范围          |
| ---- | -------------------- |
| 5J20 | 32456589 – 32456597 |
| 5J2X | 32456598 – 32456606 |
| 5J64 | 32456607 – 32456615 |
| 5J82 | 32456616 – 32456624 |
| 5J86 | 32456625 – 32456633 |
| 5J27 | 32458701 – 32458709 |

### 脚本整理

- `batch_analysis_hsp90.sh`：重写为通用版，支持所有 8 个体系，接受 `production/equilibration` 模式参数
- `batch_plot_save_images_hsp90.sh`：同样通用化
- `fix_and_submit.py`、`update_workflow.py`：已归入 `_archive/`（一次性脚本）
- `.cursor/rules/hsp90-project.mdc`：全面更新，覆盖当前所有体系状态与正确方法论

### 下一步

1. 监控 equilibration 任务，用 cpptraj 分析 distance 和 RMSD
2. 找各体系最优 sigma_OP（最大的不解离 sigma），再进入 production 阶段
3. 5J27 在 PyMOL 分析中用 `amber.pdb`（已生成）而非 `step3_input.pdb`

### Equilibration md.in 修复与重新提交

- **问题**: 6个新体系的所有54个 equilibration 任务在读取 `md.in` 时报 `Fortran runtime error: End of file`。
- **原因**: 学长的模板末尾需要 Fortran namelist 的 `&cntrl` 块结束符 `/`。
- **修复**: 使用脚本批量向所有6个体系的 `equilibration/e1_sigma*/md.in` 文件末尾追加了 `/`，并使用 `sbatch run-equil.pbs` 一次性重新提交了这 54 个任务。

### Sigma_OP 参数范围调整

- **操作**: 取消了之前提交的所有 `sigma_OP = 1.0` 的 equilibration 任务。
- **原因**: 根据评估，不再需要测试 1.0 这个过小的值。
- **替换**: 将所有 `sigma 1.0` 的目录重命名为 `1.8`，把里面的 `md.in` 修改为 `sigma0P = 1.8` 并重新提交了对应的 6 个任务。

### 新体系 2YKJ Equilibration 准备与提交

- **分析**: cMD 目录中 `amber.pdb` 显示蛋白总原子级 3268（NME尾端），总原子数 34826。配体名 YKJ，最后原子的序号为 3318。
- **互动映射**: 在 PyMOL 中确认了结合相互作用位于蛋白 `ASP 78 (OD2)` 和 配体 `YKJ 210 (N6)`：
  - `atom_p` = 1252 (ASP 78 OD2 的绝对序号)
  - `atom_l` = 1 (N6 在配体内部的相对原子序号：3269 - 3269 + 1)
- **参数**: 采用 `dblig = 2.6`，`edpro2atm = 3268`，`ntwprt = 3318`，构建了 `md.in`。
- **运行**: 创建了从 `1.5` 到 `3.5`（间隔测试点包括 `1.8`、`2.0`、`2.2`、`2.4`、`2.6`、`2.8`、`3.0`）的 9 个 sigma 测试目录，并提交到了 `l40-gpu` 对列跑 equilibration。
- **更新**: 通用批处理分析脚本 `batch_analysis_hsp90.sh` 与画图脚本中已兼容加入 `2YKJ` 配置。
- **微调**: 根据 PyMOL 实测结果，将 2YKJ 平衡配置中的 `dblig` 距离标准由 2.6 修改为 2.3，并重新提交了 9 个测试任务。

### 5J20 Equilibration 分析与 Production 准备

- **结果观测**: 5J20 在各 sigma 下平衡计算顺利完成。分析表明，配体解离现象从 `sigma_OP = 3.5` 左右开始发生。
  - **Sigma 3.0**: Mean Boost Energy (Potential) = `31.791678`, Std Dev = `5.369277`
  - **Sigma 3.5**: Mean Boost Energy (Potential) = `36.650621`, Std Dev = `26.024823`
- **Production 部署**: 确定使用未发生解离的最大值 `sigma_OP = 3.0`，为 5J20 配置了 6 组 Production 阶段复本（`3.0_1` 至 `3.0_6`），并已全部提交完毕待跑。

### 批量新体系 Equilibration 阶段部署 (2YKI, 4EFU, 5J6L 等 8个)

- **分析与索引映射**: 根据 PyMOL 的测量与 `amber.pdb` 提取算法，批量精确计算了 8 个新体系的 `atom_l` 相对序号（如 2YKI 的 46，4EFU 的 26 等）、绝对 `atom_p` 序号，以及体系划分点 `edpro2atm` 和 `ntwprt`。
- **环境构建**: 通过自动化脚本，在无视 `step5_10.rst7` 生成状态的情况下（因为可能尚未跑完 cMD），强势将 1.5 到 3.5 的 9 个 sigma 区间配置文件全面克隆覆盖进去。
- **任务状态**: `md.in` 与 `run-equil.pbs` 构建妥当，只需在有初始坐标结构后直接 sbatch 提交即可。

### 自动化工作流与文档重建 (Batch 3 完善)

- **cMD 补提与脚本缝合**: 确认新体系缺乏基础 cMD 后，重构了底层部署机制，将 `cMD 配置提交` 与 `Equilibration 生成` 融合成一体化、任意传参的通用脚本 `auto_setup_pipeline.sh`，并成功将 8 个新体系的前置 cMD 推入 `l40-gpu` 队列。
- **体系记忆恢复卡**: 完全统筹了全部 18 个系统的进度，编写 `system_preparation_guide.md` 作为恢复状态和进行下一步操作的详细指南。
- **主流程批注与清理**: 对核心教程 `HSP90_LiGaMD3_Complete_Workflow.md` 进行了 `🤖 自动化` 相关批示，并清理了工作区根目录（各类脚本统一移动至 `_scripts/`，历史和冗余配置抛入 `_archive/`，老版 AI 追踪夹 `.cursor` 重命名为 `.antigravity`）。

---

## 2026-02-24

### 全面排查失败的 Equilibration 任务

#### 失败原因分析

对 `sacct` 历史记录中所有 FAILED 状态的 equilibration 任务进行了逐一排查，发现两类不同的失败原因：

**类型 A — 缺少 step5_10.rst7（Exit Code 1:0）**

| 体系 | 受影响 sigma           | 原因                                                                                                    |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------- |
| 2YKJ | 全部 9 个 (e1.5–e3.5) | cMD**从来没有被提交过**（目录下缺 `sub-cmd.slum`），导致 equilibration 找不到 `step5_10.rst7` |

**类型 B — Periodic box dimensions 爆炸（Exit Code 255:0）**

| 体系 | 受影响 sigma           | 原因                                                                                                            |
| ---- | ---------------------- | --------------------------------------------------------------------------------------------------------------- |
| 5J86 | e2.8, e3.0, e3.5       | 首次提交时遇到 Fortran EOF 错误（缺 `/` 结束符）→ 修复后重跑 → 高 sigma 在模拟中后期发生 box dimension 爆炸 |
| 5J2X | e2.6, e2.8, e3.0, e3.5 | 同上                                                                                                            |
| 5J64 | e3.0, e3.5             | 同上                                                                                                            |
| 5J82 | e3.5                   | 同上                                                                                                            |
| 5J27 | e3.5                   | 同上                                                                                                            |

> **重要发现**: 上述类型 B 的任务在**第二次重新提交后全部成功完成**。`sacct` 中的 FAILED 记录是旧的首次提交记录。经核实，所有 Batch 2 体系（5J20, 5J2X, 5J64, 5J82, 5J86, 5J27）的 9 个 sigma 值均已完成 equilibration（`gamd-1.rst` 均存在）。

#### 修复操作

1. **2YKJ cMD 提交**: 创建 `sub-cmd.slum` 并提交 → Job **32805935**
2. **Batch 3 equilibration 提交**: 7 个已完成 cMD 的体系（2YKI, 4EFU, 5J6L, 5J6M, 5J6N, 3LDP, 5J8M）+ 5J8U，将 `step5_10.rst7` 从各自 cMD 目录复制到 equilibration 目录并提交
3. **缺失 run-equil.pbs 修复**: 5 个体系（4EFU, 5J6L, 5J6M, 5J6N, 5J8M）的 `e1_sigma2.5` 和 `e1_sigma3.2` 目录缺少 `run-equil.pbs`，从邻近 sigma 复制并修改 job-name 后提交

#### 批量提交汇总

| 体系 | 提交任务数 | 备注                                  |
| ---- | ---------- | ------------------------------------- |
| 2YKI | 9          | sigma 1.5–3.5                        |
| 4EFU | 11         | sigma 1.5–3.5 + 2.5, 3.2（补建 pbs） |
| 5J6L | 11         | 同上                                  |
| 5J6M | 11         | 同上                                  |
| 5J6N | 11         | 同上                                  |
| 3LDP | 9          | sigma 1.5–3.5                        |
| 5J8M | 11         | sigma 1.5–3.5 + 2.5, 3.2（补建 pbs） |
| 5J8U | 9          | sigma 1.5–3.5                        |

### 分析脚本改进

- **`batch_analysis_hsp90.sh` 增强**: 增加了自动生成 `sys-protein.pdb` 的功能。当分析目标目录缺少该参考文件时，脚本会自动调用 cpptraj，从 `step5_10.rst7` 或 `gamd-1.rst` 中剥离水和离子生成纯蛋白-配体 PDB。
- **批量分析执行**: 对所有已完成的 equilibration 目录运行了 cpptraj 距离和 RMSD 分析

### 5OCI Production 错误修复与清理

- **问题发现**: 5OCI 的 2.6-2.9 生产任务最初在 2.9 Equilibration 尚未完成前被错误启动，且 5OCI 在 sigma 3.0 开始解离，意味着只需进行 2.9 的 production。
- **修复操作**: 彻底使用 `scancel` 取消并使用 `rm -rf` 删除了 `production/2.6_1` 到 `production/2.8_6` 共 18 个多余且错误的目录。
- **重新提交**: 为 5OCI 重新根据刚刚跑完的正确 `gamd-1.rst` 提交了 **sigma 2.9 的 6个 replicas** 的 production (Job 32817907 等)。

<!-- ### 当前运行状态追踪与记忆建立

为了防止再出现类似的逻辑错误与跑偏，建立了专门的记忆与追踪机制：

- **AI 防错记录**: 在工作区创建了 `.antigravity/AI_lessons_learned.md`，永久记录本次关于依赖检查和多余 sigma 提交的错误。
- **独立任务监控日志**: 建立了 `.antigravity/running_tasks.log`，不再在 CHANGELOG 内部维护容易过期的运行状态表格。当前真正在跑的 5ODX (7-12)、5OCI (2.9_1~6)、以及 85 个排队中任务的客观状态，均记录于此文件中。
- **快捷 Terminal 命令 (Workflows)**: 在 `.agent/workflows/` 下生成了 3 个快捷工作流文档，提取了用于查询状态、批量跑 cpptraj 分析、以及用 xmgrace 批量出 png 图的核心 bash 命令，方便用户一键在 Terminal 中执行。 -->

---

## 2026-02-25

### Equilibration：有 out 无 distance 的目录与只补跑分析

- **对照昨天 (2/24) 日志**：2/24 批量提交了 Batch 3 equilibration（2YKI, 4EFU, 5J6L, 5J6M, 5J6N, 3LDP, 5J8M, 5J8U），并曾对「当时已完成的」目录跑过 cpptraj。2YKI / 5ODX / 5OCI / 5J20 / 5J2X 的 equilibration 已有 `dis-*.dat`（已跑过或结果已落盘）。
- **当前状态**：下面 11 个体系的所有 e1_sigma* 目录均为「有 `md-1.out` 且存在 `md-1.nc`，但还没有 `dis-ASP_OD2-*.dat`」——即任务已跑完、轨迹在，仅未做 Distance/RMSD 分析。
- **需补跑 Distance 的体系**（只对这些跑 batch_analysis equilibration，不重跑已有 distance 的）：**4EFU, 5J6N, 5J64, 5J82, 5J86, 5J27, 5J6L, 5J6M, 3LDP, 5J8M, 5J8U**（每体系 9 个 e1_sigma*，共 99 个目录）。
- **扫描命令**（有 out 无 distance）：
  ```bash
  cd /users/l/i/liualex/Miao_lab/HSP90_new && for sys in 4EFU 5J6N 5J64 5J82 5J86 5J27 5J6L 5J6M 3LDP 5J8M 5J8U; do eq="$sys/equilibration"; [ ! -d "$eq" ] && continue; for d in "$eq"/e1_sigma*/; do [ ! -d "$d" ] && continue; [ -f "${d}md-1.out" ] && [ ! -f "${d}"dis-*.dat ] 2>/dev/null && echo "NEED_DIS $sys $(basename $d)"; done; done
  ```
- **补跑命令**：
  ```bash
  bash _scripts/batch_analysis_hsp90.sh equilibration 4EFU 5J6N 5J64 5J82 5J86 5J27 5J6L 5J6M 3LDP 5J8M 5J8U
  ```

### 2YKJ equilibration md-1.out 为旧错误说明

- **2YKJ equilibration 旧错误目录已移走**：上述 8 个（e1_sigma1.5, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0）及 e1_sigma3.5 的 md-1.out 结尾均为 `Unit 9 Error on OPEN: step5_10.rst7`（在 2YKJ cMD 未产出 step5_10.rst7 时误提交所致）。已整体移至 `_archive/2YKJ_equilibration_old_error/`，避免与日后 cMD 完成再提交的 equilibration 混淆。2YKJ/equilibration 现为空，等 cMD 完成后再按流程新建 e1_sigma* 并提交。

### 5OCI / 5ODX Production md.in 核对结论

- **5OCI production 2.5_1** 与 **5ODX production 3.5_1 / 3.5_7** 的 md.in 已按 workflow 9.2 核对：`nstlim=50000000`、`irest_gamd=1`、`ntcmd=0`、`nteb=0`、`ntcmdprep=0`、`ntebprep=0`、`ntpr=500`、`ntwx=500`，与 equilibration 的 8 处差异正确；sigma0P、timask、atom_p/atom_l 与各自体系一致。
- **结论**：md.in 没有改错。5ODX 的 3.5_7～3.5_12 未观察到解离，更可能是**概率问题**（100 ns 内并非每个 replica 都会发生解离）；若需更多解离事件，可后续补跑更多 replica 或延长时长。

### 扫描“跑完但报错”任务（所用命令）

除 5ODX production 外，仅 2YKJ 的上述 8 个 equilibration 目录的 md-1.out 结尾为失败信息；无其他 equilibration/production 跑完后报错。

**扫描命令**（可复用以排查任意 md-1.out 结尾是否为失败）：

```bash
cd /users/l/i/liualex/Miao_lab/HSP90_new && for f in $(find . -name "md-1.out" \( -path "*/equilibration/*" -o -path "*/production/*" \) 2>/dev/null); do err=$(tail -3 "$f"); echo "$err" | grep -qE "Error on OPEN|ABORT|box dimension" && echo "FAIL $f" || true; done
```

### 5ODX production 分析与出图

- **Distance 分析**：仅对 3.5_7～3.5_12 补跑 cpptraj（生成 `dis-ASP_OD2-9RZ_O2.dat`、`rmsd-9RZ.dat`）；3.5_1～3.5_6 未重跑。
- **解离 replica 出图**：对 5ODX 有解离的 3.5_2、3.5_5、3.5_6 用 `gracebat` 生成 distance 图：
  - `5ODX/production/3.5_2/distance-9RZ-3.5_2.png`
  - `5ODX/production/3.5_5/distance-9RZ-3.5_5.png`
  - `5ODX/production/3.5_6/distance-9RZ-3.5_6.png`

出图命令示例：`module load grace && gracebat <dir>/dis-ASP_OD2-9RZ_O2.dat -hardcopy -hdevice PNG -printfile <dir>/distance-9RZ-3.5_X.png`

### 原始脚本运行方式与“现在不可以”的原因

- **当初用法**：`system_preparation_guide.md` 4.3 里写的是无参数调用`bash _scripts/batch_analysis_hsp90.sh`、`bash _scripts/batch_plot_save_images_hsp90.sh`，即用脚本默认的 `ALL_SYSTEMS` 处理“当时脚本里配置了的”体系。
- **现在不可以的两点原因**：
  1. **画图**：脚本里原先用 `xmgrace`，在登录节点/SSH 下没有 DISPLAY，无法弹窗，`-hardcopy` 也不会执行；已改为**优先使用 `gracebat`**（无头批处理），同一套命令在无图形环境下可直接出图。
  2. **体系不全**：脚本里的体系列表和参数曾只包含部分 Batch 1/2，没有 2YKI、2YKJ、4EFU、5J6L、5J6M、5J6N、3LDP、5J8M、5J8U，且 5J27 的残基号写成了 :301（应为 amber.pdb 重编后的 :212）。未配置的体系会被跳过或报错。

### 脚本参数与文档同步更新

- **batch_analysis_hsp90.sh**：按 `HSP90_LiGaMD3_Complete_Workflow.md` 5.4.4/5.4.5、`system_preparation_guide.md` 表，补全 4EFU、5J6L、5J6M、5J6N、3LDP、5J8M、5J8U 的 LIG_RESID/LIG_NAME/ASP_RES/ASP_ATOM/LIG_ATOM；5J27 改为 :212；5J20 的 OPT_SIGMA 设为 3.0；3LDP 使用 GLU269 OE2（ASP_RES :269, ASP_ATOM OE2）。
- **batch_plot_save_images_hsp90.sh**：已包含上述全部体系及对应 LIG_NAME/LIG_ATOM，与分析脚本一致。
- **.antigravity/rules/hsp90-project.mdc**：全部体系一览表已更新为包含 Batch 3，并注明 5J27 用 :212、3LDP 用 GLU269 OE2。

### analysis.in 的由来与修改原则

一开始是师兄给一个 cpptraj 通用模板（如 2YKI e1_sigma1.5 里的 analysis.in），换体系时只按具体原则改几处：配体残基号（amber.pdb）、蛋白监控残基与原子（:78@OD2 等）、配体原子名（PyMOL polar contacts）、输出文件名里的配体名。脚本的配置表与自动生成 analysis.in 就是把这条「模板 + 按体系改」流程固化。

### analysis.in 的由来与修改原则

- **一开始的用法**：师兄给了一个 cpptraj 的**通用模板**（如 `2YKI/equilibration/e1_sigma1.5/analysis.in` 那种：parm/reference、trajin、autoimage、rms、distance），换体系时**只按具体原则改几处**：配体残基号（以 amber.pdb 为准）、蛋白侧监控残基与原子（如 :78@OD2 / :79@OD2）、配体侧原子名（如 O2/N6，来自 PyMOL polar contacts）、以及输出文件名里的配体名。
- **原则**：amber.pdb 定残基号；PyMOL 定蛋白–配体原子对；atom_l 对应到配体原子名。脚本里的配置表 + 自动写 `analysis.in` 就是把这条“师兄模板 + 按体系改”的流程固化，避免手改出错。

### Equilibration 分析结果与 Production / 备用 Equilibration 部署

#### Equilibration Distance 分析结论

| 体系 | 解离起始 sigma_OP | 最优 sigma_OP（production 用） | 备用 sigma（新建 equil） |
| ---- | ----------------- | ------------------------------ | ------------------------ |
| 2YKI | **2.2**     | **2.0**                  | 2.1                      |
| 5J2X | **2.6**     | **2.4**                  | 2.5                      |
| 4EFU | **2.4**     | **2.2**                  | 2.3                      |

#### Production 部署（每体系 6 replicas）

从对应的最优 equilibration 目录复制 `gamd-1.rst`、`gamd-restart.dat`、`step3_input.parm7`；md.in 改为 production 参数（`irest_gamd=1, ntcmd=0, nteb=0, nstlim=50000000, ntpr=500, ntwx=500`，`-c gamd-1.rst`）。

| 体系 | Production 目录        | sigma_OP | 源 Equilibration | Job ID 范围          |
| ---- | ---------------------- | -------- | ---------------- | -------------------- |
| 2YKI | `production/2.0_1~6` | 2.0      | `e1_sigma2.0`  | 32923547 – 32923552 |
| 5J2X | `production/2.4_1~6` | 2.4      | `e1_sigma2.4`  | 32923553 – 32923558 |
| 4EFU | `production/2.2_1~6` | 2.2      | `e1_sigma2.2`  | 32923559 – 32923564 |

#### 备用 Equilibration 部署

万一 production 未观察到解离，可用这些备用的更高 sigma 跑 production。

| 体系 | 新建目录        | sigma_OP | Job ID   |
| ---- | --------------- | -------- | -------- |
| 2YKI | `e1_sigma2.1` | 2.1      | 32923565 |
| 5J2X | `e1_sigma2.5` | 2.5      | 32923566 |
| 4EFU | `e1_sigma2.3` | 2.3      | 32923567 |

### 当日正在跑的任务

- **Production**：2YKI (2.0_1~6)、5J2X (2.4_1~6)、4EFU (2.2_1~6) — 共 18 个 production replicas
- **Equilibration（备用）**：2YKI e1_sigma2.1、5J2X e1_sigma2.5、4EFU e1_sigma2.3 — 共 3 个
- **其他**：11 个体系的 equilibration Distance/RMSD 分析正在后台运行（batch_analysis_hsp90.sh）

### 2YKJ cMD 前置门禁检查（阻断）

- **门禁结果**：`sacct -j 32805935` 当前仍为 `PENDING`（`State=PENDING, ExitCode=0:0`，尚未开始/完成）。
- **文件核对**：`2YKJ/cMD/charmm-gui-7187586401/amber/` 下仍无 `step5_10.rst7` / `step5_10.nc` / `step5_10.out`。
- **结论**：本轮不创建 2YKJ 的 `equilibration/e1_sigma*`，避免误提任务；待 cMD 完成后再执行标准拷贝与提交流程。

### 2BSM 当前状态核查

- **现状**：`2BSM` 目前只有 `cMD/charmm-gui-7188753824/amber` 的输入文件；未见 cMD 产物 `step5_10.rst7` / `step5_10.nc`，也无 `equilibration/` 与 `production/` 目录。
- **判断**：当前不是“参数缺失”，而是处于 **cMD 尚未完成（或尚未提交）** 的前置阶段。

### 当日处理结果（全项目状态总表机制落地）

- 新增全项目状态面板：`.antigravity/running_status.md`（每天读一份就能看到全体系进度）。
- 新增参数主表：`.antigravity/system_parameters_master.md`（集中记录 `atom_p/atom_l/dblig/timask1` 与来源文件）。
- 后续 `CHANGELOG.md` 只做“每日增量状态更新”；参数与全局快照同步维护在上述两份文件。

### 3LDP：解离阈值判定与新一轮提交

- **Distance 结论**：`3LDP` 在 `sigma_OP = 1.8` 开始出现解离，故当前 production 选 `sigma_OP = 1.5`。
- **Production 部署**：新建并提交 `3LDP/production/1.5_1~6`（共 6 个 replicas），Job IDs：`32924376`–`32924382`。
- **备用 Equilibration 部署**：新建并提交 `3LDP/equilibration/e1_sigma1.6`、`3LDP/equilibration/e1_sigma1.7`，Job IDs：`32924383`、`32924384`。
- **用途**：若 `1.5` 的 production 未稳定观察到目标事件，可继续用 `1.6/1.7` 的 equilibration 结果作为后续 production 候选。

### 5J82 / 5J86：解离阈值判定与生产/备用 Equilibration 部署

| 体系 | 解离起始 sigma | 选定 production sigma | Production Job IDs | 备用 Equilibration | Equil Job ID |
| ---- | -------------- | --------------------- | ------------------ | ------------------ | ------------ |
| 5J82 | 2.6            | 2.4                   | 32926991–32926996 | e1_sigma2.5        | 32927056     |
| 5J86 | 2.8            | 2.6                   | 32927003–32927009 | e1_sigma2.7        | 32927057     |

### 5J6L / 5J6M / 5J6N / 5J8U：解离阈值判定与生产/备用 Equilibration 部署

| 体系 | 解离起始 sigma | 选定 production sigma | Production Job IDs | 备用 Equilibration | Equil Job ID |
| ---- | -------------- | --------------------- | ------------------ | ------------------ | ------------ |
| 5J6L | 2.6            | 2.4                   | 32926450–32926455 | e1_sigma2.5        | 32926479     |
| 5J6M | 2.8            | 2.6                   | 32926458–32926463 | e1_sigma2.7        | 32926480     |
| 5J6N | 2.8            | 2.6                   | 32926464–32926469 | e1_sigma2.7        | 32926481     |
| 5J8U | 2.8            | 2.6                   | 32926470–32926478 | e1_sigma2.7        | 32926482     |

- 每个体系各建 6 个 production replicas（`gamd-1.rst` 均已从对应 equilibration 目录复制）。
- 备用 equilibration 目录（`e1_sigma{2.5/2.7}`）已建立并提交，供后续更高 sigma 的 production 备用。

### 5J2X：e1_sigma2.5 状态核查与 production 2.5 目录预建

- **e1_sigma2.5 状态**：Job `32923566` 仍为 `PENDING`（尚未开始运行），目录下只有 `step3_input.parm7` / `md.in` / `run-equil.pbs` / `step5_10.rst7`，无 `md-1.nc` / `gamd-1.rst`。任务已在队列中，无需重新提交。
- **production 2.5 预建**：已新建 `5J2X/production/2.5_1~6` 共 6 个目录，`md.in`（sigma0P=2.5）和 `run-equil.pbs` 已写入，`step3_input.parm7` 已复制。
- **待操作**：等 `e1_sigma2.5` 跑完后，将其 `gamd-1.rst` 和 `gamd-restart.dat` 复制到 `2.5_1~6` 各目录，再逐一 `sbatch` 提交。

## 2026-02-26

### Batch analysis 脚本更新（按学长建议）

- 更新 `_scripts/batch_analysis_hsp90.sh`：生成 `sys-protein.pdb` 时优先读取同目录 `md.in` 的 `ntwprt`，并改用 `strip !(@1-ntwprt)` 保留复合物原子；仅在 `ntwprt` 缺失时回退旧逻辑。
- 新增可选严格报错机制（默认不影响现有流程）：
  - `STRICT_MODE=1`：若发现 equilibration 的 distance 文件缺失或末步 `< MIN_EQ_STEPS`，脚本最终返回非零退出码。
  - `MIN_EQ_STEPS` 默认 `3900`，可按需覆盖。
- 生产目录扫描增加跳过 `_` 前缀目录，避免误处理归档目录。

### 结果更新：5J2X 与 2YKI production

- **5J2X (`2.4_1~6`)**：distance 均已生成；`2.4_3/4/5/6` 明显解离，`2.4_2` 也出现上升。
- **2YKI (`2.0_1~6`)**：6 个 replica 均观察到解离。
- 按当前结论将 `5J2X` 备用 production `2.5_1~6` 从 `production/` 主目录移至：
  `.antigravity/archive/5J2X_production_sigma2.5/`

### 全体系 Equilibration 完整性核查（fact check）

- 判据（修正后）：以 `md.in` 的 `nstlim/ntwx` 计算理论完整步数（equilibration 通常为 `4400`），`distance` 最后步数达到该值才视为完整。
- 核查显示若干体系存在短轨迹或缺 distance（主要集中在高 sigma 或新提交但尚未完成的目录），全量统计已同步到：
  `.antigravity/running_status.md`
- 当前最典型未齐项：
  - `5J2X/e1_sigma2.5`、`2YKI/e1_sigma2.1`、`4EFU/e1_sigma2.3`、`3LDP/e1_sigma1.6/1.7`：有 `md-1.nc` 但无 distance（或仍在运行中）。
  - `5J8U` 部分 sigma 的 distance 末步显著低于理论完整步数 `4400`（短轨迹）。

### 日志与文件结构整理

- 将参数总表置顶合并到 `.antigravity/running_status.md`。
- 新增项目根目录参数镜像：`system_parameters_master.md`（便于直接查看）。
- 规则更新：每日主记录只维护 `CHANGELOG.md` + `.antigravity/running_status.md`；其余分析日志仅作中间记录。

### 短轨迹复核与 5J8U 定向重跑

- 对所有 `distance` 偏短目录做了参数一致性核查：这些目录的 `md.in` 关键项一致（`nstlim=22000000`, `ntcmd=2000000`, `nteb=20000000`），未发现“输入参数写错”。
- 重点复核 `5J8U` 发现并非全部轨迹短：
  - `e1_sigma1.5/1.8/2.0/2.2/2.4/2.6/3.5` 的 `gamd-1.log` 已到 `22000000`（100%）。
  - 真正未跑满的是 `e1_sigma2.8`（约 15.5%）与 `e1_sigma3.0`（约 9.1%）；`e1_sigma2.7` 尚无 `md-1.nc`。
- 已按“保留原目录 + 新建重跑目录”执行：
  - 新建 `5J8U/equilibration/Rerun/`
  - 定向提交 `e1_sigma2.7/2.8/3.0` 三个重跑任务，Job IDs：`33044144`–`33044146`
- 同时对 `5J8U` 原目录重新跑一轮 cpptraj 分析，确认目前仅 `2.8` 与 `3.0` 的 distance 仍短，其余 sigma 的 distance 已补齐到完整步数。

### 5J8U Rerun 任务撤销（按用户确认）

- 用户已明确 `5J8U` 的 production 采用 `sigma=2.6`，且 production 已在跑；不再需要新增 equilibration rerun。
- 已取消刚提交的 3 个 `5J8U-R1` 任务：`33044144`、`33044145`、`33044146`。

## 2026-03-03

### 当日文件变更与错误修复

**修改文件**

- `5J64/production/2.2_1~6/md.in`（新建）
- `5J64/production/2.2_1~6/run-equil.pbs`（新建）
- `5J64/production/2.2_1~6/gamd-1.rst`（从 e1_sigma2.2 复制）
- `5J64/production/2.2_1~6/step3_input.parm7`（从 e1_sigma2.2 复制）
- `5J8M/production/2.6_1~6/md.in`（新建）
- `5J8M/production/2.6_1~6/run-equil.pbs`（新建）
- `5J8M/production/2.6_1~6/gamd-1.rst`（从 e1_sigma2.6 复制）
- `5J8M/production/2.6_1~6/step3_input.parm7`（从 e1_sigma2.6 复制）
- `3LDP/production/1.6_1~6/md.in`（新建，sigma0P=1.6）
- `3LDP/production/1.6_1~6/run-equil.pbs`（新建）
- `3LDP/production/1.6_1~6/gamd-1.rst`（从 e1_sigma1.6 复制）
- `3LDP/production/1.6_1~6/step3_input.parm7`（从 1.5_1 复制）
- `.antigravity/running_status.md`（更新队列状态与 production sigma 表）

**发现的问题**

- 3LDP production 1.5 解离轮数不够，需要补跑 sigma=1.6 的 6 轮 production。
- 确认 `3LDP/equilibration/e1_sigma1.6/gamd-1.log` 最后一步 `total_nstep=22000000 == nstlim=22000000`，已完整跑完。

**采取的更新**

- 按参数（5J64: ntwprt=3314, edpro=3283, :211; 5J8M: ntwprt=3326, edpro=3295, :212）生成 production md.in（igamd=28, irest_gamd=1, ntcmd=0, nstlim=50000000）。
- 提交全部 12 个 production 任务（5J64+5J8M）。
- 为 3LDP 新建 `production/1.6_1~6`，从 `e1_sigma1.6` 复制 `gamd-1.rst`，sigma0P=1.6，提交 6 个任务。
- Distance 脚本现状核查：无 cpptraj/batch_analysis 进程正在运行；3LDP 1.5 production 的 distance 数据已完整（6 replicas 各 100001 行）。

### 当日正在跑的任务

- **Production**：5J64 (2.2_1~6) — 6 replicas，Job IDs: 34355260–34355265（部分 RUNNING）
- **Production**：5J8M (2.6_1~6) — 6 replicas，Job IDs: 34355266–34355269, 34355276–34355277（PENDING）
- **Production**：3LDP (1.6_1~6) — 6 replicas，Job IDs: 34356760–34356765（PENDING）

### 当日处理结果

- **5J64**：选定 production sigma = 2.2，新建 2.2_1~6 并提交，Job IDs 34355260–34355265
- **5J8M**：选定 production sigma = 2.6，新建 2.6_1~6 并提交，Job IDs 34355266–34355269, 34355276–34355277
- **3LDP**：e1_sigma1.6 已确认完成（total_nstep=22000000）；新建 1.6_1~6 并提交，Job IDs 34356760–34356765
- **Distance 脚本**：当前无运行中的分析进程；3LDP 1.5 distance 数据完整（各 100001 行）

### 全体系现状快照（每日末尾表）

| 系统 | 本次更新内容                          | 是否已解离 | 选定 production sigma | production 任务状态                       |
| ---- | ------------------------------------- | ---------- | --------------------- | ----------------------------------------- |
| 5J64 | 新建 2.2_1~6，提交 production         | 待判定     | 2.2                   | 2.2_1~6 部分 RUNNING (34355260–34355265) |
| 5J8M | 新建 2.6_1~6，提交 production         | 待判定     | 2.6                   | 2.6_1~6 PENDING (34355266–34355277)      |
| 3LDP | e1_sigma1.6 完成，新建 1.6_1~6 并提交 | 待判定     | 1.6                   | 1.6_1~6 PENDING (34356760–34356765)      |

### 4EFU Production 扩展

- **结果观察**：4EFU 在 sigma_OP = 2.2 的前六轮 production (`2.2_1~6`) 中没有观察到解离；而在 `2.3` 和 `2.4` 则观察到解离。
- **操作**：为了获得在 `2.2` 的解离事件，我们在 `4EFU/production/` 下补充提交了第 7 到第 12 轮（`2.2_7~12`），Job IDs: 34567822, 34567829-34567833。

### 5J6L Production

- **提交情况**：在 sigma_OP = 2.5 重新提交了 6 轮 Production（`2.5_1~6`）。
- **参数变化**：使用 `e1_sigma2.5` 的 `gamd-1.rst` 和 `gamd-restart.dat`。

### 3LDP Production

- **提交情况**：在 sigma_OP = 1.5 重新提交了 6 轮 Production（`1.5_1~6`）。
- **参数变化**：使用 `e1_sigma1.5` 的 `gamd-1.rst` 和 `gamd-restart.dat`，延长到 `50000000` 步。

### 5J27 Production 与 Equilibration 补传

- **现有状态**：确认 5J27 之前没有提交过 production。
- **提交情况**：
  - 基于 sigma_OP = 2.6 新建并提交了 6 轮 Production（`2.6_1~6`）。
  - 补充提交了第 1 个 sigma_OP = 2.7 的 Equilibration（`e1_sigma2.7`）以备未来之用。

## 2026-03-05

### 当日文件变更与错误修复

**修改文件**

- `5J27/production/2.6_1~6/md.in`
- `5J27/production/2.6_1~6/gamd-1.rst`
- `5J27/production/2.6_1~6/gamd-restart.dat`
- `5J6L/production/2.5_1~6/md.in`
- `5J6L/production/2.5_1~6/gamd-1.rst`
- `5J6L/production/2.5_1~6/gamd-restart.dat`
- `4EFU/production/2.2_7~12/md.in`
- `4EFU/production/2.2_7~12/gamd-1.rst`
- `4EFU/production/2.2_7~12/gamd-restart.dat`
- `2YKJ/equilibration/e1_sigma1.5~3.5/md.in`（重建）
- `2YKJ/equilibration/e1_sigma1.5~3.5/run-equil.pbs`（重建）
- `2YKJ/equilibration/e1_sigma1.5~3.5/step3_input.parm7`（从 cMD 复制）
- `2YKJ/equilibration/e1_sigma1.5~3.5/step5_10.rst7`（从 cMD 复制）
- `.antigravity/running_status.md`
- `.antigravity/system_parameters_master.md`
- `system_parameters_master.md`
- `CHANGELOG.md`

**发现的问题**

- `5J27/production/2.6_1~6`、`5J6L/production/2.5_1~6`、`4EFU/production/2.2_7~12` 的 `dis-*.dat` 只有约 `4401` 行；对照 `md.in` 和 `md-1.out`，确认这些 production 实际使用了 `nstlim=22000000`、`ntwx=5000` 的短程设置。
- 这三批目录都把 `irest_gamd=1`、`ntcmd=0`、`nteb=0` 改成了 production 形式，但遗漏了 `nstlim`、`ntpr`、`ntwx`，说明昨天是“部分改参”，不是完整套用标准 production 模板。
- 由于 `pmemd.cuda` 使用 `-c gamd-1.rst -r gamd-1.rst`，错误短跑结束后目录内 `gamd-1.rst` 已被覆盖；若不从对应 equilibration 目录重新复制，重提会从错误 production 终点继续跑。
- 全仓库复查后，仅 `3LDP/production/1.5_1~6` 仍存在历史参数/结果不一致：当前 `md.in/md-1.out` 显示 `22000000/5000`，但现存 `dis` 为 `100001` 点，需后续单独追溯；其余 production 未发现同类“步数漏改”问题。
- `2YKJ` 旧的 equilibration 错误目录此前已归档；现在 cMD 已真正产出 `step5_10.rst7`，可以按原先确认过的参数（`timask1=:210`, `atom_p=1252`, `atom_l=1`, `dblig=2.3`）正式重建并提交。
- `2BSM` 当前不再是“缺 cMD 材料”；仓库里已有 `step5_10.rst7` / `step5_10.nc`，但还没有已确认的 reaction residue / atom 编号记录，因此尚不能开始 LiGaMD3 `equilibration`。

**采取的更新**

- 将上述 18 个 production 目录统一修正为标准 production 参数：`nstlim=50000000`、`ntpr=500`、`ntwx=500`。
- 从对应 `e1_sigma*` 目录重新复制 `gamd-1.rst` 与 `gamd-restart.dat`，确保重提从 equilibration 终点而非错误短跑终点启动。
- 将原有短程 `dis-*.dat` 改名为 `bad_short_run_*`，避免后续 distance 分析脚本误判为已完成。
- 按提交前查重规则重新 `sbatch` 提交 18 个任务：`5J27` `34905914–34905919`，`5J6L` `34905920–34905925`，`4EFU` `34905926–34905931`。
- 使用 `_archive/2YKJ_equilibration_old_error/` 中已确认参数的 `md.in/run-equil.pbs` 作为模板，重建 `2YKJ/equilibration/e1_sigma1.5–3.5` 共 9 个目录，并从当前 cMD 复制 `step3_input.parm7` 与 `step5_10.rst7`。
- 提交 `2YKJ` 的 9 个 equilibration 任务：`34907705–34907715`（缺 `34907708/12`，对应 `e1.5,1.8,2.0,2.2,2.4,2.6,2.8,3.0,3.5`）。

### 当日正在跑的任务

- **Production**：`5J27` (`2.6_1~6`) — 6 个 replicas，Job IDs: `34905914–34905919`
- **Production**：`5J6L` (`2.5_1~6`) — 6 个 replicas，Job IDs: `34905920–34905925`
- **Production**：`4EFU` (`2.2_7~12`) — 6 个 replicas，Job IDs: `34905926–34905931`
- **Equilibration**：`2YKJ` (`e1_sigma1.5–3.5`) — 9 个 sigma，Job IDs: `34907705–34907715`（缺 `34907708/12`）

### 当日处理结果

- **5J27**：确认昨天新建的 `2.6_1~6` 使用了 equilibration 的短程步数；已修正为标准 production 参数并全部重提。
- **5J6L**：确认昨天重提的 `2.5_1~6` 同样遗漏 `nstlim/ntwx` 修改；已修正并全部重提。
- **4EFU**：确认昨天补开的 `2.2_7~12` 也是同一类部分改参错误；已修正并全部重提。
- **剩余体系复查**：除 `3LDP/production/1.5_1~6` 的历史不一致需后续追溯外，其余 production 未发现新的“用错 equilibration 步数”目录。
- **2YKJ**：cMD 完成后，已按既定参数重建并提交 9 个 `equilibration/e1_sigma*` 任务，后续可直接按标准流程补跑 distance 和筛选 sigma。
- **2BSM**：确认当前阻断点是 reaction residue / atom 参数尚未落表，不是缺 cMD 产物。

### 全体系现状快照（每日末尾表）

| 系统 | 本次更新内容                                                     | 是否已解离 | 选定 production sigma    | production 任务状态                                   |
| ---- | ---------------------------------------------------------------- | ---------- | ------------------------ | ----------------------------------------------------- |
| 5J27 | 修正 `2.6_1~6` 的 production 步数并重提                        | 待判定     | 2.6                      | `2.6_1~6` PENDING (`34905914–34905919`)          |
| 5J6L | 修正 `2.5_1~6` 的 production 步数并重提                        | 待判定     | 2.4（既定），2.5（补跑） | `2.5_1~6` PENDING (`34905920–34905925`)          |
| 4EFU | 修正 `2.2_7~12` 的 production 步数并重提                       | 待判定     | 2.2                      | `2.2_7~12` PENDING (`34905926–34905931`)         |
| 3LDP | 全仓库复查时发现 `1.5_1~6` 存在历史参数/结果不一致，待单独追溯 | 待判定     | 1.5（既定），1.6（补跑） | `1.5_1~6` 已有结果，`1.6_1~6` 待后续确认          |
| 2YKJ | cMD 完成后重建并提交 `e1_sigma1.5–3.5`                        | 待判定     | 待定                     | `e1_sigma1.5–3.5` PENDING (`34907705–34907715`) |
| 2BSM | cMD 已完成，待确认 reaction residue / atom 参数                  | 待判定     | 待定                     | 未提交                                                |

## 2026-03-22

### 4FKx 体系下载记录汇总

本次将 `4FKO / 4FKP / 4FKR / 4FKS / 4FKT / 4FKU / 4FKV / 4FKW` 这 8 个体系的实验结构文件与 AlphaFold 下载信息统一整理，后续手动对齐和 SWISS-MODEL 补残都以这里为准。

#### 1. UniProt 编号

这 8 个体系全部映射到同一个蛋白目标：

- 蛋白：`CDK2_HUMAN`
- UniProt accession：`P24941`
- 实验结构链：`A`
- AlphaFold 条目：`AF-P24941-F1`
- AlphaFold PDB：`AF-P24941-F1-model_v6.pdb`

UniProt 编号的判定依据来自各自实验 PDB 的 `DBREF` 记录。

示例（`4FKR.pdb`）：

```text
DBREF  4FKR A    1   298  UNP    P24941   CDK2_HUMAN       1    298
```

#### 2. 缺失区间

这里记录的“缺失区间”指的是**实验 PDB 结构里缺失、后续需要从 AlphaFold 借坐标来补的残基区间**，不是说 AlphaFold 模型本身缺这些残基。

缺失区间通过实验 PDB 的 `REMARK 465` 读取并按连续编号归并得到。

| 体系 | UniProt | 配体 | 需要从 AlphaFold 补的缺失区间 |
| ---- | ------- | ---- | ----------------------------- |
| 4FKO | P24941  | 20K  | 38-44                         |
| 4FKP | P24941  | LS5  | 36-43；153-162                |
| 4FKR | P24941  | 45K  | 38-44；154-162                |
| 4FKS | P24941  | 46K  | 36-44；151-162；297-298       |
| 4FKT | P24941  | 48K  | 36-44；153-161；297-298       |
| 4FKU | P24941  | 60K  | 38-42                         |
| 4FKV | P24941  | 61K  | 38-42；151-161                |
| 4FKW | P24941  | 62K  | 38-42；150-162                |

示例读取方式：

```bash
rg -n "^REMARK 465|^DBREF" HSP90_structures/new_systems/4FKR/4FKR.pdb
```

示例（`4FKR.pdb`）：

```text
REMARK 465     ASP A    38
REMARK 465     THR A    39
REMARK 465     GLU A    40
REMARK 465     THR A    41
REMARK 465     GLU A    42
REMARK 465     GLY A    43
REMARK 465     VAL A    44
REMARK 465     VAL A   154
...
REMARK 465     GLU A   162
```

归并后即：

- `38-44`
- `154-162`

#### 3. AlphaFold 是怎么下载的

AlphaFold 文件来自 **官方 AlphaFold EBI 站点**，不是从 RCSB 下载。

步骤如下：

1. 用 UniProt accession 查询 AlphaFold API：

```bash
curl -fL "https://alphafold.ebi.ac.uk/api/prediction/P24941" \
  -o HSP90_structures/new_systems/4FKR/alphafold/P24941_prediction.json
```

2. 从返回的 JSON 里读取官方 `pdbUrl`：

```text
https://alphafold.ebi.ac.uk/files/AF-P24941-F1-model_v6.pdb
```

3. 直接下载官方 AlphaFold PDB：

```bash
curl -fL "https://alphafold.ebi.ac.uk/files/AF-P24941-F1-model_v6.pdb" \
  -o HSP90_structures/new_systems/4FKR/alphafold/AF-P24941-F1-model_v6.pdb
```

4. 同时下载官方 UniProt FASTA：

```bash
curl -fL "https://rest.uniprot.org/uniprotkb/P24941.fasta" \
  -o HSP90_structures/new_systems/4FKR/alphafold/P24941_uniprot.fasta
```

补充说明：

- 因为这 8 个体系全部对应同一个 UniProt `P24941`，所以实际使用的是同一个 AlphaFold 主条目 `AF-P24941-F1-model_v6.pdb`
- 操作上是先按官方 URL 下载一次，再复制到每个体系各自的 `alphafold/` 目录

#### 3.5 为什么选 `AF-P24941-F1-model_v6.pdb`

这里选的是：

- `AF-P24941-F1`
- `model_v6`

不是因为它“分辨率更高”，而是因为 AlphaFold 这里真正区分的是：

- **UniProt 条目/isoform 是否匹配**
- **数据库版本是否是当前最新**
- **置信度信息（pLDDT / PAE）**

不是晶体学里的 `resolution`。

具体判断逻辑：

1. 实验 PDB 的 `DBREF` 明确写的是 `P24941`
2. 这条实验链覆盖 `1-298`
3. AlphaFold API 返回两个相关条目：
   - `AF-P24941-F1`：canonical，`1-298`
   - `AF-P24941-2-F1`：isoform 2，`1-264`
4. 因为实验结构是 canonical 的 298 aa 蛋白，所以必须选 `AF-P24941-F1`
5. API 返回 `latestVersion = 6`，所以下载 `model_v6`

换句话说，这里选 `AF-P24941-F1-model_v6.pdb` 的依据是“**和实验结构链完全匹配 + 官方当前最新版本**”，不是按“分辨率”选的。

#### 3.6 现已改回本组实际在用的 PyMOL workflow

这里的目标不是让 AlphaFold 替换整个实验结构，而是：

1. 以实验复合物为主
2. 把 AlphaFold 结构刚性对齐到实验蛋白骨架上
3. 只从 AlphaFold 里取实验结构缺失的那几段残基
4. 用 `cmd.copy_to(...)` 把缺失段复制到实验对象里
5. 直接把这个处理后的 object 保存为 `[PDB_ID]_prepare_for_swiss.pdb`

这里之前做过一版 `*_swiss_template_candidate.pdb` 的“clean merged template”尝试，但后来确认这和组里实际上传 SWISS-MODEL 的习惯不一致，现已回退到 `prepare_for_swiss` 工作流。

这里有两个逻辑必须分清：

- **共享的部分**：都用 `AF-P24941-F1-model_v6.pdb`，都按蛋白 `chain A` 的 CA 原子对齐
- **不共享的部分**：每个体系的缺失区间不同，保留的配体名不同，所以每个体系的 `select gap*` 和 `remove exp and not (...)` 都必须单独写

#### 3.7 4FKW 示例：实际使用过的 PyMOL 指令

示范脚本文件：

- `HSP90_structures/new_systems/4FKW/prepare_4FKW_missing_segments.pml`

脚本主体如下：

```pymol
reinitialize

load /Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures/new_systems/4FKW/4FKW.pdb, exp
load /Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures/new_systems/4FKW/alphafold/AF-P24941-F1-model_v6.pdb, af

remove exp and not ((polymer.protein and chain A) or (resn 62K and chain A and resi 301) or (resn ACE and chain A and resi 0))
remove exp and solvent
remove exp and resn ACE

remove af and not (polymer.protein and chain A)

align af and polymer.protein and chain A and name CA, exp and polymer.protein and chain A and name CA

select gap1, af and chain A and resi 38-42
select gap2, af and chain A and resi 150-162

cmd.copy_to("exp", "gap2", zoom=0, quiet=0)
cmd.copy_to("exp", "gap1", zoom=0, quiet=0)

save HSP90_structures/new_systems/4FKW/4FKW_prepare_for_swiss.pdb, exp
```

#### 3.8 每条 PyMOL 指令是什么意思

`reinitialize`

- 清空当前 PyMOL 会话，避免旧对象干扰新体系。

`load ... 4FKW.pdb, exp`

- 把实验结构读入，命名为 `exp`。
- 后面所有“以实验结构为准”的操作都针对这个对象。

`load ... AF-P24941-F1-model_v6.pdb, af`

- 把 AlphaFold 结构读入，命名为 `af`。
- 它只作为补缺失片段的坐标来源。

`remove exp and not ((polymer.protein and chain A) or (resn 62K and chain A and resi 301) or (resn ACE and chain A and resi 0))`

- 在实验结构对象里，只保留：
  - 蛋白链 `A`
  - 配体实例 `62K A 301`
  - 末端修饰 `ACE A 0`
- 这样做的目的是从源头上避免把 `GOL/ACT/NA` 这类也属于 `chain A` 的杂原子误保留下来。

`remove exp and solvent`

- 删除水分子。

`remove exp and resn ACE`

- 删除 `ACE` 这个非天然 N 端 cap。
- 原因：后面做 SWISS-MODEL 时，模板 PDB 的蛋白序列要和天然 FASTA 一致，`ACE` 不能保留。

`remove af and not (polymer.protein and chain A)`

- AlphaFold 结构本身通常只有蛋白，但这里仍显式只保留蛋白链 `A`，让对象语义清楚。

`align af and polymer.protein and chain A and name CA, exp and polymer.protein and chain A and name CA`

- 这是核心对齐命令。
- 含义是：用**蛋白主链的 CA 原子**，把 `af` 刚性叠合到 `exp` 上。
- 我没有直接用所有原子去对齐，是因为：
  - CA 对齐更稳
  - 侧链差异和局部构象噪声更少
  - 适合做“先叠整体骨架，再借缺失段”

`select gap_38_42, af and chain A and resi 38-42`

- 从 AlphaFold 对象里选中第一段缺失区。

`select gap_150_162, af and chain A and resi 150-162`

- 从 AlphaFold 对象里选中第二段缺失区。

`cmd.copy_to("exp", "gap2", zoom=0, quiet=0)`

- 把 `gap2` 这段 AlphaFold 片段复制到 `exp` 这个实验对象里。
- 这一步之后，PyMOL 可能会提示 `Uniquify` 修改 chain / segi；这是当前组里工作流里的正常现象。

`cmd.copy_to("exp", "gap1", zoom=0, quiet=0)`

- 再把另一段缺失片段复制到同一个 `exp` object 里。

`save ... 4FKW_prepare_for_swiss.pdb, exp`

- 直接保存当前 object，作为上传到 SWISS-MODEL 的模板文件。

#### 3.9 实际对齐结果

PyMOL 的实际 CA 对齐结果如下：

| 体系 | RMSD (A) | 对齐 CA 原子数 |
| ---- | -------- | -------------- |
| 4FKO | 0.680    | 228            |
| 4FKP | 0.570    | 226            |
| 4FKR | 0.569    | 229            |
| 4FKS | 0.472    | 213            |
| 4FKT | 0.520    | 222            |
| 4FKU | 0.546    | 222            |
| 4FKV | 0.478    | 227            |
| 4FKW | 0.492    | 218            |

现已统一生成这 8 个体系的 `*_prepare_for_swiss.pdb`，并删除了旧的 `*_swiss_template_candidate.pdb`、`*_exp_noACE_complex.pdb`、`*_missing_patch_from_alphafold.pdb` 等中间产物。

这说明对齐在整体骨架层面是合理的，但它**并不自动等于可以直接拿去做最终模型**。后面仍必须人工检查：

1. 缺失段前后的锚点是否接得上
2. 是否有重复残基被带进去
3. 缺失段有没有明显穿过配体或主链
4. 配体是否还在原始 pocket 位置

#### 3.10 为什么 sequence 里仍然可能看到灰 gap

这次重新确认后，组里当前实际 workflow 是：

- 在 PyMOL 里对齐 `exp` 和 `af`
- 用 `copy_to` 把缺失段复制到 `exp`
- sequence 上原始实验链仍然可能保留灰 gap
- 直接把这个 object 保存成 `prepare_for_swiss.pdb`

换句话说，灰 gap 并不自动说明“模板没准备好”；关键是 copied AF 片段已经在同一个 saved object 里，并且 SWISS-MODEL 可以识别这个 template。

#### 3.11 SWISS-MODEL API 本地化策略

根据 SWISS-MODEL 官方帮助页里的 Modelling API 说明，`/user_template` 端点支持直接提交：

- `target_sequences`
- `template_coordinates`
- `project_title`

并可通过：

- `GET /project/{project_id}/models/summary/` 查询状态
- `coordinates_url` 下载 PDB 结果
- `POST /projects/download/` 打包下载全部 API 创建的项目

本地脚本 `scripts/swiss_model_api.py` 现已改成：

- 读取 `[PDB_ID]_prepare_for_swiss.pdb` 作为模板
- 读取对应 FASTA，并自动移除其中的 `X`
- 支持 `submit` / `submit_all` / `status` / `download` / `bulk_download`

#### 4. 当前每个 4FKx 目录里应有的文件

- 实验结构：`*.pdb`
- 实验结构：`*.cif`
- 实验链 FASTA：`*.fasta`
- AlphaFold 元数据：`alphafold/P24941_prediction.json`
- UniProt FASTA：`alphafold/P24941_uniprot.fasta`
- AlphaFold 结构：`alphafold/AF-P24941-F1-model_v6.pdb`
- PyMOL 对齐脚本：`prepare_[PDB_ID]_missing_segments.pml`
- 上传前模板：`[PDB_ID]_prepare_for_swiss.pdb`
- SWISS-MODEL 返回结果：`[PDB_ID]_swiss_prepared_model.pdb` 或 `[PDB_ID]_swissmodel_output.pdb`
- SWISS 后最终复合物：`[PDB_ID]_final_complex.pdb`
- CHARMM-GUI 上传集合：`new_systems/[PDB_ID]/charmm_gui_ready/`

#### 5. 校验方法

后续如果要确认这些下载是否正确，优先检查：

1. 实验 PDB 的 `DBREF` 是否指向 `P24941`
2. AlphaFold JSON 的 `entryId` 是否为 `AF-P24941-F1`
3. AlphaFold JSON 里的 `pdbUrl` 是否与下载文件名一致
4. AlphaFold 条目是否覆盖残基 `1-298`
5. 缺失区间是否来自实验 PDB 的 `REMARK 465`，而不是手工猜测

## 2026-03-23 - SWISS API FastTrack 跑通并补全 4FKx 的 CHARMM-GUI 输入

### 结果概览

- 已确认 `4FKO` 的网页 SWISS 结果和 API 结果在结构内容上等价：
  - `ATOM/HETATM` 记录完全一致
  - 差异只在文件头的项目标题
- 已通过 API 成功提交并下载以下 6 个此前未跑完的体系：
  - `4FKP -> c1327c`
  - `4FKS -> 85eb16`
  - `4FKT -> 79bc2f`
  - `4FKU -> 99fbe1`
  - `4FKV -> f331c0`
  - `4FKW -> 6882a7`
- 既有 `4FKO` API 项目：`405623`
- `4FKR` 后续也补跑了 API：`8977b7`
- 原网页输出 `4FKR_swiss_prepared_model.pdb` 已确认不适合直接送 CHARMM-GUI：
  - 含有额外 `chain B`
  - 仍带 `GOL`
  - 导致 CHARMM-GUI 把蛋白错误拆成多个 protein entry
- 当前 `4FKR` 已切换为 API 输出 `4FKR_swissmodel_output.pdb`，并重新生成干净的 `4FKR_complex.pdb`

### FASTA / 模板检查

已对 `4FKO` 到 `4FKW` 全部 8 个体系执行本地校验：

- FASTA 原始长度均为 `299 aa`
- 每个 FASTA 都含有 1 个 `X`
- 脚本提交前会自动去掉 `X`，提交给 SWISS 的长度均为 `298 aa`
- `prepare_for_swiss.pdb` 均已确认不含 `ACE/NME/HOH/WAT/GOL/ACT`
- 所有模板都含蛋白 `ATOM` 记录，并保留正确目标配体

### CHARMM-GUI 准备逻辑修正

- `HSP90_structures/scripts/prepare_charmm_gui_inputs.py`

最初版本的脚本曾采用这条路线：

1. 读取 SWISS 输出 `*_swissmodel_output.pdb` 或 `*_swiss_prepared_model.pdb`
2. 从 SWISS 输出里只保留蛋白
3. 从原始 `PDB` 里单独提取配体
4. 让 PyMOL 自动猜测并导出 ligand mol2

后续在 CHARMM-GUI 中发现这条路线对某些配体不稳：

- `4FKP` 的 `LS5` 在 `antechamber` 里报 `Weird atomic valence`
- `4FKR` 的 `45K` 在 `antechamber` 里报 `Weird atomic valence`
- `4FKT` 也出现了同类问题

因此现已改回更接近组里原始手工 PyMOL workflow 的实现：

1. 读取 SWISS 输出 `*_swissmodel_output.pdb` 或 `*_swiss_prepared_model.pdb`
2. 从 SWISS 输出里只保留蛋白 `chain A`
3. 读取原始实验结构，优先使用原始 `*.cif`
4. 用蛋白 CA 原子对齐 SWISS 输出与原始结构
5. 从原始实验结构里把目标配体复制到同一个 `complex` object
6. 在该 `complex` object 上做去水、去无关小分子、`h_add`
7. 直接从这个 `complex` object 导出 `*_complex.pdb` 和 `*_ligand_H.mol2`
8. 生成最终复合物 `new_systems/[PDB_ID]/[PDB_ID]_final_complex.pdb`
9. 生成 CHARMM-GUI 上传文件夹 `new_systems/[PDB_ID]/charmm_gui_ready/`

补充结论：

- 这里的核心问题不是 AlphaFold / SWISS 补全后的蛋白
- 问题主要出在 ligand mol2 的导出路线
- 原始 `mmCIF` 作为 ligand source 时，导出的原子型/键型会明显不同于从 `PDB` 抽配体再让 PyMOL 猜键型的结果
- 因此现在统一改为：**优先用 CIF，且在单一 complex object 里处理后再导出 CHARMM-GUI 文件**

### 新生成的文件

对 `4FKO` 到 `4FKW` 已统一生成：

- `new_systems/[PDB_ID]/[PDB_ID]_final_complex.pdb`
- `new_systems/[PDB_ID]/charmm_gui_ready/[PDB_ID].cifx`
- `new_systems/[PDB_ID]/charmm_gui_ready/[PDB_ID]_complex.pdb`
- `new_systems/[PDB_ID]/charmm_gui_ready/[PDB_ID]_ligand_H.mol2`

项目根目录下的 `charmm_gui_ready/[PDB_ID]/` 现在只是这套文件的镜像副本，便于批量查看；真正与各体系绑定的主位置是各自子目录内的 `charmm_gui_ready/`。

这意味着这 8 个体系现已进入“可直接上传 CHARMM-GUI”的状态。

## 2026-03-27 - 新增 5J9X 完整 HSP90 单链体系

### 1. 体系判断

- `5J9X` 是 HSP90-alpha N-terminal domain 单链体系，目标配体为 `6GC A 301`
- 原始 `REMARK 465` 只出现在构建体两端：
  - N 端 `9-15`
  - C 端 `224-233`
- 这不是口袋附近的内部缺口，因此当前按“完整体系”处理，不走 AlphaFold / SWISS-MODEL

### 2. 新增脚本

- 新增通用脚本：
  - `scripts/prepare_single_chain_raw_charmm_gui.py`
- 用途：
  - 为完整的单链蛋白-配体体系直接准备 CHARMM-GUI 输入
  - 当前已配置 `5J9X -> 6GC`

### 3. 已生成文件

- `new_systems/5J9X/5J9X.pdb`
- `new_systems/5J9X/5J9X.cif`
- `new_systems/5J9X/prepare_5J9X_single_chain_charmm_gui.pml`
- `new_systems/5J9X/5J9X_final_complex.pdb`
- `new_systems/5J9X/charmm_gui_ready/5J9X.cif`
- `new_systems/5J9X/charmm_gui_ready/5J9X_complex.pdb`
- `new_systems/5J9X/charmm_gui_ready/5J9X_ligand_H.mol2`

### 4. 本地校验结果

- `5J9X_final_complex.pdb` 与 `charmm_gui_ready/5J9X_complex.pdb` 当前均满足：
  - 蛋白链只有 `A`
  - 配体只有 `6GC A 301`
  - `HOH/WAT = 0`
  - 结晶添加剂 `DMS A 302` 已移除

### 5. 分类入口

- 已将 `5J9X` 加入：
  - `systems_hsp90/5J9X -> new_systems/5J9X`

## 2026-03-27 - 1D4H CHARMM-GUI 将 `BEH` 误判为 lipid type

### 1. 症状

- 用户在 CHARMM-GUI `PDB Reader` 页面上传 `1D4H` 后，页面直接报错：
  - `Error: Unsupported lipid type (BEH).`

### 2. 根因判断

- 这不是蛋白链或配体坐标错误。
- 当前上传文件中的配体残基名确实是：
  - `new_systems/1D4H/charmm_gui_ready/1D4H_complex.pdb` -> `BEH C 501`
  - `new_systems/1D4H/charmm_gui_ready/1D4H_ligand_H.mol2` -> `BEH501`
- 该行为与 workflow 第 `1.7` 节里已经记录过的 `Unsupported lipid type (XXX)` 问题一致：
  - CHARMM-GUI 将某些三字母配体名误识别为内置 lipid 类型

### 3. 证据

- `new_systems/1D4H/charmm_gui_ready/1D4H_complex.pdb`
- `new_systems/1D4H/charmm_gui_ready/1D4H_ligand_H.mol2`
- `HSP90_LiGaMD3_Complete_Workflow.md` 中 `Unsupported lipid type (XXX)` 排雷条目

### 4. 当前状态

- `1D4H` 的失败已定位为**配体命名冲突**，不是结构组织错误。
- 已执行修复：
  - 在 `scripts/prepare_hiv_dimer_raw_charmm_gui.py` 中为 `1D4H` 增加安全输出别名
  - 将输出配体名从 `BEH` 改为 `H4X`
  - 已重新生成：
    - `new_systems/1D4H/1D4H_final_complex.pdb`
    - `new_systems/1D4H/charmm_gui_ready/1D4H_complex.pdb`
    - `new_systems/1D4H/charmm_gui_ready/1D4H_ligand_H.mol2`
- 当前新文件中的目标配体已变为：
  - `H4X C 501`（PDB）
  - `H4X501`（MOL2）
- 下一步：用这套新的 `1D4H/charmm_gui_ready/` 文件重新上传 CHARMM-GUI。

## 2026-03-27 - 4FKU 选错原始晶体中的 `60K` 副本

### 1. 症状

- 用户发现 `4FKU` 从 CHARMM-GUI / Amber 回来的配体看起来离蛋白明显偏远，与其它 `4FK*` 体系不一致。

### 2. 根因

- 问题不是 CHARMM-GUI 后面才引入的，而是更早在本地准备 `4FKU_complex.pdb` 时就选错了原始晶体中的 ligand copy。
- `4FKU.pdb` 里实际有两份 `60K`：
  - `60K A 301`
  - `60K A 303`
- 旧脚本 `scripts/prepare_charmm_gui_inputs.py` 将所有 `4FKx` 都硬编码成了 `resi 301`，因此 `4FKU` 被错误地选成了 `60K A 301`。

### 3. 证据

- 原始晶体 `4FKU.pdb` 中：
  - `60K A 301` 的 `centroid_dist ≈ 31.918`
  - `60K A 303` 的 `centroid_dist ≈ 13.060`
- 旧的 `amber_4FKU.pdb` 也对应错误副本：
  - ligand id 为 `_ 301`
  - `centroid_dist ≈ 31.560`
- 重新生成后的新输入文件已切换为：
  - `60K A 303`
  - `centroid_dist ≈ 12.927`

### 4. 修复

- 已修改 `scripts/prepare_charmm_gui_inputs.py`：
  - 不再默认写死 `resi 301`
  - 若原始 PDB 中同一种配体出现多份，脚本会自动选择**距离蛋白链 A 最近的那一份**
- 已重新生成：
  - `new_systems/4FKU/4FKU_final_complex.pdb`
  - `new_systems/4FKU/charmm_gui_ready/4FKU_complex.pdb`
  - `new_systems/4FKU/charmm_gui_ready/4FKU_ligand_H.mol2`

### 5. 当前状态

- 新的 `4FKU` 上传输入现在是正确的：
  - `60K A 303`
- 旧的 `amber_4FKU.pdb` 和基于旧输入得到的 CHARMM-GUI / Longleaf 结果应视为**过期结果**，不要再用。
- 下一步：用新的 `4FKU/charmm_gui_ready/` 重新跑 CHARMM-GUI，然后再重新上传 Longleaf。
