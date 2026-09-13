#!/usr/bin/env bash
set -Eeuo pipefail

# H4 完整实验: 训练完成后一键运行
# 用法: bash scripts/run_h4_experiment.sh

source ~/anaconda3/etc/profile.d/conda.sh
conda activate isaaclab
cd ~/IsaacLab

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export LC_ALL=en_US.UTF-8

PROJECT=~/research/construction-scene-ready
H4_OUT=$PROJECT/generated/h4
mkdir -p "$H4_OUT"

# === 1. 找最新的训练 checkpoint ===
echo "=== 1. 查找训练 checkpoint ==="
LATEST_RUN=$(ls -dt ~/IsaacLab/logs/rsl_rl/g1_steel_assembly/2026-* 2>/dev/null | head -1)
echo "训练run: $LATEST_RUN"

# 找最大轮数的 model
CHECKPOINT=$(ls "$LATEST_RUN"/model_*.pt 2>/dev/null | sed 's/.*model_//;s/\.pt//' | sort -n | tail -1)
CHECKPOINT_PATH="$LATEST_RUN/model_${CHECKPOINT}.pt"
echo "使用checkpoint: $CHECKPOINT_PATH (轮数: $CHECKPOINT)"

if [ ! -f "$CHECKPOINT_PATH" ]; then
    echo "✗ 未找到checkpoint! 请确认训练已完成。"
    exit 1
fi

# === 2. 运行 H4 评估 ===
echo ""
echo "=== 2. 运行 H4 评估 ==="
echo "开始时间: $(date)"

./isaaclab.sh -p "$PROJECT/scripts/h4_evaluate.py" \
    --checkpoint "$CHECKPOINT_PATH" \
    --num-envs 64 \
    --steps 500 \
    --repeats 5 \
    --output "$H4_OUT/results.json" \
    --headless

echo ""
echo "评估完成: $(date)"

# === 3. 运行 H4 分析 ===
echo ""
echo "=== 3. 运行 H4 分析 ==="
python3 "$PROJECT/scripts/h4_analyze.py" \
    --input "$H4_OUT/results.json" \
    --output-dir "$H4_OUT/"

echo ""
echo "=== 全部完成! ==="
echo "结果目录: $H4_OUT/"
echo "  - results.json     (原始rollout数据)"
echo "  - h4_analysis.json (相关性分析)"
echo "  - h4_correlation.png (图表)"
