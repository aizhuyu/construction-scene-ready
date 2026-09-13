# ConstructionSimReady-H 新颖性审计

审计日期：2026-07-27  
目标期刊：*Automation in Construction*  
审计范围：IFC/BIM—机器人互操作、IFC—USD、物理就绪资产、机器人数字孪生、建造人形仿真、agentic scene generation、验证与修复。

## 当前证据状态

- `paper/references.bib`：61 条文献记录。
- 当前编译正文实际引用：60 条。
- DOI 记录：46 条，均经 Crossref 标题和年份核对。
- 无 DOI 记录：15 条，主要为官方标准、软件文档、会议论文集页面和 arXiv 预印本。
- `docs/literature-matrix.csv`：55 项既有研究/技术来源，加 1 项本研究占位。
- LaTeX：AIC/Elsevier `elsarticle` 模板可本地完整编译，无未定义引用。

## 会直接限制论文首创表述的近邻工作

### IFC/BIM 到机器人仿真

Kim et al.、Wong Chong et al.、Zhu et al. 和 Oyediran et al. 已经分别建立 BIM/IFC 到 SDF、ROS/Gazebo、木框架装配和 4D BIM 动作级仿真的路线。因此，本文不能声称首次把 IFC/BIM 转换为机器人仿真场景，也不能把格式转换本身作为核心贡献。

### 施工设备 CAD 到物理 USD

Xu et al. (2024) 已经自动生成施工设备的关节、驱动、碰撞和材料等 USD 物理属性，并使用 LLM 从说明书提取缺失参数。因此，本文不能声称首次自动生成施工机器人物理模型、首次 CAD-to-USD 或首次用 LLM 补全仿真参数。

### Specification-driven IFC-to-USD

Ren et al. (2025) 已经把信息交付要求作为 scene contract，完成 IFC 到 OpenUSD 的可配置选择、映射和语义保存。因此，本文不能声称首次 IFC-to-USD、首次 specification-driven scene contract，或首次在 USD 中保存 IFC 标识、层级、几何、材料和属性。

### BIM 与人形机器人建造仿真

Ye et al. (2026) 已经将 BIM 几何和语义信息转换为 MuJoCo 场景，以 Unitree G1 展示建造任务分解与模拟。因此，本文不能声称首次 BIM-to-humanoid construction simulation、首次 Unitree G1 建造场景或首次用数字孪生研究建造人形机器人。

### 通用 simulation-ready 场景生成

SimRecon、EmbodiedGen V2 和 Agentic Real2Sim 已经分别覆盖视频到可组合仿真场景、跨仿真器任务世界生成，以及带物理参数和对象状态的 agentic real-to-sim。因此，本文不能声称首次 agentic simulation-ready world generation、首次 scene-level physical plausibility 或首次由 Agent 建立可运行物理世界。

### 通用 SimReady 规则

NVIDIA 已经定义 asset-level Capability、Feature、Profile 和机器可执行规则。本文不能声称首次 SimReady Profile 或首次 USD 验证器。官方 FAQ 同时明确指出，当前规范和验证仍以资产/Feature 为单位，尚未定义成熟的 scene-level specifications and validators。这个公开边界是本文场景级研究缺口的重要依据。

## 当前可以守住的组合创新

论文的核心不再是某个格式、机器人型号或 Agent，而是以下机制的联合实现和可检验关系：

1. **建造任务场景就绪契约**：在资产验证之上检查 IFC 身份闭合、跨资产引用、坐标系、工作区激活、装配接口、临时施工状态、机器人能力和任务成功判据。
2. **任务激活的多尺度编译**：把同一 IFC 工程对象组织为全局导航、作业区和交互层；由任务选择有效 payload，而不是把整栋建筑统一细化。
3. **物理参数来源与不确定性**：关键参数同时保存数值、来源、置信度、适用任务和是否允许自动修改。
4. **可控故障注入与 ground truth**：对语义、空间、物理、接口、状态和任务缺陷建立可复现实验，而不是展示一个成功案例。
5. **验证器约束的 Agent 修复**：Agent 只能调用白名单工具；确定性验证器独立裁决；高风险或来源不足的修改必须升级给人。
6. **就绪质量到任务结果的证据链**：检验 scene-readiness score、关键规则失败与人形运动规划/装配任务成功之间的统计关系。

这是一项**组合创新**。单独的 IFC-to-USD、G1、OpenUSD、Agent、验证器或故障注入都不是新颖性来源；论文强度来自统一问题定义、可执行实现、严格基线、消融、统计检验和公开基准。

## 稳妥的论文表述

建议在摘要、引言和结论中使用：

> The work addresses the unresolved transition from individually valid
> digital assets to an auditable, composed, task-specific construction world.

或：

> To the best of the authors' knowledge, prior work has not jointly evaluated
> construction-task scene rules, task-activated multi-scale USD composition,
> physical-property provenance, deterministic fault detection,
> validator-grounded repair, and downstream humanoid assembly outcomes.

第二种表述必须在投稿前再次更新检索，不使用无边界的 “first”。

## 禁止使用的表述

- first IFC-to-robot-simulation framework
- first IFC-to-USD pipeline
- first BIM-to-SimReady method
- first BIM-to-robot-ready digital twin
- first BIM-based humanoid construction simulation
- first automated construction-equipment physical model
- first SimReady validator
- first agent-generated simulation scene
- first use of Unitree G1 in construction simulation
- Agent-generated parameters are physically correct

## 下一次新颖性复核门

在完成 CPU 最小闭环、开始 RTX 批量实验前再次检索：

- 2026 年 *Automation in Construction* online-first；
- 2026 年 ISARC 全部 BIM/robot/digital-twin/humanoid 论文；
- arXiv `cs.RO`, `cs.CV`, `cs.AI` 中 `SimReady`, `scene generation`, `real2sim`, `IFC`, `construction humanoid`；
- NVIDIA SimReady Foundation 的 scene-level 规范更新。

如果通用 scene-level validator 在此期间发布，论文仍应依靠建造任务规则、故障基准、来源约束和任务结果关联保持差异，而不是依赖“通用工具尚未提供该功能”。

## 关键新增来源

- Ren, G., Huang, C., Su, T. (2025). From Building Deliverables to Open Scene Description: A Pipeline for Lifecycle 3D Interoperability. *Buildings*, 15(24), 4503. https://doi.org/10.3390/buildings15244503
- Ye, X., Liu, L., König, M. (2026). Digital Twin Framework for Humanoid Robotics in Construction: A Conceptual Approach for Scene and Task Simulation. *Proceedings of the 43rd ISARC*, 438–445. https://doi.org/10.22260/ISARC2026/0057
- Wang, X. et al. (2026). EmbodiedGen V2: An Agentic, Simulation-Ready 3D World Engine for Embodied AI. https://arxiv.org/abs/2607.07459
- Chen, G. et al. (2026). Agentic Real2Sim: Physics-Based World Modeling with Vision-Language Agents. https://arxiv.org/abs/2607.19190
- Xia, C. et al. (2026). SimRecon: SimReady Compositional Scene Reconstruction from Real Videos. https://arxiv.org/abs/2603.02133
- NVIDIA. SimReady FAQ. https://docs.omniverse.nvidia.com/simready/latest/simready-faq.html
