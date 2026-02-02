# 门禁止损逻辑 (Stop Rules)

本系统采用「样本量 / 花费 / 窗口不达标 ≠ 失败」原则。以下规则用于明确：何时不下结论、何时直接停、何时进入验证。

---

## 一、不下结论（INCONCLUSIVE / INSUFFICIENT）

**样本量、花费、窗口不达标时，禁止输出「结构不行」或「失败」。**

| 条件 | 输出 | 动作 |
|------|------|------|
| 探索窗 spend < min_spend（默认 500） | INSUFFICIENT | 提示「补足预算」后复测 |
| 验证窗窗口数 < 2 | INCONCLUSIVE | 提示「补足跨天复测数据」 |
| 轻扩人群无数据 | 可进入验证，但无轻扩校验 | 正常继续，轻扩阶段再补 |
| 曝光/安装/花费任一不达最小门槛 | INSUFFICIENT | 提示「样本不足」，建议补样本 |

**核心原则**：样本不足 → 不下结论 → 输出「补样本处方」，禁止输出「结构不行」。

---

## 二、直接停（FAIL / STOP）

**门禁失败、指标明确劣化时，建议停止或换层。**

| 条件 | 输出 | 动作 |
|------|------|------|
| Explore：≥2 指标优于 baseline 不满足 | FAIL | 结构暂不成立，建议换 hook/why_now |
| Validate：IPM 波动超阈值（ipm_cv > 0.35） | FAIL | 波动大，不建议放量 |
| Validate：IPM 回撤超阈值（ipm_drop > 30%） | FAIL | 回撤过大 |
| Validate：CPI 涨幅超阈值（cpi_increase > 25%） | FAIL | 成本恶化 |
| 轻扩人群：IPM 跌幅 / CPI 涨幅超阈值 | FAIL | 扩圈后劣化 |
| bucket 与 baseline 不一致（OFAAT 违规） | INVALID | 禁止对比，需修正实验设计 |

---

## 三、进入验证（PASS Explore → Validate）

**仅当 Explore 通过后，才进入验证阶段。**

| 条件 | 输出 | 动作 |
|------|------|------|
| Explore：≥2 指标优于 baseline 且 spend ≥ min_spend | PASS | 进入验证 |
| 验证窗 ≥2 个 + 指标在阈值内 | PASS | 可放量 |

---

## 四、状态流转

```
未测 → 探索中（小流量 Explore）
         ↓
     [INSUFFICIENT] → 补样本，保持探索中
     [FAIL]         → 换层/换结构，重新探索
     [PASS]         → 进验证
         ↓
进验证 → 可放量（跨窗稳定 + 轻扩通过）
         ↓
     [FAIL] → 止损或复测
     [PASS] → 放量
```

---

## 五、与 diagnosis 的对应

| failure_type | 含义 | Stop Rule 对应 |
|--------------|------|----------------|
| INCONCLUSIVE | 样本不足 | 一、不下结论 |
| EFFICIENCY_FAIL | Explore 效率不行 | 二、直接停（Explore FAIL） |
| QUALITY_FAIL | Validate 质量不行 | 二、直接停（Validate FAIL） |
| HANDOFF_MISMATCH | 承接断裂 | 二、直接停（指标打架） |
| OS_DIVERGENCE | iOS/Android 不一致 | 二、直接停（端内修正） |
| MIXED_SIGNALS | 指标打架 | 二、直接停（难归因） |
