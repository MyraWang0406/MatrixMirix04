# 自动化投放素材生成与评审 Demo

## 环境准备

```bash
cd creative_eval_demo
pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，填入 OpenRouter API Key 和模型：

```bash
copy .env.example .env
# 编辑 .env，设置 OPENROUTER_API_KEY 和 OPENROUTER_MODEL
```

## 启动

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 使用说明

1. **左侧**：选择示例（game_card.json / ecommerce_card.json）或自定义输入结构卡片 JSON
2. 设置「生成变体数量」（默认 5）
3. 点击 **生成并评审**
4. **右侧**：查看评审表格（含 PASS/REVISE/KILL 门禁结果）
5. 点击 **下载 Markdown** 或 **下载 CSV** 导出结果

## 结构卡片字段

- `vertical`: `"game"` 或 `"ecommerce"`
- `product_name`: 产品/活动名称
- `target_audience`: 目标人群
- `key_selling_points`: 卖点列表
- `tone`: 语调
- `constraints`: 约束条件
- `extra_context`: 补充信息
