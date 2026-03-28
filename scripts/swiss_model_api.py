#!/usr/bin/env python3
"""
SWISS-MODEL User Template API 自动化脚本

官方参考:
  https://swissmodel.expasy.org/docs/help

输入文件要求:
  1. FASTA:
     - 文件名: [PDB_ID].fasta
     - 位置:
       * repair_queue/[PDB_ID]/01_raw/[PDB_ID].fasta
       * 或 new_systems/[PDB_ID]/[PDB_ID].fasta
     - 内容:
       * 可以有一个以 ">" 开头的 header 行
       * 后续必须是目标蛋白的氨基酸序列
       * 不应包含配体、ACE/NME 等非天然残基
       * 如果有 "X"，脚本会在提交前自动移除

  2. 模板 PDB:
     - 文件名: [PDB_ID]_prepare_for_swiss.pdb
     - 位置:
       * repair_queue/[PDB_ID]/04_swissmodel/
       * repair_queue/[PDB_ID]/03_pymol/
       * 或 new_systems/[PDB_ID]/
     - 内容:
       * 来自 PyMOL 中 align + select gap + copy_to + save 的 object
       * 必须是 .pdb 文本文件
       * 应包含目标蛋白和你保留的目标配体
       * 不应包含 ACE/NME、溶剂或无关小分子
       * sequence 上仍可能看到灰 gap, 这在当前 workflow 下是允许的

用法:
  1. 先在 https://swissmodel.expasy.org/account 获取你的 API token
  2. 设置环境变量: export SWISSMODEL_TOKEN="你的token"
  3. 运行:
     python3 swiss_model_api.py validate 4FKR          # 本地检查输入文件是否合理
     python3 swiss_model_api.py submit 4FKR            # 提交单个体系
     python3 swiss_model_api.py submit_all             # 批量提交所有准备好的体系
     python3 swiss_model_api.py status                 # 查询所有已记录任务
     python3 swiss_model_api.py download all           # 下载所有已完成结果
     python3 swiss_model_api.py bulk_download          # 打包下载 API 创建的所有项目
"""

import os
import sys
import json
import time
import gzip
import urllib.error
import urllib.request

# ============================================================
# 配置
# ============================================================
BASE_URL = "https://swissmodel.expasy.org"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_SYSTEMS_DIR = os.path.join(PROJECT_ROOT, "new_systems")
REPAIR_QUEUE_DIR = os.path.join(PROJECT_ROOT, "repair_queue")

# 各体系的配体名称（手动维护，避免把配体序列送进 SWISS-MODEL）
LIGAND_MAP = {
    "4FKO": "20K",
    "4FKP": "LS5",
    "4FKR": "45K",
    "4FKS": "46K",
    "4FKT": "48K",
    "4FKU": "60K",
    "4FKV": "61K",
    "4FKW": "62K",
}

# 用于记录提交的 project_id
JOBS_FILE = os.path.join(PROJECT_ROOT, "swiss_model_jobs.json")
AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWYX")


class SimpleResponse:
    def __init__(self, status_code, body, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    @property
    def text(self):
        return self._body.decode("utf-8", errors="replace")

    @property
    def content(self):
        return self._body

    def json(self):
        return json.loads(self.text)


def http_request(url, method="GET", headers=None, json_body=None):
    headers = dict(headers or {})
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return SimpleResponse(resp.status, resp.read(), dict(resp.headers))
    except urllib.error.HTTPError as e:
        return SimpleResponse(e.code, e.read(), dict(e.headers))


def decode_pdb_payload(response):
    """把 SWISS 返回的坐标内容稳妥解码成 PDB 文本。"""
    raw = response.content
    content_encoding = str(response.headers.get("Content-Encoding", "")).lower()

    # SWISS 有时会返回 gzip 压缩内容。
    if content_encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    return raw.decode("utf-8", errors="strict")


def get_system_dir(pdb_id):
    """优先使用 repair_queue，其次回退到 new_systems"""
    repair_dir = os.path.join(REPAIR_QUEUE_DIR, pdb_id)
    legacy_dir = os.path.join(NEW_SYSTEMS_DIR, pdb_id)
    if os.path.isdir(repair_dir):
        return repair_dir
    if os.path.isdir(legacy_dir):
        return legacy_dir
    return None


def get_fasta_path(system_dir, pdb_id):
    queue_fasta = os.path.join(system_dir, "01_raw", f"{pdb_id}.fasta")
    legacy_fasta = os.path.join(system_dir, f"{pdb_id}.fasta")
    if os.path.exists(queue_fasta):
        return queue_fasta
    if os.path.exists(legacy_fasta):
        return legacy_fasta
    return None


def get_template_path(system_dir, pdb_id):
    candidates = [
        os.path.join(system_dir, "04_swissmodel", f"{pdb_id}_prepare_for_swiss.pdb"),
        os.path.join(system_dir, "03_pymol", f"{pdb_id}_prepare_for_swiss.pdb"),
        os.path.join(system_dir, f"{pdb_id}_prepare_for_swiss.pdb"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def get_output_dir(system_dir, pdb_id):
    """下载结果统一优先写回 new_systems/[PDB_ID]/"""
    legacy_dir = os.path.join(NEW_SYSTEMS_DIR, pdb_id)
    if os.path.isdir(legacy_dir):
        return legacy_dir

    queue_out = os.path.join(system_dir, "04_swissmodel")
    if os.path.isdir(queue_out):
        return queue_out
    return system_dir


def get_token():
    """从环境变量获取 SWISS-MODEL API token"""
    token = os.environ.get("SWISSMODEL_TOKEN")
    if not token:
        print("错误: 请先设置环境变量 SWISSMODEL_TOKEN")
        print("  export SWISSMODEL_TOKEN=\"你的token\"")
        print("  Token 获取地址: https://swissmodel.expasy.org/account")
        sys.exit(1)
    return token


def read_fasta_sequence(fasta_path):
    """读取 FASTA 文件，返回纯序列字符串，并移除 SWISS-MODEL 不接受的 X"""
    with open(fasta_path) as f:
        lines = f.readlines()
    
    seq_lines = [line.strip() for line in lines if not line.startswith(">")]
    sequence = "".join(seq_lines)
    
    x_count = sequence.count("X")
    if x_count:
        print(f"  注意: FASTA 中检测到 {x_count} 个 X，已在提交前自动移除")
        sequence = sequence.replace("X", "")
    
    return sequence


def read_fasta_raw(fasta_path):
    with open(fasta_path) as f:
        lines = f.readlines()
    seq_lines = [line.strip() for line in lines if not line.startswith(">")]
    return "".join(seq_lines)


def read_template_pdb(pdb_path):
    """读取模板 PDB 文件内容"""
    with open(pdb_path) as f:
        return f.read()


def validate_system_inputs(pdb_id):
    """检查 FASTA 和 prepare_for_swiss 模板是否满足基本要求"""
    sys_dir = get_system_dir(pdb_id)
    if not sys_dir:
        print(f"错误: 找不到体系目录 {pdb_id}")
        return False

    ok = True

    fasta_path = get_fasta_path(sys_dir, pdb_id)
    if not fasta_path:
        print(f"❌ {pdb_id}: 缺少 FASTA 文件")
        return False

    raw_seq = read_fasta_raw(fasta_path)
    cleaned_seq = raw_seq.replace("X", "")
    invalid_chars = sorted(set(cleaned_seq) - AA_ALPHABET)
    print(f"\n=== {pdb_id} ===")
    print(f"FASTA: {fasta_path}")
    print(f"  原始长度: {len(raw_seq)} aa")
    print(f"  去除 X 后长度: {len(cleaned_seq)} aa")
    print(f"  X 数量: {raw_seq.count('X')}")
    if invalid_chars:
        ok = False
        print(f"  ❌ 存在非法字符: {''.join(invalid_chars)}")
    else:
        print("  ✅ FASTA 字符检查通过")

    template_path = get_template_path(sys_dir, pdb_id)
    if not template_path:
        print(f"❌ {pdb_id}: 缺少 {pdb_id}_prepare_for_swiss.pdb")
        return False

    print(f"Template: {template_path}")
    atom_count = 0
    het_res = []
    bad_het = []
    with open(template_path) as f:
        for line in f:
            if line.startswith("ATOM  "):
                atom_count += 1
            elif line.startswith("HETATM"):
                resn = line[17:20].strip()
                chain = line[21].strip()
                resi = line[22:26].strip()
                key = (resn, chain, resi)
                if key not in het_res:
                    het_res.append(key)
                if resn in {"ACE", "NME", "HOH", "WAT", "GOL", "ACT"}:
                    bad_het.append(key)

    print(f"  ATOM 数量: {atom_count}")
    print(f"  HETATM 残基: {het_res if het_res else '无'}")
    if atom_count == 0:
        ok = False
        print("  ❌ 模板中没有 ATOM 记录")
    else:
        print("  ✅ 模板含有蛋白坐标")

    if bad_het:
        ok = False
        print(f"  ❌ 模板中仍有不应保留的小分子/末端残基: {bad_het}")
    else:
        print("  ✅ 未检测到 ACE/NME/水/GOL/ACT")

    if ok:
        print(f"✅ {pdb_id}: 输入文件检查通过，可以尝试提交 SWISS-MODEL")
    else:
        print(f"⚠️ {pdb_id}: 输入文件存在问题，建议先修正再提交")
    return ok


def submit_user_template(pdb_id, token):
    """提交一个体系到 SWISS-MODEL User Template"""
    sys_dir = get_system_dir(pdb_id)
    if not sys_dir:
        print(f"错误: 找不到体系目录 {pdb_id}")
        return None
    
    # 1. 读取 FASTA 序列
    fasta_path = get_fasta_path(sys_dir, pdb_id)
    if not fasta_path:
        print(f"错误: 找不到 {fasta_path}")
        return None
    sequence = read_fasta_sequence(fasta_path)
    print(f"  序列长度: {len(sequence)} aa")
    
    # 2. 读取模板 PDB（prepare_for_swiss）
    template_path = get_template_path(sys_dir, pdb_id)
    if not template_path:
        print(f"错误: 找不到模板文件 {pdb_id}_prepare_for_swiss.pdb")
        print(f"  请先在 PyMOL 中完成对齐和 copy_to，保存为 {pdb_id}_prepare_for_swiss.pdb")
        return None
    template_coords = read_template_pdb(template_path)
    print(f"  模板文件: {template_path} ({len(template_coords)} bytes)")
    
    # 3. 提交到 API
    print(f"  正在提交到 SWISS-MODEL...")
    response = http_request(
        f"{BASE_URL}/user_template",
        method="POST",
        headers={"Authorization": f"Token {token}"},
        json_body={
            "target_sequences": sequence,
            "template_coordinates": template_coords,
            "project_title": f"{pdb_id} CDK2 missing segment repair"
        }
    )
    
    if response.ok:
        project_id = response.json().get("project_id")
        print(f"  ✅ 提交成功! project_id = {project_id}")
        print(f"     状态码: {response.status_code}")
        if response.status_code == 202:
            print(f"     (已接受，等待处理)")
        elif response.status_code == 200:
            print(f"     (之前已提交过相同任务，直接使用结果)")
        return project_id
    else:
        print(f"  ❌ 提交失败! 状态码: {response.status_code}")
        print(f"     响应: {response.text[:500]}")
        return None


def check_status(project_id, token):
    """查询一个 project 的状态"""
    response = http_request(
        f"{BASE_URL}/project/{project_id}/models/summary/",
        method="GET",
        headers={"Authorization": f"Token {token}"}
    )
    
    if response.ok:
        data = response.json()
        status = data.get("status", "UNKNOWN")
        print(f"  状态: {status}")
        
        if status == "COMPLETED":
            models = data.get("models", [])
            print(f"  模型数量: {len(models)}")
            for i, model in enumerate(models):
                print(f"    模型 {i+1}:")
                print(f"      PDB 下载: {model.get('coordinates_url', 'N/A')}")
                print(f"      ModelCIF: {model.get('modelcif_url', 'N/A')}")
        
        return data
    else:
        print(f"  查询失败: {response.status_code}")
        return None


def download_model(project_id, pdb_id, token):
    """下载完成的模型到对应体系目录"""
    data = check_status(project_id, token)
    if not data or data.get("status") != "COMPLETED":
        print("  模型尚未完成，无法下载")
        return False
    
    models = data.get("models", [])
    if not models:
        print("  没有可下载的模型")
        return False
    
    # 下载第一个模型的 PDB 坐标
    coords_url = models[0].get("coordinates_url")
    if not coords_url:
        print("  缺少 coordinates_url")
        return False
    
    response = http_request(coords_url, method="GET")
    if response.ok:
        system_dir = get_system_dir(pdb_id)
        if not system_dir:
            print(f"  找不到体系目录 {pdb_id}")
            return False

        try:
            pdb_text = decode_pdb_payload(response)
        except Exception as exc:
            print(f"  下载内容解码失败: {exc}")
            return False

        if "ATOM" not in pdb_text and "HEADER" not in pdb_text and "TITLE" not in pdb_text:
            print("  下载内容看起来不像 PDB 文本，已停止保存")
            return False

        output_dir = get_output_dir(system_dir, pdb_id)
        output_path = os.path.join(output_dir, f"{pdb_id}_swissmodel_output.pdb")
        with open(output_path, "w") as f:
            f.write(pdb_text)
        print(f"  ✅ 模型已保存到: {output_path}")
        return True
    else:
        print(f"  下载失败: {response.status_code}")
        return False


def wait_and_download(project_id, pdb_id, token, poll_interval=15, max_wait=600):
    """等待建模完成并自动下载"""
    print(f"  等待建模完成 (最多 {max_wait}s, 每 {poll_interval}s 查询一次)...")
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        
        response = http_request(
            f"{BASE_URL}/project/{project_id}/models/summary/",
            method="GET",
            headers={"Authorization": f"Token {token}"}
        )
        
        if response.ok:
            status = response.json().get("status", "UNKNOWN")
            print(f"  [{elapsed}s] 状态: {status}")
            
            if status == "COMPLETED":
                return download_model(project_id, pdb_id, token)
            elif status == "FAILED":
                print(f"  ❌ 建模失败!")
                print(f"     详情: {json.dumps(response.json(), indent=2)[:500]}")
                return False
    
    print(f"  ⚠️ 等待超时 ({max_wait}s)")
    return False


def save_job(pdb_id, project_id):
    """保存 project_id 到记录文件"""
    jobs = {}
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE) as f:
            jobs = json.load(f)
    
    jobs[pdb_id] = {
        "project_id": project_id,
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


def bulk_download(token):
    """按官方 API 打包下载所有通过 API 创建的项目结果"""
    response = http_request(
        f"{BASE_URL}/projects/download/",
        method="POST",
        headers={"Authorization": f"Token {token}"}
    )
    if not response.ok:
        print(f"打包请求失败: {response.status_code}")
        print(response.text[:500])
        return False

    download_id = response.json().get("download_id")
    if not download_id:
        print("缺少 download_id")
        return False

    print(f"  打包任务已创建: {download_id}")
    while True:
        time.sleep(5)
        poll = http_request(
            f"{BASE_URL}/projects/download/{download_id}/",
            method="GET",
            headers={"Authorization": f"Token {token}"}
        )
        if not poll.ok:
            print(f"  查询打包任务失败: {poll.status_code}")
            return False
        data = poll.json()
        status = data.get("status", "UNKNOWN")
        print(f"  打包状态: {status}")
        if status in {"COMPLETED", "FAILED"}:
            break

    if status != "COMPLETED":
        print("  打包失败")
        return False

    download_url = data.get("download_url")
    if not download_url:
        print("  缺少 download_url")
        return False

    archive = http_request(download_url, method="GET")
    if not archive.ok:
        print(f"  下载打包结果失败: {archive.status_code}")
        return False

    output_path = os.path.join(PROJECT_ROOT, "swiss_model_bulk_download.zip")
    with open(output_path, "wb") as f:
        f.write(archive.content)
    print(f"  ✅ 已保存到: {output_path}")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command == "validate":
        if len(sys.argv) < 3:
            print("用法: python3 swiss_model_api.py validate <PDB_ID>")
            sys.exit(1)
        pdb_id = sys.argv[2].upper()
        ok = validate_system_inputs(pdb_id)
        sys.exit(0 if ok else 1)

    token = get_token()
    
    if command == "submit":
        # 提交单个体系
        if len(sys.argv) < 3:
            print("用法: python3 swiss_model_api.py submit <PDB_ID>")
            sys.exit(1)
        
        pdb_id = sys.argv[2].upper()
        print(f"\n=== 提交 {pdb_id} ===")
        project_id = submit_user_template(pdb_id, token)
        
        if project_id:
            save_job(pdb_id, project_id)
            
            # 询问是否等待
            if "--wait" in sys.argv:
                wait_and_download(project_id, pdb_id, token)
    
    elif command == "submit_all":
        # 批量提交所有有模板文件的体系
        print("\n=== 批量提交所有准备好的体系 ===")
        for pdb_id in sorted(LIGAND_MAP.keys()):
            sys_dir = get_system_dir(pdb_id)
            template_path = get_template_path(sys_dir, pdb_id) if sys_dir else None
            if template_path:
                print(f"\n--- {pdb_id} ---")
                project_id = submit_user_template(pdb_id, token)
                if project_id:
                    save_job(pdb_id, project_id)
                time.sleep(2)  # 避免 rate limit
            else:
                print(f"\n--- {pdb_id}: 跳过（模板文件不存在）---")
    
    elif command == "status":
        # 查询单个 project 或所有已提交的
        if len(sys.argv) >= 3:
            project_id = sys.argv[2]
            print(f"\n=== 查询 project {project_id} ===")
            check_status(project_id, token)
        else:
            # 查询所有已记录的 jobs
            if not os.path.exists(JOBS_FILE):
                print("没有已提交的任务记录")
                sys.exit(0)
            with open(JOBS_FILE) as f:
                jobs = json.load(f)
            for pdb_id, info in jobs.items():
                print(f"\n=== {pdb_id} (project: {info['project_id']}) ===")
                check_status(info["project_id"], token)
    
    elif command == "download":
        # 下载指定 project 的结果
        if len(sys.argv) >= 4:
            project_id = sys.argv[2]
            pdb_id = sys.argv[3].upper()
            print(f"\n=== 下载 {pdb_id} ===")
            download_model(project_id, pdb_id, token)
        elif len(sys.argv) >= 3 and sys.argv[2] == "all":
            # 下载所有已完成的
            if not os.path.exists(JOBS_FILE):
                print("没有已提交的任务记录")
                sys.exit(0)
            with open(JOBS_FILE) as f:
                jobs = json.load(f)
            for pdb_id, info in jobs.items():
                print(f"\n=== 下载 {pdb_id} ===")
                download_model(info["project_id"], pdb_id, token)
        else:
            print("用法:")
            print("  python3 swiss_model_api.py download <project_id> <PDB_ID>")
            print("  python3 swiss_model_api.py download all")
    
    elif command == "bulk_download":
        print("\n=== 打包下载 API 创建的全部项目 ===")
        bulk_download(token)
    
    else:
        print(f"未知命令: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
