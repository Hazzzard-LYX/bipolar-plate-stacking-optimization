# 实验34：精确DP堆叠序列复现实验28

本实验完全复用实验28的15片真实双极板、全积分S4壳、刚体端板、0.448 MPa恒压、小滑移摩擦和少约束设置，仅将min/max堆叠顺序替换为Held-Karp状态压缩动态规划求得的精确解。

## 堆叠顺序

- 精确min：2-14-3-5-4-12-11-8-13-1-10-7-9-15-6
- 自然顺序：1-2-3-4-5-6-7-8-9-10-11-12-13-14-15
- 精确max：11-1-2-10-14-9-13-7-5-6-3-15-8-4-12

精确算法及距离矩阵参数见上级归档目录中的`精确算法_min_max_堆叠序列参数说明(1).md`。

## 运行流程

```powershell
powershell -ExecutionPolicy Bypass -File .\00_prepare_all.ps1
powershell -ExecutionPolicy Bypass -File .\02_run_abaqus_jobs.ps1
powershell -ExecutionPolicy Bypass -File .\07_postprocess.ps1
```

后处理同时生成实验34三排序结果，以及实验28启发式序列与实验34精确序列的直接对比。
