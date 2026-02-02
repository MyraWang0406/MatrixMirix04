"""
评测系统原型：结构组合卡 + 结构级变体 + 元素标签
不调用任何模型 API，基于模拟数据构建。

【核心原则】评测对象是「结构组合」（CreativeCard），而非视频文件。
视频是渲染结果，不参与结构胜率统计。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# -------- 枚举定义 --------

MotivationBucket = Literal[
    "省钱", "体验", "社交", "胜负欲", "成就感", "收集", "爽感", "品质", "口碑", "其他",
]

# 英文动机桶（用于跨语言/跨国家统计）
MotivationBucketEn = Literal[
    "boredom", "competition", "reward", "social", "romance", "convenience",
    "deal", "quality", "trust", "experience", "achievement", "other",
]


class WhyYouKey(str, Enum):
    """Why you 稳定 key（与 vertical 无关，词库扩展不崩溃）"""
    price_advantage = "price_advantage"
    limited_offer = "limited_offer"
    quality_guarantee = "quality_guarantee"
    word_of_mouth = "word_of_mouth"
    need_based = "need_based"
    experience_upgrade = "experience_upgrade"
    hero_easy = "hero_easy"
    season_reward = "season_reward"
    rank_easier = "rank_easier"
    social_showcase = "social_showcase"
    catharsis = "catharsis"
    other = "other"


# label -> key 映射（词库 label 转为稳定 key）
_WHY_YOU_LABEL_TO_KEY: dict[str, str] = {
    "价格优势": "price_advantage",
    "限时优惠": "limited_offer",
    "品质保证": "quality_guarantee",
    "口碑推荐": "word_of_mouth",
    "刚需满足": "need_based",
    "体验升级": "experience_upgrade",
    "新英雄上手快": "hero_easy",
    "赛季福利多": "season_reward",
    "上分更容易": "rank_easier",
    "社交炫耀": "social_showcase",
    "爽感释放": "catharsis",
    "其他": "other",
}
# key -> 默认 label（用于仅有 key 时）
_WHY_YOU_KEY_TO_LABEL: dict[str, str] = {v: k for k, v in _WHY_YOU_LABEL_TO_KEY.items()}

WhyNowTrigger = Literal[
    "新赛季刚开", "限时活动", "节日促销", "版本更新", "热度上升",
    "竞品疲软", "节点冲刺", "用户召回",
    "涨价预警", "大促来袭", "限时秒杀", "满减活动", "库存告急", "新品首发", "会员日特惠",
    "新手福利", "周末双倍", "赛季末冲刺", "新英雄上线",
    "其他",
]
ElementType = Literal["hook", "why_you", "why_now", "sell_point", "sell_point_copy", "cta", "asset"]


# -------- 扩展结构（Creative Card 增强，可枚举/可统计） --------


class SegmentSpec(BaseModel):
    """投放人群/场景规格（可枚举，用于分层抽样与胜率统计）"""

    country: str = Field(default="", description="国家/地区")
    language: str = Field(default="", description="语言")
    os: Literal["iOS", "Android", "all"] = Field(default="all", description="操作系统")
    user_type: Literal["new", "returning", "retargeting"] = Field(
        default="new",
        description="用户类型：新客/回流/再营销",
    )
    context_scene: str = Field(
        default="",
        description="场景：无聊/通勤/睡前/对比购买 等",
    )


class InsightTension(BaseModel):
    """洞察张力（用于解释为什么赢/为什么输）"""

    root_gap: str = Field(default="", description="核心心理/现实缺口")
    trigger: str = Field(default="", description="触发器：无聊/压力/被拒/想赢")
    contrast: str = Field(default="", description="反差认知：以为很难→实际很爽")


class FormatPattern(BaseModel):
    """表达模式（可枚举，用于结构胜率统计）"""

    narrative_type: str = Field(
        default="",
        description="叙事类型：POV/对比/反转/挑战/剧情",
    )
    rhythm: str = Field(
        default="",
        description="节奏：0-3s爆点 / 铺垫→爆",
    )
    evidence_style: str = Field(
        default="",
        description="证据风格：画面/数据/口碑",
    )


class HandoffExpectation(BaseModel):
    """承接预期（落地页/商店页一致性）"""

    first_screen_promise: str = Field(
        default="",
        description="点进去 10 秒内必须看到什么",
    )
    consistency_check: bool = Field(
        default=False,
        description="是否与素材承诺一致",
    )


# -------- 1. StrategyCard / CreativeCard（结构组合卡）--------
#
# 评测最小单元 = 结构组合，不是视频。
# 每张卡 = 一组结构变量；视频是渲染结果，不参与结构胜率统计。
#


class StrategyCard(BaseModel):
    """结构组合卡：评测系统的核心输入"""

    card_id: str = Field(..., description="卡片唯一 ID")
    version: str = Field(default="1.0", description="版本")

    # 投放维度
    vertical: str = Field(default="casual_game", description="casual_game / ecommerce")
    country: str = Field(default="", description="投放国家/地区")
    os: str = Field(default="", description="iOS / Android / all")
    objective: str = Field(default="", description="install / purchase / lead 等")
    segment: str = Field(default="", description="人群分层")

    # 动机与触发（向后兼容：历史 JSON 可能缺字段）
    motivation_bucket: str = Field(default="其他", description="动机桶（可枚举）")
    why_you_key: str = Field(default="other", description="Why you 稳定 key，评测/聚合用")
    why_you_label: str = Field(default="其他", description="Why you 展示文案，UI 用")
    why_now_trigger: str = Field(default="其他", description="Why now 触发器（可枚举）")

    @model_validator(mode="before")
    @classmethod
    def _normalize_card_fields(cls, data: Any) -> Any:
        """兼容历史 JSON：why_you_bucket、why_now_phrase/why_now_trigger_bucket 等旧字段映射"""
        if not isinstance(data, dict):
            return data
        data = dict(data)

        # why_you 兼容
        wyb = data.get("why_you_bucket")
        if wyb is not None and "why_you_key" not in data and "why_you_label" not in data:
            label = str(wyb).strip()
            key = _WHY_YOU_LABEL_TO_KEY.get(label, "other")
            data["why_you_key"] = key
            data["why_you_label"] = label or "其他"
        data.setdefault("why_you_key", "other")
        data.setdefault("why_you_label", _WHY_YOU_KEY_TO_LABEL.get(data.get("why_you_key", "other"), "其他"))

        # why_now_trigger 兼容：why_now_phrase / why_now_trigger_bucket / why_now / trigger
        if "why_now_trigger" not in data or data.get("why_now_trigger") is None or data.get("why_now_trigger") == "":
            for old_key in ("why_now_phrase", "why_now_trigger_bucket", "why_now", "trigger", "why_now_reason"):
                if data.get(old_key):
                    val = str(data[old_key]).strip()
                    if val:
                        data["why_now_trigger"] = val
                        break
            data.setdefault("why_now_trigger", "其他")

        # motivation_bucket 兼容
        if "motivation_bucket" not in data or data.get("motivation_bucket") is None or data.get("motivation_bucket") == "":
            data.setdefault("motivation_bucket", "其他")

        return data

    @property
    def why_you_bucket(self) -> str:
        """兼容旧代码：返回 why_you_label"""
        return self.why_you_label

    # 解释
    root_cause_gap: str = Field(default="", description="根因/缺口解释（文本）")

    # 资产化：证据点 + 承接预期（向后兼容）
    proof_points: list[str] = Field(default_factory=list, description="证据点：如何让人信")
    handoff_expectation: str = Field(default="", description="承接第一屏（兼容旧格式）")
    handoff_expectation_detail: HandoffExpectation | None = Field(
        default=None,
        description="承接预期结构化（first_screen_promise, consistency_check）",
    )

    # 扩展：投放人群/场景规格（可枚举）
    segment_spec: SegmentSpec | None = Field(default=None, description="人群/场景结构化")

    # 扩展：洞察张力（用于失败解释与复盘）
    insight_tension: InsightTension | None = Field(default=None, description="root_gap/trigger/contrast")

    # 扩展：表达模式（可统计叙事/节奏/证据风格）
    format_pattern: FormatPattern | None = Field(default=None, description="narrative_type/rhythm/evidence_style")

    # 风险标注（夸大/误导/白量）
    risk_flags: list[str] = Field(default_factory=list, description="风险标签")

    # provenance（卡片来源）
    source_channel: str = Field(default="", description="来源渠道")
    source_url: str = Field(default="", description="来源 URL")
    source_date: str = Field(default="", description="来源日期")


# -------- 2. Variant（结构级变体）--------


class AssetVariables(BaseModel):
    """资产层变量"""
    subtitle_template: str = Field(default="", description="字幕模板")
    bgm: str = Field(default="", description="BGM/背景音乐")
    rhythm: str = Field(default="", description="节奏/剪辑节奏")
    shot_template: str = Field(default="", description="镜头模板")


class Variant(BaseModel):
    """结构级变体：继承自 StrategyCard 的具体创意表达"""

    variant_id: str = Field(..., description="变体唯一 ID")
    parent_card_id: str = Field(..., description="所属 StrategyCard 的 card_id")

    hook_type: str = Field(default="", description="Hook 类型")
    sell_point: str = Field(
        default="",
        description="说服层表达：由 why_you_bucket + why_now_trigger + 一句可读表达组成",
    )
    cta_type: str = Field(default="", description="CTA 类型，如：立即下载/领福利/马上玩")

    expression_template: str = Field(
        default="",
        description="叙事模板标识：3幕/5镜头 等",
    )
    asset_variables: AssetVariables | dict[str, Any] = Field(
        default_factory=AssetVariables,
        description="字幕模板/BGM/节奏/镜头模板",
    )

    # 可选：用于元素级拆解时的细粒度标注
    why_you_expression: str = Field(default="", description="Why you 具体表述（可选）")
    why_now_expression: str = Field(default="", description="Why now 具体表述（可选）")

    # OFAAT 生成时写入：单变量改动标识
    changed_field: str = Field(
        default="",
        description="本次相对基线改动的字段：hook_type / sell_point / cta / asset_var，基线为空",
    )
    delta_desc: str = Field(
        default="",
        description="人类可读改动描述，如：CTA: 立即下单 -> 领券立减",
    )


# -------- 3. ElementTag（元素标签）--------


class ElementTag(BaseModel):
    """元素标签：用于元素级贡献分析"""

    element_type: ElementType = Field(..., description="hook / why_you / why_now / cta / asset")
    element_value: str = Field(default="", description="元素取值")


# -------- 拆解函数 --------


def decompose_variant_to_element_tags(variant: Variant) -> list[ElementTag]:
    """
    将 Variant 拆解为一组 ElementTag。
    用于结构级 Gate 判断 + 元素级贡献分析。
    """
    tags: list[ElementTag] = []

    # hook
    if variant.hook_type:
        tags.append(ElementTag(element_type="hook", element_value=variant.hook_type))

    # why_you：优先用 why_you_expression，否则用 sell_point
    why_you_val = variant.why_you_expression or variant.sell_point
    if why_you_val:
        tags.append(ElementTag(element_type="why_you", element_value=why_you_val))

    # why_now：优先用 why_now_expression，否则用 sell_point
    why_now_val = variant.why_now_expression or variant.sell_point
    if why_now_val:
        tags.append(ElementTag(element_type="why_now", element_value=why_now_val))

    # sell_point：说服层表达（why_you + why_now 的可读综合）
    if variant.sell_point:
        tags.append(ElementTag(element_type="sell_point", element_value=variant.sell_point))

    # cta
    if variant.cta_type:
        tags.append(ElementTag(element_type="cta", element_value=variant.cta_type))

    # asset：从 asset_variables 拆出多个 asset 标签
    asset = variant.asset_variables
    if isinstance(asset, dict):
        for k, v in asset.items():
            if v and isinstance(v, str):
                tags.append(ElementTag(element_type="asset", element_value=f"{k}={v}"))
    else:
        if asset.subtitle_template:
            tags.append(
                ElementTag(element_type="asset", element_value=f"subtitle_template={asset.subtitle_template}")
            )
        if asset.bgm:
            tags.append(ElementTag(element_type="asset", element_value=f"bgm={asset.bgm}"))
        if asset.rhythm:
            tags.append(ElementTag(element_type="asset", element_value=f"rhythm={asset.rhythm}"))
        if asset.shot_template:
            tags.append(
                ElementTag(element_type="asset", element_value=f"shot_template={asset.shot_template}")
            )

    return tags


# -------- 三层评测集模型 --------
#
# CreativeSet / EvaluationSet 本质是 CreativeCard 的组合。
# 每张卡 = 一组结构变量（不是一个 mp4）；视频是渲染结果，不参与结构胜率统计。
#
# StructureEvaluationSet 见 evalset_sampler.py（dataclass，已实现）
#


class ExplorationEvaluationSet(BaseModel):
    """
    探索评测集（小流量）。
    - 固定 segment
    - 有 baseline 对照
    - 有早期门禁指标（IPM/CPI/early_roas）
    """

    cards: list["StrategyCard"] = Field(default_factory=list)
    segment_fixed: SegmentSpec | None = None
    baseline_card: "StrategyCard | None" = None
    min_spend: float = 500.0
    min_better_metrics: int = 2


class ValidationEvaluationSet(BaseModel):
    """
    验证评测集（放量前）。
    - 跨时间窗口复测
    - 轻扩人群
    """

    card: "StrategyCard"
    window_metrics: list[dict[str, Any]] = Field(default_factory=list)
    light_expansion_metrics: dict[str, Any] | None = None
