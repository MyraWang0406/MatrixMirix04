# 投放实验决策系统 (Decision Support System)

结构可解释、胜率可复用的**结构化创意评测系统（Creative Evaluation System）**。支持 Creative Card、OFAAT 变体、门禁评测与元素级贡献分析。

## 核心原则：评测对象是结构组合，不是视频

**CreativeSet / EvaluationSet 本质是 CreativeCard（结构卡片）的组合。**

| 概念 | 说明 |
|------|------|
| 最小评测单元 | 结构组合（CreativeCard），而非视频文件 |
| 每张卡 | 一组结构变量（hook / sell_point / CTA / 动机桶 / 表达模式 等） |
| 视频 | 渲染结果，不参与结构胜率统计 |

所有新增字段均：可枚举 / 可标签化 / 能用于统计胜率 / 能用于解释「为什么赢 / 为什么输」。

## 结构卡片字段（StrategyCard / CreativeCard）

### 基础字段

| 字段 | 结构语义 |
|------|----------|
| hook_type | 表达模式 + 认知反差（非文案本身，可统计胜率） |
| why_you_bucket | 核心动机桶（可统计、可复用） |
| why_now_trigger | 行为触发器（时机/紧迫感） |

### 扩展字段（向后兼容）

| 字段 | 说明 |
|------|------|
| segment_spec | 投放人群/场景：country, language, os, user_type, context_scene |
| insight_tension | root_gap（核心缺口）、trigger（触发器）、contrast（反差认知） |
| format_pattern | narrative_type（POV/对比/反转）、rhythm、evidence_style |
| proof_points | 证据点列表（如何让人信） |
| handoff_expectation_detail | first_screen_promise（10 秒内必须看到什么）、consistency_check |
| risk_flags | 夸大 / 误导 / 白量风险标签 |

上述扩展字段不参与实验对照，用于：失败解释 / 结构复盘 / 胜率统计 / Prompt 生成。

**实现**：Python + Pydantic（`eval_schemas.py`）。理由：类型校验、JSON 序列化、向后兼容、无额外依赖。

**门禁 ≠ 结论**

- 样本不足 → 不下结论（仅提示补足数据），详见 [docs/STOP_RULES.md](docs/STOP_RULES.md)
- 门禁失败 → 结构暂不成立（需复测或换层）
- 仅当：跨窗稳定 + OS 不冲突 + 指标达线 → 才允许「结构成立」

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app_demo.py
```

### 校验 Mock 数据（可选）

```bash
python scripts/validate_mock_data.py
```

### 冒烟验收（推荐部署前执行）

```bash
python scripts/smoke_check.py
```

验证：模块导入、路径自检、决策 summary / element_scores / variant_suggestions 最小链路。

本地指定端口：`streamlit run app_demo.py --server.port 3100`

## 云部署：Streamlit Community Cloud（推荐）

1. 将仓库推送到 GitHub
2. 打开 [share.streamlit.io](https://share.streamlit.io)，用 GitHub 登录
3. **New app** → 仓库 `MyraWang0406/AIGC-auto-ads`，分支 `main`
4. **Main file path**：`app_demo.py`（必填，根目录下）
5. 点击 **Deploy**

> **说明**：`app_demo.py` 使用模拟数据，无需配置 Secrets。若部署 `app.py`（LLM 生成），需在 Settings → Secrets 中配置 `OPENROUTER_API_KEY`、`OPENROUTER_MODEL`。

### 健康检查

部署后若页面加载慢，可访问：

- `https://你的app.streamlit.app/?page=health` 或 `?health=1`
- 或点击导航栏 **Health** 按钮

用于排查依赖、环境变量等问题。

## 三层评测集模型

| 层级 | 用途 | 说明 |
|------|------|------|
| **StructureEvaluationSet**（离线） | 结构胜率统计 | 只关心结构字段，见 `evalset_sampler.py` |
| **ExplorationEvaluationSet**（小流量） | 探索阶段 | 固定 segment、baseline 对照、早期门禁 |
| **ValidationEvaluationSet**（放量前） | 验证阶段 | 跨时间窗口复测、轻扩人群 |

评测集 = 结构卡片集合（非视频集合）。每张卡 = 一组结构变量；视频是渲染结果。

## 结构卡片完整示例

见 `samples/example_creative_card.json`，包含扩展字段。简化示例：

```json
{
  "card_id": "sc_casual_game_001",
  "vertical": "casual_game",
  "segment": "18-50岁休闲玩家",
  "motivation_bucket": "成就感",
  "why_you_bucket": "更省事",
  "why_you_phrase": "上手快",
  "why_now_trigger": "新手福利",
  "root_cause_gap": "用户想玩但怕上手难，需要降低门槛与爽点前置",
  "proof_points": ["真实对局展示", "3秒一局即开即玩"],
  "handoff_expectation": "首屏 10 秒内出现福利弹窗",
  "insight_tension": { "root_gap": "怕上手难", "trigger": "无聊想解压", "contrast": "以为要肝→实际3秒一局" }
}
```

## 判断标准

系统能回答：**「这次没跑出来，是样本不足？效率问题？质量问题？承接断裂？还是 OS 分歧？下一轮该改哪一层、怎么改（OFAAT 处方）？」**

- 结构不行 → 门禁失败 / 跨 OS 冲突 / 某层倾向拖后腿 → 下一步变体建议指出具体字段
- 样本不够 → 决策结论显示「样本不足」，建议补足后再决策该层

## 诊断层 (Diagnosis)

诊断模块基于 explore/validate 指标、门禁状态、样本量、OS 结果，输出结构化诊断与处方。

### failure_type（枚举）

| 值 | 说明 |
|----|------|
| INCONCLUSIVE | 样本不足，不下结论（禁止输出「结构不行」） |
| EFFICIENCY_FAIL | Explore 效率不行（IPM 低 / CPI 高） |
| QUALITY_FAIL | Validate 质量不行（early_roas 低） |
| HANDOFF_MISMATCH | 承接断裂（IPM 还行但 CPI/ROAS 崩） |
| OS_DIVERGENCE | iOS/Android 结论不一致 |
| MIXED_SIGNALS | 指标打架 / 难归因 |

### primary_signal（触发信号）

| 值 | 说明 |
|----|------|
| SAMPLE_TOO_LOW | 样本或窗口不达门槛 |
| IPM_DROP | IPM 回撤 |
| CPI_SPIKE | CPI 飙升 |
| ROAS_DROP | early_roas 下降 |
| IPM_OK_BUT_CPI_BAD | IPM 不差但 CPI 崩 |
| IPM_OK_BUT_ROAS_BAD | IPM 不差但 ROAS 崩 |
| IOS_PASS_ANDROID_FAIL | iOS 过 Android 不过 |
| ANDROID_PASS_IOS_FAIL | Android 过 iOS 不过 |

### 处方单格式 (recommended_actions)

每条处方包含：
- **action**: RESAMPLE / CHANGE_HOOK / CHANGE_WHY_NOW / CHANGE_CTA / CHANGE_WHY_YOU / ADD_EVIDENCE / FIX_HANDOFF
- **change_field**: hook_type / why_you_bucket / why_now_trigger / cta
- **direction**: 改动方向（从候选池选哪类）
- **experiment_recipe**: OFAAT 说明（一次只改一个字段，固定其余）
- **target_os**: 端内修正时标注 iOS / Android
- **reason**: 触发原因

示例输出见 `samples/diagnosis_example_output.json`。

## Card Library（结构卡片资产化）

**是什么**：可复用的结构卡片资产库，50–100 张起步。每张卡带 version、provenance，支持按 vertical/channel/country/segment 筛选。

- **proof_points** / **handoff_expectation**：StrategyCard 新增字段（向后兼容）
- **provenance**：source_channel（Meta/TikTok/Google）、source_country、source_date、source_ref
- **data/card_library/**：`cards.jsonl`（每行一卡带 version）、`cards_index.json`
- **card_library.py**：`load_cards()` / `save_cards()` / `filter_cards(vertical, country, segment, motivation_bucket, os, channel)` / `bump_version(card_id)`

## EvalSet Sampler（评测集设计）

**如何保证可迁移、抗噪、跨国家/人群/渠道可对比**：

- **分层抽样**：vertical × channel × country × segment × os × motivation_bucket
- **每层至少 1 张**；配额不足则回退到 country=US / segment=new / motivation_bucket=deal_discount
- **每层指定 baseline 卡**用于抗噪对照
- **默认配额**（configs/default_evalset_config.json）：vertical 70% 电商 30% 游戏；channel Meta 45% / TikTok 35% / Google 20%；os Android 60% / iOS 40%；segment new 60% / returning 25% / retargeting 15%
- **评测集 = 结构卡片集合**（非视频集合）；`card.os=all` 时自动支持 iOS/Android 双端

## Knowledge Store（复盘知识库）

**如何让换人不断**：SQLite 沉淀结构胜率与适用场景，新同学可检索历史实验、failure_type 分布、表现最稳结构。

- **表**：cards / experiments / variant_metrics / diagnosis / element_scores / decisions
- **写入**：决策看板每次评测 + 评测集「批量写入知识库」
- **复盘检索页**：按 vertical/channel/country/segment/os/motivation_bucket 筛选；展示 Explore/Validate PASS 率、failure_type 分布 Top3、表现最稳结构 Top10

## 从处方到素材 Brief（D，待实现）

**如何连接素材生产与决策闭环**：Creative Brief 将 diagnosis 的 failure_type/primary_signal、proof_points、handoff_expectation 输入 AIGC，输出 script_beats、visual_evidence_plan、handoff_checklist 等，使决策结论可直接驱动素材生产。

## 数据流

```
评测集（分层抽样+baseline）→ 门禁/诊断 → 下一步处方 → 写入 knowledge_store → 复盘页可检索
                                    ↓
                         [Creative Brief] → AIGC 素材生产
```

## 门禁止损逻辑 (Stop Rules)

详见 [docs/STOP_RULES.md](docs/STOP_RULES.md)：

- **不下结论**：样本量/花费/窗口不达标 ≠ 失败，禁止输出「结构不行」
- **直接停**：Explore/Validate 门禁失败、指标明确劣化
- **进入验证**：Explore PASS 后进入跨窗复测与轻扩人群校验

## 项目结构

```
├── app_demo.py           # 主入口
├── card_library.py       # Card Library
├── evalset_sampler.py    # 评测集分层抽样（StructureEvaluationSet）
├── knowledge_store.py    # 复盘知识库（SQLite）
├── docs/
│   └── STOP_RULES.md     # 门禁止损逻辑
├── configs/
│   └── default_evalset_config.json
├── samples/
│   ├── example_creative_card.json  # 扩展字段示例
│   └── ...
├── data/
│   ├── card_library/     # cards.jsonl, cards_index.json
│   └── knowledge.db
├── MatrixMirix02/        # 完整模块（eval_schemas, explore_gate, 等）
└── ...
```

## 联系

myrawzm0406@163.com
