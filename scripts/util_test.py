"""
PyAEDT + ANSYS AEDT 连接测试
只打开项目查看信息，不运行仿真
"""

from ansys.aedt.core import Hfss
import os, sys, traceback

SIM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AEDT_VERSION = "2023.1"
PROJECT_FILE = os.path.join(SIM_DIR, "projects", "dipole_halfwave.aedt")

print(f"Python:   {sys.version}")
print(f"PyAEDT:   0.26.3")
print(f"ANSYS:    {AEDT_VERSION}")
print(f"项目文件: {PROJECT_FILE}")
print(f"文件存在: {os.path.exists(PROJECT_FILE)}")
print()

try:
    os.chdir(SIM_DIR)
    with Hfss(
        project=PROJECT_FILE,
        version=AEDT_VERSION,
        non_graphical=True,
        close_on_exit=True,
    ) as hfss:
        print(f"项目: {hfss.project_name}")
        print(f"设计: {hfss.design_name}")
        print(f"设计列表: {hfss.design_list}")

        print(f"\n求解设置 ({len(hfss.setups)} 个):")
        for setup in hfss.setups:
            print(f"  - {setup.name}:")
            for k, v in setup.props.items():
                print(f"      {k}: {v}")

        print(f"\n设计变量:")
        for k, v in hfss.variable_manager.design_variables.items():
            print(f"  {k} = {v}")

        print(f"\n连接成功！AEDT 已就绪。")

except Exception as e:
    print(f"\n连接失败: {e}")
    traceback.print_exc()
