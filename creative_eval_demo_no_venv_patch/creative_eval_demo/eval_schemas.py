"""
评测系统原型：结构组合卡 + 结构级变体 + 元素标签
不调用任何模型 API，基于模拟数据构建。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# -------- 枚举定义 --------

MotivationBucket = Literal[
    "省钱", "体验", "社交", "胜负欲", "成就感", "收集", "爽感", "品质", "口碑", "其他",
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


# -------- 1. StrategyCard（结构组合卡）--------


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

    # 动机与触发
    motivation_bucket: MotivationBucket = Field(..., description="动机桶（必填枚举）")
    why_you_key: str = Field(default="other", description="Why you 稳定 key，评测/聚合用")
    why_you_label: str = Field(default="其他", description="Why you 展示文案，UI 用")
    why_now_trigger: WhyNowTrigger = Field(..., description="Why now 触发器（枚举）")

    @model_validator(mode="before")
    @classmethod
    def _normalize_why_you(cls, data: Any) -> Any:
        """兼容 why_you_bucket 旧格式：自动转为 why_you_key + why_you_label"""
        if isinstance(data, dict):
            wyb = data.get("why_you_bucket")
            if wyb is not None and "why_you_key" not in data and "why_you_label" not in data:
                label = str(wyb).strip()
                key = _WHY_YOU_LABEL_TO_KEY.get(label, "other")
                data = {**data, "why_you_key": key, "why_you_label": label or "其他"}
            if "why_you_key" not in data:
                data.setdefault("why_you_key", "other")
            if "why_you_label" not in data:
                data.setdefault("why_you_label", _WHY_YOU_KEY_TO_LABEL.get(data.get("why_you_key", "other"), "其他"))
        return data

    @property
    def why_you_bucket(self) -> str:
        """兼容旧代码：返回 why_you_label"""
        return self.why_you_label

    # 解释
    root_cause_gap: str = Field(default="", description="根因/缺口解释（文本）")

    # 资产化：证据点 + 承接预期（最小字段增量，向后兼容）
    proof_points: list[str] = Field(default_factory=list, description="证据点：如何让人信")
    handoff_expectation: str = Field(default="", description="承接第一屏：点进去 10 秒内必须看到什么")

    #  provenance（卡片来源，可选）
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
        ...,
        description="说服层表达：由 why_you_bucket + why_now_trigger + 一句可读表达组成，例：新赛季冲分黄金期，上手就能打出优势",
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
