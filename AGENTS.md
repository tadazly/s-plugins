# AGENTS.md

## 项目定位

- 本仓库用于维护可分发的 Agent Plugins。
- 当前只实现 Codex Plugins；未经明确要求，不添加其他 Agent 平台的兼容层、manifest 或发布流程。

## Codex Plugin 约定

- 本地插件源码放在 `plugins/<plugin-name>/`，也允许 marketplace 使用 `git-subdir` 指向独立发布仓库。
- 每个本地插件必须包含 `plugins/<plugin-name>/.codex-plugin/plugin.json`。
- 插件名使用小写 kebab-case，并与目录名、manifest `name`、marketplace 条目保持一致。
- `skills/`、`hooks/`、`assets/`、`.mcp.json` 和 `.app.json` 放在插件根目录，不放入 `.codex-plugin/`。
- 仅当对应文件真实存在时，才在 manifest 中声明 `skills`、`mcpServers` 或 `apps`。
- 新增、删除或重命名本地插件时，同步更新 `.agents/plugins/marketplace.json`。
- marketplace 新条目默认使用 `AVAILABLE`、`ON_INSTALL` 和与插件用途匹配的 `category`；不要无依据添加 `policy.products`。
- `plugin-released` repository dispatch 表示上游已完成发布验收；接收端只进行 payload 和 marketplace 静态校验，然后直接更新 `main`，不重复构建或验收上游插件。

## 文档与验证

- 项目文档默认使用简体中文；技术术语、代码标识符和专有名词保留原文。
- 提交前运行 `python scripts/validate_repo.py`。
- 对单个插件的变更，还应使用 Codex 的 `plugin-creator` validator 做插件级校验。
- 不提交凭据、访问令牌、私有 endpoint 或本地绝对路径。
