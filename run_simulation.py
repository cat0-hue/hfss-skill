"""
PyAEDT 自动化仿真脚本
使用方法: 在安装了 ANSYS AEDT 的机器上运行:
    python run_simulation.py

前置要求: pip install pyaedt
"""

from ansys.aedt.core import Hfss
import os, shutil, tempfile, uuid

# ===== 配置 =====
PROJECT_FILE = os.path.join(os.path.dirname(__file__), "半波偶极子天线.aedt")
AEDT_VERSION = "2023.1"  # ANSYS EM 2023 R1
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")
USE_TEMP_PATH = True  # True: 复制到临时目录避免中文路径问题


def _prepare_project(src_path):
    """如果路径含中文，复制到临时目录"""
    if not USE_TEMP_PATH:
        return src_path, None
    try:
        src_path.encode("ascii")
        return src_path, None  # 已经是纯 ASCII 路径
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    tmp_dir = os.path.join(tempfile.gettempdir(), "aedt_sim_" + uuid.uuid4().hex[:8])
    os.makedirs(tmp_dir, exist_ok=True)
    dst_path = os.path.join(tmp_dir, "project.aedt")
    shutil.copy2(src_path, dst_path)

    # 同时复制 .aedb 文件夹（如果有）
    src_aedb = src_path.replace(".aedt", ".aedb")
    dst_aedb = dst_path.replace(".aedt", ".aedb")
    if os.path.isdir(src_aedb):
        shutil.copytree(src_aedb, dst_aedb, dirs_exist_ok=True)

    print(f"源文件: {src_path}")
    print(f"临时文件: {dst_path}")
    return dst_path, tmp_dir


def run_simulation():
    """打开项目并运行仿真"""
    project_file, tmp_dir = _prepare_project(PROJECT_FILE)

    with Hfss(
        project=project_file,
        version=AEDT_VERSION,
        non_graphical=True,
        close_on_exit=True,
    ) as hfss:
        print(f"项目: {hfss.project_name}")
        print(f"设计: {hfss.design_name}")

        # 查看所有求解设置
        for setup in hfss.setups:
            print(f"  求解设置: {setup.name}")
            print(f"    频率: {setup.props.get('Frequency', 'N/A')}")
            print(f"    最大迭代: {setup.props.get('MaximumPasses', 'N/A')}")
            print(f"    收敛误差: {setup.props.get('MaxDeltaS', 'N/A')}")

        # 确保扫频保存远场数据
        for setup in hfss.setups:
            if hasattr(setup, 'props') and 'Sweeps' in setup.props:
                sweeps = setup.props['Sweeps']
                if isinstance(sweeps, dict) and 'Sweep' in sweeps:
                    sweep = sweeps['Sweep']
                    if isinstance(sweep, dict):
                        sweep['SaveRadFields'] = True

        # 添加远场球面（Infinite Sphere）确保方向图可查看
        try:
            hfss.insert_infinite_sphere(
                name="3D",
                phi_start=0, phi_stop=360, phi_step=2,
                theta_start=0, theta_stop=180, theta_step=2,
            )
            print("已添加远场球面 3D")
        except Exception as e:
            print(f"远场球面已存在或添加失败: {e}")

        # 运行仿真
        print("正在运行仿真（这会花一些时间）...")
        success = hfss.analyze(cores=4)
        if not success:
            print("仿真失败！")
            return
        print("仿真完成！")

        # 导出结果
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ===== 导出 S11 (回波损耗) CSV =====
        try:
            sweep_name = "Setup1 : Sweep"
            print(f"导出 S11 数据，扫频: {sweep_name}")
            # 导出 dB 幅度: dB(S(1,1)) 才是真正的回波损耗
            soln = hfss.post.get_solution_data(
                expressions=["dB(S(1,1))"],
                setup_sweep_name=sweep_name,
            )
            if not soln:
                sweep_name = "Setup1 : LastAdaptive"
                print(f"全扫频不可用，回退到: {sweep_name}")
                soln = hfss.post.get_solution_data(
                    expressions=["dB(S(1,1))"],
                    setup_sweep_name=sweep_name,
                )
            if soln:
                soln.export_data_to_csv(os.path.join(OUTPUT_DIR, "S11_dB.csv"))
                print("S11_dB.csv 已导出 (dB(S(1,1)))")
        except Exception as e:
            print(f"S11 导出跳过: {e}")

        # ===== 导出方向图 (远场) CSV =====
        try:
            center_freq = hfss.setups[0].props["Frequency"]
            print(f"导出方向图，频率: {center_freq}")

            # 方法1: 通过创建远场报告导出
            report = hfss.post.create_report(
                expressions="GainTotal",
                setup_sweep_name="Setup1 : LastAdaptive",
                domain="Sweep",
                primary_sweep_variable="Theta",
                report_category="Far Fields",
            )
            if report:
                soln = report.get_solution_data()
                if soln:
                    soln.export_data_to_csv(os.path.join(OUTPUT_DIR, "farfield.csv"))
                    print("farfield.csv 已导出")

            # 方法2: 直接导出所有可用报告量
            quantities = hfss.post.available_report_quantities()
            ff_quantities = [q for q in quantities if "Gain" in q or "Directivity" in q or "Radiation" in q]
            if ff_quantities:
                print(f"可用远场量: {ff_quantities[:5]}")
        except Exception as e:
            print(f"方向图导出跳过: {e}")

        # ===== 导出 Touchstone S 参数 =====
        try:
            hfss.export_results(
                export_folder=OUTPUT_DIR,
                matrix_type="S",
                touchstone_format="DbPhase",
            )
            print("Touchstone S 参数已导出")
        except Exception as e:
            print(f"Touchstone 导出跳过: {e}")

        hfss.save_project()
        print(f"\n结果已保存至: {OUTPUT_DIR}")

    # 清理临时文件
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def modify_and_run():
    """修改参数后运行仿真（示例）"""
    project_file, tmp_dir = _prepare_project(PROJECT_FILE)

    with Hfss(
        project=project_file,
        version=AEDT_VERSION,
        non_graphical=True,
        close_on_exit=True,
    ) as hfss:
        # 示例: 修改设计变量
        # hfss.variable_manager.set_variable("length", expression="75mm")
        # hfss.variable_manager.set_variable("width", expression="10mm")

        # 修改求解设置
        setup = hfss.setups["Setup1"]
        setup.props["MaximumPasses"] = 15
        setup.update()

        # 运行
        hfss.analyze(cores=4)
        hfss.save_project()

    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_simulation()
