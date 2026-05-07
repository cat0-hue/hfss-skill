# HFSS 自动化仿真 Skill 规范 V2.0

**角色**: 精通 PyAEDT 和电磁场理论的专家级仿真工程师。

---

## 目录
1. [参数提取与变量化](#1-参数提取与变量化)
2. [环境初始化](#2-环境初始化)
3. [稳健建模](#3-稳健建模)
4. [求解与扫频配置](#4-求解与扫频配置)
5. [执行求解](#5-执行求解)
6. [结果导出与可视化](#6-结果导出与可视化)
7. [后处理闭环](#7-后处理闭环)
8. [异常拦截与恢复](#8-异常拦截与恢复)
9. [参数扫描与优化](#9-参数扫描与优化)
10. [检查清单与输出物](#10-检查清单与输出物)

---

## 1. 参数提取与变量化

### 1.1 提取来源
- 论文中的几何尺寸表格
- 截图中的标注
- 用户描述
- 已有 .aedt 文件（`app.variable_manager.design_variable_names` 读取）

### 1.2 变量定义规则
所有数值通过 `app.variable_manager.set_variable()` 定义，禁止硬编码。

```python
# 正确
app["L_patch"] = "50mm"
app["W_patch"] = "40mm"
app["h_sub"] = "1.6mm"

# 错误
hfss.modeler.create_box([0,0,0], [50, 40, 1.6], ...)
```

### 1.3 依赖关系
变量间依赖也通过变量管理器定义，方便后续优化中联动。

```python
app["W_ground"] = "L_ground"       # 方形地，与长度相同
app["L_feed"] = "L_patch / 2"      # 馈线位置 = 贴片半长
app["airbox_x"] = "L_ground + 4 * (299.792458 / Freq_GHz / 4)"
app["airbox_y"] = "W_ground + 4 * (299.792458 / Freq_GHz / 4)"
app["airbox_z"] = "h_sub + 4 * (299.792458 / Freq_GHz / 4)"
```

### 1.4 物理约束检查
定义变量后立即验证物理合理性。

| 检查项 | 阈值 | 处理 |
|--------|------|------|
| 贴片尺寸 vs 波长 | `L < λ/10` 不可靠 | `warn()` 但继续 |
| 介质基板厚度 vs 波长 | `h > λ/10` 表面波严重 | `warn()` |
| 空气盒距辐射体 | `< λ/4` 精度不够 | 自动扩大到 `λ/4` |
| 端口尺寸 | 过小/过大影响 S 参数 | 自动修正 |

---

## 2. 环境初始化

### 2.1 连接策略

| 场景 | `new_desktop_session` | `non_graphical` | 适用 |
|------|----------------------|-----------------|------|
| 已有 HFSS 开着 | `False` | `False` | 日常调试 |
| 脚本全自动 | `True` | `True` | 批量/CI |
| 临时调试 | `True` | `False` | 验证建模 |

```python
from ansys.aedt.core import Hfss

app = Hfss(
    specified_version="2023.2",
    non_graphical=False,
    new_desktop_session=False,  # 优先连接已有实例
    close_on_exit=False,
)
```

### 2.2 项目与设计管理
```python
project_name = "antenna_sim"
if project_name in app.project_list():
    app.close_project(project_name)
app.new_project(project_name)

design_name = "HFSSDesign"
if design_name in app.design_list():
    app.delete_design(design_name)
app.insert_design(design_name)
```

### 2.3 中文路径防护
```python
import os, shutil, tempfile, uuid

def ensure_ascii_path(path):
    try:
        path.encode("ascii")
        return path, None
    except UnicodeEncodeError:
        tmp = os.path.join(tempfile.gettempdir(), "aedt_" + uuid.uuid4().hex[:8])
        os.makedirs(tmp, exist_ok=True)
        dst = os.path.join(tmp, os.path.basename(path))
        shutil.copy2(path, dst)
        aedb_src = path.replace(".aedt", ".aedb")
        aedb_dst = dst.replace(".aedt", ".aedb")
        if os.path.isdir(aedb_src):
            shutil.copytree(aedb_src, aedb_dst, dirs_exist_ok=True)
        return dst, tmp
```

---

## 3. 稳健建模

### 3.1 建模顺序
```
1. 基板 (Substrate)     <- 材料属性：er, tan(delta)
2. 接地板 (Ground)      <- Perfect E
3. 辐射贴片 (Patch)     <- Perfect E
4. 馈线/馈电 (Feed)     <- Lumped Port / Wave Port
5. 空气盒 (Airbox)      <- Radiation Boundary
6. 远场球面 (Infinite Sphere) <- 方向图计算前提
```

### 3.2 材料库
优先从 `app.materials` 读取标准材料，找不到再创建：

```python
try:
    sub = app.materials["Rogers RO4350B"]
except KeyError:
    sub = app.materials.add_material("Rogers RO4350B")
    sub.conductivity = 0
    sub.permittivity = 3.66
    sub.loss_tangent = 0.0031
```

### 3.3 端口设置
```python
port = app.modeler.create_lumped_port(
    position=[x1, y1, z1],
    reference=[x1, y1, z1 - h_sub],
    impedance=50,
    name="Port1",
    integration_line_axis="Z",
)
```

| 端口类型 | 使用场景 | 注意事项 |
|---------|---------|---------|
| Lumped Port | 微带/共面波导 | 设积分线方向对齐电场 |
| Wave Port | 波导/同轴 | 需足够长度（>=3*宽度） |
| Gap Source | 偶极子天线 | 定义在导线间隙 |

### 3.4 辐射边界与空气盒
```python
f_min = 2  # GHz
lambda_min = 299.792458 / f_min  # mm
airbox_margin = lambda_min / 4

airbox = app.modeler.create_box(
    position=[x_min - airbox_margin, y_min - airbox_margin, z_min - airbox_margin],
    sizes=[w + 2*airbox_margin, d + 2*airbox_margin, h + 2*airbox_margin],
    name="Airbox",
    material="vacuum",
)
airbox.assign_radiation_boundary()
```

### 3.5 远场球面（关键！）
**必须**关联到求解设置，否则看不到方向图：

```python
# 创建球面
app.insert_infinite_sphere(
    name="3D",
    phi_start=0, phi_stop=360, phi_step=2,
    theta_start=0, theta_stop=180, theta_step=2,
)

# 关联到 Setup（关键步骤）
setup = [s for s in app.setups if s.name == "Setup1"][0]
setup.props["InfiniteSphereSetup"] = "3D"
setup.props["SaveRadFieldsOnly"] = False
if "Sweeps" in setup.props:
    sweep = setup.props["Sweeps"]["Sweep"]
    sweep["SaveRadFields"] = True
setup.update()
```

### 3.6 网格控制（可选但推荐）
```python
patch_surface = app.modeler.get_object_by_name("Patch")
patch_surface.mesh_length = wavelength / 20

app.mesh.initial_mesh_settings["MeshSettings"]["MaxEle"] = 50000
```

---

## 4. 求解与扫频配置

### 4.1 求解设置
```python
setup = app.create_setup("Setup1")
setup.props["Frequency"] = f"{f_center}GHz"       # 求解频率
setup.props["MaximumPasses"] = 20                   # 最大迭代
setup.props["MaxDeltaS"] = 0.02                     # 收敛条件
setup.props["PortsOnly"] = False                    # 必须求解全部
setup.update()
```

### 4.2 扫频设置
```python
sweep = app.create_linear_count_sweep(
    setup="Setup1",
    sweep_name="Sweep",
    frequency_range=[f_min, f_max],
    num_of_freq_points=401,
    save_fields=True,
    save_rad_fields=True,
)
```

---

## 5. 执行求解

```python
success = app.analyze_nominal(cores=4)
if not success:
    raise RuntimeError("仿真求解失败")
```

### 收敛监控
```python
converged = setup.is_converged
passes = setup.passes
max_delta_s = setup.convergence["MaxDeltaS"]
print(f"收敛: {converged}, 迭代: {passes}, 最后 DeltaS: {max_delta_s:.4f}")
```

---

## 6. 结果导出与可视化

### 6.1 导出清单
```
results/
├── s11.csv                  # S11 dB 频率响应
├── farfield_3d.csv          # 3D 方向图（GainTotal）
├── farfield_eplane.csv      # E 面切片 (Phi=0deg)
├── farfield_hplane.csv      # H 面切片 (Phi=90deg)
├── touchstone.s1p           # Touchstone S 参数
└── analysis_summary.txt     # 完整分析摘要
```

> CSV 数据是核心输出物。可视化图表建议用 MATLAB / Matplotlib 从 CSV 生成，不依赖 HFSS 截图。

### 6.2 S11 导出
```python
soln = app.post.get_solution_data(
    expressions=["dB(S(1,1))"],
    setup_sweep_name="Setup1 : Sweep",
)
if soln:
    soln.export_data_to_csv(os.path.join(RESULTS_DIR, "s11.csv"))
```

### 6.3 方向图导出（E/H 面切片 + 3D）
```python
# 3D 远场
report = app.post.create_report(
    expressions="GainTotal",
    setup_sweep_name="Setup1 : LastAdaptive",
    domain="Sweep",
    primary_sweep_variable="Theta",
    secondary_sweep_variable="Phi",
    report_category="Far Fields",
    context="3D",
    plot_type="Radiation Pattern",
)
report.export_data_to_csv(os.path.join(RESULTS_DIR, "farfield_3d.csv"))

# E 面切片 (Phi=0deg)
report_e = app.post.create_report(
    expressions="GainTotal",
    setup_sweep_name="Setup1 : LastAdaptive",
    domain="Sweep",
    primary_sweep_variable="Theta",
    report_category="Far Fields",
    context="3D",
    plot_type="Rectangular Plot",
    variations={"Phi": "0deg"},
)
report_e.export_data_to_csv(os.path.join(RESULTS_DIR, "farfield_eplane.csv"))
```

### 6.4 Touchstone S 参数
```python
app.export_results(
    export_folder=RESULTS_DIR,
    matrix_type="S",
    touchstone_format="DbPhase",
)
```

---

## 7. 后处理闭环

### 7.1 自动分析
仿真完成后自动计算关键指标：

```python
def analyze_s11(freq, s11_dB):
    idx_min = np.argmin(s11_dB)
    f_res = freq[idx_min]
    s11_min = s11_dB[idx_min]

    below = s11_dB <= -10
    bw = (freq[below][-1] - freq[below][0]) if any(below) else 0

    gamma = 10 ** (s11_min / 20)
    vswr = (1 + gamma) / (1 - gamma)

    return f_res, s11_min, bw, vswr

def analyze_gain(gain_dB, theta, phi):
    g_max = np.max(gain_dB)
    idx = np.argmax(gain_dB)
    return g_max, theta[idx], phi[idx]
```

### 7.2 合格判定

| 指标 | 天线类型 | 合格阈值 |
|------|---------|---------|
| S11 谐振点偏差 | 任何 | < 5% 目标频率 |
| S11 最小值 | 任何 | < -10 dB |
| -10dB 带宽 | 窄带 | >= 目标值 |
| 最大增益 | 任何 | >= 目标值 - 0.5dB |
| VSWR | 任何 | < 2.0 |

### 7.3 自动修正回路
```python
def auto_tune(app, target_freq, actual_freq, max_iter=3):
    for i in range(max_iter):
        error = (actual_freq - target_freq) / target_freq
        if abs(error) < 0.05:
            return True
        scale = 1 + error * 0.8
        app["L_patch"] = f"{float(app['L_patch'].rstrip('mm')) * scale:.3f}mm"
        app.analyze_nominal(cores=4)
        actual_freq = find_resonance(app)
    return False
```

---

## 8. 异常拦截与恢复

### 8.1 异常分类与处理

| 异常类型 | 检测方式 | 处理 |
|---------|---------|------|
| **中文路径** | `UnicodeEncodeError` | 复制到 ASCII 临时目录 |
| **项目锁定** | `.lock` 文件存在 / "Project is locked" | 清理锁文件 + `taskkill` |
| **gRPC 连接失败** | 端口无响应 | 重试 + 端口 +1 |
| **COM 接口崩溃** | `COMError` | `taskkill /f /im ansysedt.exe` + 重连 |
| **网格失败** | 求解日志含 "Mesh failed" | 放宽网格限制后重试 |
| **求解不收敛** | `MaxDeltaS > 0.1` 用完所有 passes | 增加 passes 到 30 |
| **setup 不存在** | 索引错误 | 遍历查找名称 |
| **无远场数据** | `InfiniteSphereSetup = -1` | 修正关联 + 确保已求解 |

### 8.2 锁文件清理
```python
def clean_locks(project_path):
    lock_dir = project_path.replace(".aedt", ".aedb")
    if os.path.isdir(lock_dir):
        for f in os.listdir(lock_dir):
            if f.endswith(".lock"):
                os.remove(os.path.join(lock_dir, f))
```

### 8.3 进程重启
```python
def restart_aedt():
    import subprocess
    subprocess.run(["taskkill", "/f", "/im", "ansysedt.exe"],
                   capture_output=True)
    time.sleep(5)
```

### 8.4 装饰器自动重试
```python
def retry_on_error(max_retries=3, delay=5):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        raise
                    print(f"第 {i+1} 次失败: {e}，{delay}s 后重试")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator
```

---

## 9. 参数扫描与优化

### 9.1 单变量参数扫描
```python
results_grid = []
for L in np.linspace(45, 55, 6):
    app["L_patch"] = f"{L}mm"
    app.analyze_nominal(cores=4)
    f_res = analyze_s11(app)[0]
    results_grid.append((L, f_res))
```

### 9.2 多变量扫描
```python
from itertools import product

param_grid = list(product(
    [45, 50, 55],    # L_patch
    [35, 40, 45],    # W_patch
    [1.6, 3.2],      # h_sub
))

for L, W, h in param_grid:
    app["L_patch"] = f"{L}mm"
    app["W_patch"] = f"{W}mm"
    app["h_sub"] = f"{h}mm"
    app.analyze_nominal(cores=4)
```

### 9.3 优化目标函数
```python
def objective(app, target_freq=2.45):
    f_res, s11_min, bw, vswr = analyze_s11(app)
    g_max, _, _ = analyze_gain(app)

    cost = 0
    cost += 100 * abs(f_res - target_freq) / target_freq
    cost += max(0, -10 - s11_min)
    cost += max(0, g_max - 8) * 2 if g_max < 5 else 0
    return cost
```

---

## 10. 检查清单与输出物

### 仿真前检查
- [ ] 所有尺寸已变量化
- [ ] 材料属性已设定（er, tan(delta)）
- [ ] 端口类型正确 + 积分线方向
- [ ] 空气盒 >= lambda/4
- [ ] 远场球面已定义
- [ ] InfiniteSphereSetup 已关联到 Setup
- [ ] 求解频率 = 中心频率
- [ ] 扫频范围覆盖目标带宽的 2~3 倍

### 仿真后检查
- [ ] 求解已收敛（DeltaS < 0.02）
- [ ] S11 谐振点频率偏差 < 5%
- [ ] S11 最小值 < -10 dB
- [ ] 方向图在 HFSS 中可查看
- [ ] 增益值在物理合理范围内
- [ ] CSV 文件已导出

### 最终输出物
```
results/
├── s11.csv
├── farfield_3d.csv
├── farfield_eplane.csv
├── farfield_hplane.csv
├── touchstone.s1p
└── analysis_summary.txt
```

---

*V2.0 -- 2026-05-07*
