# HFSS Simulation Skill

基于 PyAEDT 的 ANSYS HFSS 天线仿真自动化框架。

## 目录结构

```
├── HFSS_Simulation_Spec_V2.md   # 仿真规范 V2.0
├── run_simulation.py             # 主仿真脚本
├── run_proper.py                 # 修正版（InfiniteSphereSetup 关联）
├── batch_simulate.py             # 批量仿真
├── analyze_results.m             # MATLAB 后处理分析
├── test_connection.py            # PyAEDT 连接测试
└── run_simulation.bat            # Windows 双击启动
```

## 规范版本

- **V2.0** — 当前最新。完整覆盖参数化建模、求解配置、结果导出、后处理闭环、异常拦截、参数扫描。
