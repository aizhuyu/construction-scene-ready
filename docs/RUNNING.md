# 本地运行指南（RUNNING）

本仓库是论文《ConstructionSceneReady》的全部实验代码与数据管线。
论文图表和 CSV 全部由注册脚本生成（`scripts/`），不含手工填入的数字。

## 1. CPU 实验（检测/修复/消融/资源/图生成）

```bash
python3 -m venv .venv && .venv/bin/pip install \
  jsonschema numpy pandas pydantic networkx trimesh \
  ifcopenshell==0.8.5 usd-core==26.8 matplotlib pytest
```

```bash
make test                                # 单元测试
make local-pipeline                      # 完整流水线(需 ifcopenshell+usd-core)
# 冻结分区清单已入库: data/partition-manifest.json
PYTHONPATH=src .venv/bin/python scripts/run_detection_repair.py      # B0/B1/A1/A2/A4
PYTHONPATH=src .venv/bin/python scripts/analyze_detection_repair.py  # bootstrap CI + McNemar
PYTHONPATH=src .venv/bin/python scripts/run_resource_efficiency.py   # A3 资源
PYTHONPATH=src .venv/bin/python scripts/run_scale_resource.py        # 规模扫描
PYTHONPATH=src .venv/bin/python scripts/run_external_ifc.py          # 真实IFC(buildingSMART样例已入库 data/external/)
PYTHONPATH=src .venv/bin/python scripts/make_figures.py              # fig7/fig8
PYTHONPATH=src .venv/bin/python scripts/make_diagram_figures_a.py    # fig1-3
PYTHONPATH=src .venv/bin/python scripts/make_diagram_figures_b.py    # fig4-6
PYTHONPATH=src .venv/bin/python scripts/make_case_study_figure.py    # fig9
```

## 2. LLM 修复实验（B2/B3/A5，可选）

需要 GPU（实验用 RTX 4090 D 24GB）：

```bash
conda create -n llm python=3.11 && conda activate llm
pip install vllm==0.6.6 "transformers==4.46.3" openai   # transformers 5.x 与 vllm 0.6.6 不兼容
HF_ENDPOINT=https://hf-mirror.com hf download Qwen/Qwen2.5-Coder-14B-Instruct-AWQ \
    --local-dir ~/llm_models/qwen25-coder-14b-instruct-awq
python -m vllm.entrypoints.openai.api_server \
    --model ~/llm_models/qwen25-coder-14b-instruct-awq \
    --served-model-name csr-qwen25-coder-14b-awq --port 8399 \
    --max-model-len 8192 --gpu-memory-utilization 0.85 &
# 服务就绪后(约2分钟):
PYTHONPATH=src .venv/bin/python scripts/run_llm_repair.py            # 全量 1050 episodes(断点续跑)
PYTHONPATH=src .venv/bin/python scripts/analyze_llm_repair.py        # 方法对比统计
```

## 3. 人形机器人任务数据（task_outcomes.csv 的来源）

机器人侧代码与策略在配套仓库
[g1-steel-assembly](https://github.com/aizhuyu/g1-steel-assembly)（见该库
`docs/RUNNING.md`）：Isaac Sim 4.2 + Isaac Lab + 已训练插入策略 checkpoint。
`scripts/run_readiness_task_link.py` 读取其逐回合 JSONL 输出。

## 4. 论文编译

仓库不含 LaTeX 发行版；安装 tectonic（`conda install -c conda-forge tectonic`）后：

```bash
cd paper && tectonic manuscript.tex
```
