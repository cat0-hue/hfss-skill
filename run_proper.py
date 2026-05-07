"""
修正脚本：设置 InfiniteSphereSetup 确保远场方向图正确计算
用法: python run_proper.py
"""
from ansys.aedt.core import Hfss
import os, shutil, tempfile, uuid

PROJECT_FILE = os.path.join(os.path.dirname(__file__), "半波偶极子天线.aedt")
AEDT_VERSION = "2023.1"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")

def _prepare_project(src_path):
    try:
        src_path.encode("ascii")
        return src_path, None
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    tmp_dir = os.path.join(tempfile.gettempdir(), "aedt_sim_" + uuid.uuid4().hex[:8])
    os.makedirs(tmp_dir, exist_ok=True)
    dst_path = os.path.join(tmp_dir, "project.aedt")
    shutil.copy2(src_path, dst_path)

    src_aedb = src_path.replace(".aedt", ".aedb")
    dst_aedb = dst_path.replace(".aedt", ".aedb")
    if os.path.isdir(src_aedb):
        shutil.copytree(src_aedb, dst_aedb, dirs_exist_ok=True)

    print(f"源文件: {src_path}")
    print(f"临时文件: {dst_path}")
    return dst_path, tmp_dir


def run():
    project_file, tmp_dir = _prepare_project(PROJECT_FILE)

    with Hfss(
        project=project_file,
        version=AEDT_VERSION,
        non_graphical=True,
        close_on_exit=True,
    ) as hfss:
        print(f"项目: {hfss.project_name}")
        print(f"设计: {hfss.design_name}")

        # 查看已有的 Infinite Sphere 定义
        try:
            spheres = hfss.field_setup_names
            print(f"已有的远场球面: {spheres}")
        except Exception as e:
            print(f"获取 field_setup_names 失败: {e}")
            spheres = []

        if "3D" not in spheres:
            hfss.insert_infinite_sphere(
                name="3D",
                phi_start=0, phi_stop=360, phi_step=2,
                theta_start=0, theta_stop=180, theta_step=2,
            )
            print("已创建远场球面 3D")

        # === 关键修正：将 InfiniteSphereSetup 关联到 Setup1 ===
        setup = [s for s in hfss.setups if s.name == "Setup1"][0]
        print(f"修正前 InfiniteSphereSetup = {setup.props.get('InfiniteSphereSetup', 'N/A')}")

        setup.props["InfiniteSphereSetup"] = "3D"
        setup.props["SaveRadFieldsOnly"] = False
        setup.update()
        print(f"修正后 InfiniteSphereSetup = {setup.props.get('InfiniteSphereSetup', 'N/A')}")

        # 确保扫频保存远场数据
        if 'Sweeps' in setup.props:
            sweeps = setup.props['Sweeps']
            if isinstance(sweeps, dict) and 'Sweep' in sweeps:
                sweep = sweeps['Sweep']
                if isinstance(sweep, dict):
                    sweep['SaveRadFields'] = True
                    print("已设置 Sweep SaveRadFields=True")

        # 运行仿真
        print("正在运行仿真...")
        success = hfss.analyze(cores=4)
        if not success:
            print("仿真失败！")
            return
        print("仿真完成！")

        # ===== 导出结果 =====
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # S11
        try:
            soln = hfss.post.get_solution_data(
                expressions=["dB(S(1,1))"],
                setup_sweep_name="Setup1 : Sweep",
            )
            if soln:
                soln.export_data_to_csv(os.path.join(OUTPUT_DIR, "S11_dB.csv"))
                print("S11_dB.csv 已导出")
        except Exception as e:
            print(f"S11 导出跳过: {e}")

        # 方向图 - 使用 context="3D" 参数
        try:
            report = hfss.post.create_report(
                expressions="GainTotal",
                setup_sweep_name="Setup1 : LastAdaptive",
                domain="Sweep",
                primary_sweep_variable="Theta",
                secondary_sweep_variable="Phi",
                report_category="Far Fields",
                context="3D",
                plot_type="Radiation Pattern",
            )
            if report:
                soln = report.get_solution_data()
                if soln:
                    soln.export_data_to_csv(os.path.join(OUTPUT_DIR, "farfield.csv"))
                    print("farfield.csv 已导出")
        except Exception as e:
            print(f"方向图导出跳过: {e}")

        # Touchstone
        try:
            hfss.export_results(
                export_folder=OUTPUT_DIR,
                matrix_type="S",
                touchstone_format="DbPhase",
            )
            print("Touchstone S 参数已导出")
        except Exception as e:
            print(f"Touchstone 导出跳过: {e}")

        # 保存结果到 D 盘（避免中文路径问题）
        d_result = r"D:\dipole_results.aedt"
        try:
            hfss.save_project(d_result)
            print(f"项目已保存至: {d_result}")
        except Exception as e:
            print(f"保存到 D 盘失败: {e}")
            hfss.save_project()
            print(f"项目已保存到原位置")

        print(f"\n结果已保存至: {OUTPUT_DIR}")

    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    run()
