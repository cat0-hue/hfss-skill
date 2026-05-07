"""
批量运行所有天线仿真
在安装了 ANSYS AEDT 的机器上运行:
    python batch_simulate.py

前置要求: pip install pyaedt
"""

from ansys.aedt.core import Hfss
import os, shutil, tempfile, uuid

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
AEDT_VERSION = "2023.1"
AEDT_FILES = [f for f in os.listdir(SIM_DIR) if f.endswith(".aedt")]


def _prepare_project(src_path):
    """如果路径含中文，复制到临时目录"""
    try:
        src_path.encode("ascii")
        return src_path, None
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    tmp_dir = os.path.join(tempfile.gettempdir(), "aedt_sim_" + uuid.uuid4().hex[:8])
    os.makedirs(tmp_dir, exist_ok=True)
    dst_path = os.path.join(tmp_dir, os.path.basename(src_path))
    shutil.copy2(src_path, dst_path)
    src_aedb = src_path.replace(".aedt", ".aedb")
    dst_aedb = dst_path.replace(".aedt", ".aedb")
    if os.path.isdir(src_aedb):
        shutil.copytree(src_aedb, dst_aedb, dirs_exist_ok=True)
    return dst_path, tmp_dir


if not AEDT_FILES:
    print("未找到 .aedt 文件")
    exit(1)

for aedt_file in AEDT_FILES:
    filepath = os.path.join(SIM_DIR, aedt_file)
    print(f"\n{'='*60}")
    print(f"开始仿真: {aedt_file}")
    print(f"{'='*60}")

    project_file, tmp_dir = _prepare_project(filepath)

    try:
        with Hfss(
            project=project_file,
            version=AEDT_VERSION,
            non_graphical=True,
            close_on_exit=True,
        ) as hfss:
            print(f"  设计: {hfss.design_name}")
            for setup in hfss.setups:
                print(f"  运行求解: {setup.name}")
            hfss.analyze(cores=4)
            hfss.save_project()
            print(f"  OK {aedt_file} 完成")
    except Exception as e:
        print(f"  FAIL {aedt_file} 失败: {e}")
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n全部仿真完成！")
