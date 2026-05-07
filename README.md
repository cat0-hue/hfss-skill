# HFSS Simulation Skill

基于 PyAEDT 的 ANSYS HFSS 天线仿真自动化框架。

## 目录结构

```
├── scripts/                       # Python 仿真脚本
│   ├── sim_core.py                # 主仿真流程
│   ├── sim_farfield_fix.py        # 远场球面修正
│   ├── sim_batch.py               # 批量仿真
│   ├── util_test.py               # 连接测试
│   └── run.bat                    # Windows 双击启动
├── analysis/
│   └── analyze_results.m          # MATLAB 后处理分析
├── spec/
│   └── HFSS_Simulation_Spec_V2.md # 仿真规范 V2.0
├── projects/                      # HFSS 项目文件 (.aedt)
├── results/                       # 仿真结果
└── .gitignore
```

## 使用

```bash
# 主仿真
python scripts/sim_core.py

# 远场修正仿真
python scripts/sim_farfield_fix.py

# 批量仿真
python scripts/sim_batch.py

# MATLAB 分析
matlab -batch "run('analysis/analyze_results.m')"
```

## 规范版本

- **V2.0** — 完整覆盖参数化建模、求解配置、结果导出、后处理闭环、异常拦截、参数扫描。
