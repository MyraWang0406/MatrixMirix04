# GitHub + Streamlit Cloud 部署指南

## 1. 推送到 GitHub 需要包含的文件

### 必须上传
```
MatrixMirix02/
├── app_demo.py              # 主应用
├── streamlit_app.py         # Streamlit 入口（调用 app_demo.main）
├── requirements.txt         # 依赖
├── path_config.py           # 路径配置
├── ui/
│   └── styles.py            # 样式
├── samples/                 # 全部
│   ├── vertical_config.json
│   ├── eval_strategy_card*.json
│   └── ...
├── configs/
│   └── default_evalset_config.json
├── MatrixMirix02/           # 业务模块
│   ├── eval_schemas.py
│   ├── element_scores.py
│   ├── simulate_metrics.py
│   ├── explore_gate.py
│   ├── validate_gate.py
│   ├── diagnosis.py
│   ├── variant_suggestions.py
│   ├── decision_summary.py
│   ├── vertical_config.py
│   ├── eval_set_generator.py
│   ├── ofaat_generator.py
│   ├── scoring_eval.py
│   └── ...
├── card_library.py
├── evalset_sampler.py
├── knowledge_store.py
├── scripts/
│   ├── smoke_check.py
│   └── validate_mock_data.py
└── data/                    # 如有 card_library 数据
```

### 不要上传
- `.venv/`、`venv/`、`__pycache__/`
- `*.pyc`、`.env`、`*.db`（知识库 DB 可选，可空库部署）
- `node_modules/`、`.cursor/`

## 2. Streamlit Community Cloud 配置

1. 打开 https://share.streamlit.io，用 GitHub 登录
2. **New app**
3. **Repository**：`MyraWang0406/AIGC-auto-ads`（或你的仓库）
4. **Branch**：`main`
5. **Main file path**（二选一）：
   - 若仓库根目录是 `MatrixMirix02/`：填 `streamlit_app.py`
   - 若仓库根目录是项目根、`MatrixMirix02` 是子目录：填 `MatrixMirix02/streamlit_app.py`
6. **Advanced settings**：通常无需配置 Secrets（使用模拟数据）
7. 点击 **Deploy**

## 3. 推荐仓库根目录结构

为让 Streamlit Cloud 简单识别入口，建议：

```
AIGC-auto-ads/           # 仓库根
├── streamlit_app.py     # 入口（若放根目录）
├── requirements.txt
├── MatrixMirix02/       # 主项目目录
│   ├── app_demo.py
│   ├── samples/
│   ├── ...
```

此时 **Main file path** 填：`streamlit_app.py`

若 `streamlit_app.py` 在 `MatrixMirix02/` 内，则填：`MatrixMirix02/streamlit_app.py`

## 4. requirements.txt 示例

```
streamlit>=1.30,<3
pydantic>=2,<3
```

## 5. 部署后验证

- 访问 `https://你的app名.streamlit.app`
- 点击 **Health** 检查依赖与路径
- 若报错：查看 Cloud 日志，确认 `samples/`、`path_config` 等路径正确
