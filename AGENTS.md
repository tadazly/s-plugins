# AGENTS.md

## 项目定位

- 本仓库用于维护可分发的 Agent Plugins，同时提供 Codex、Claude Code 与 WorkBuddy 三个插件市场。
- `.agents/plugins/marketplace.json`（Codex）是唯一数据源；`.claude-plugin/marketplace.json`（Claude Code）、`.codebuddy-plugin/marketplace.json`（WorkBuddy / CodeBuddy）和 README 插件目录由脚本生成。
- 未经明确要求，不添加以上三端以外平台的兼容层、manifest 或发布流程；新增平台时在 `scripts/validate_repo.py` 的 `GENERATED_MARKETPLACES` 中登记生成函数。

## Codex Plugin 约定

- 本地插件源码放在 `plugins/<plugin-name>/`，也允许 marketplace 使用 `git-subdir` 指向独立发布仓库。
- 每个本地插件必须包含 `plugins/<plugin-name>/.codex-plugin/plugin.json`。
- 插件名使用小写 kebab-case，并与目录名、manifest `name`、marketplace 条目保持一致。
- `skills/`、`hooks/`、`assets/`、MCP 配置和 `.app.json` 放在插件根目录，不放入 `.codex-plugin/`。Codex 的 MCP 配置不要命名为 `.mcp.json`，也不要放进 `mcp/` 目录，建议用 `.codex-mcp.json` 并在 manifest 中引用（原因见下一节）。
- 仅当对应文件真实存在时，才在 manifest 中声明 `skills`、`mcpServers` 或 `apps`。
- 新增、删除或重命名本地插件时，同步更新 `.agents/plugins/marketplace.json`。
- marketplace 新条目默认使用 `AVAILABLE`、`ON_INSTALL` 和与插件用途匹配的 `category`；不要无依据添加 `policy.products`。
- 每个 marketplace 插件条目都应包含 `version`、`description` 和完整 `interface` 展示字段；它们同时用于 Codex 安装前展示、Claude Code marketplace 和 README 插件目录，不另建重复元数据文件。
- 不手工编辑 README 的“插件目录”章节；使用 `scripts/sync_generated.py` 从 marketplace 生成。生成区以 Markdown 二级标题定位，不使用可见标记。
- `plugin-released` repository dispatch 表示上游已完成发布验收；首次登记必须提供完整来源和展示元数据，后续通知以 `name` 定位，以 `version` 和 `source.ref` 更新版本，并仅覆盖明确传入的展示字段。
- 接收端只进行 payload、marketplace 和 README 静态校验，然后直接更新 `main`，不重复构建或验收上游插件。

## Claude Code 与 WorkBuddy 约定

- 不手工编辑 `.claude-plugin/marketplace.json` 和 `.codebuddy-plugin/marketplace.json`；它们由 `scripts/sync_generated.py` 和 `scripts/update_marketplace.py` 从 Codex marketplace 生成，`scripts/validate_repo.py` 会拒绝漂移。
- 生成结果只包含各平台 schema 支持的字段，不写入 `policy`、`interface` 等 Codex 专属字段；映射规则集中在 `scripts/validate_repo.py` 的 `render_claude_marketplace` 与 `render_codebuddy_marketplace`。WorkBuddy 清单只写 CodeBuddy 文档列出的字段。
- `git-subdir` 的 `path` 在两端都不带 `./` 前缀；`policy.installation` 为 `NOT_AVAILABLE` 的插件不列出。
- 插件提供 `.claude-plugin/plugin.json`，建议再提供 `.codebuddy-plugin/plugin.json`（WorkBuddy 优先读取，缺失时退回 `.claude-plugin`），两者的 `name`、`version` 与 Codex manifest 一致。
- 插件根目录不放 `.mcp.json` 与 `mcp/*.json`：Claude Code 与 WorkBuddy 都会自动加载，WorkBuddy 还会让它们覆盖清单里的同名 server。MCP 要求见 README“支持 Claude Code 与 WorkBuddy”，`scripts/plugin_compat.py` 按各客户端规则检查。
- WorkBuddy 已实测市场添加与插件安装；插件 MCP 是否可用，以冒烟测试和实机验证为准，未经验证不要在文档中声称可用。

## 文档与验证

- 项目文档默认使用简体中文；技术术语、代码标识符和专有名词保留原文。
- 提交前运行 `python scripts/validate_repo.py` 与 `python -m unittest discover -s tests`。
- 修改 marketplace 后运行 `python scripts/sync_generated.py`。
- 对单个插件的变更，还应使用 Codex 的 `plugin-creator` validator 做插件级校验；Claude Code 可用时，再运行 `claude plugin validate .` 和 `claude plugin validate plugins/<plugin-name>`；CodeBuddy CLI 可用时（先退出 WorkBuddy），运行 `codebuddy plugin validate .`。
- 不提交凭据、访问令牌、私有 endpoint 或本地绝对路径。
