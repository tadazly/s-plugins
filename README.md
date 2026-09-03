# S Plugins

`s-plugins` 是一个面向 Agent 的插件集合仓库。当前阶段仅支持 **Codex Plugins**；其他 Agent 平台尚未接入。

## 仓库结构

```text
.
├─ .agents/plugins/marketplace.json  # Codex marketplace 清单
├─ plugins/                          # 可选的仓库内插件源码
├─ scripts/update_marketplace.py     # 发布通知处理器
├─ scripts/validate_repo.py          # 仓库结构与 manifest 校验
├─ tests/                            # marketplace 自动化测试
└─ .github/workflows/                # 持续集成与自动更新
```

插件既可以直接存放在本仓库，也可以通过 marketplace 的 `git-subdir` source 指向独立 Git 仓库。仓库内插件使用以下结构：

```text
plugins/<plugin-name>/
├─ .codex-plugin/plugin.json         # 必需
├─ skills/                           # 可选
├─ hooks/                            # 可选
├─ assets/                           # 可选
├─ .mcp.json                         # 可选
└─ .app.json                         # 可选
```

## 使用 marketplace

从 GitHub 添加：

```powershell
codex plugin marketplace add tadazly/s-plugins
codex plugin marketplace list
```

本地开发时，也可以在仓库根目录执行：

```powershell
codex plugin marketplace add .
```

当前 marketplace 尚未包含具体插件。添加第一个插件后，重新加载 marketplace 即可在 Codex 中浏览和安装。

## 自动接收插件发布

插件仓库完成发布后，向本仓库发送 `plugin-released` 类型的 `repository_dispatch`。该事件被视为上游已经完成构建、测试和发布验收；本仓库会直接更新 marketplace，执行静态格式检查，然后提交到 `main`，不会重复拉取或验证上游发布包。

`client_payload` 格式：

```json
{
  "name": "design-rag",
  "url": "https://github.com/tadazly/design-rag.git",
  "path": "./plugins/design-rag",
  "ref": "v0.3.0",
  "category": "Productivity"
}
```

同一插件再次发布时会原位更新条目并保留 marketplace 顺序；重复发送相同版本不会产生新提交。

### 发布仓库发送通知

在插件仓库中创建一个仅授权目标 `s-plugins` 仓库、具有 `Contents: Read and write` 权限的 fine-grained personal access token，并保存为仓库 Secret：

```text
S_PLUGINS_DISPATCH_TOKEN
```

将以下步骤放在插件现有发布 job 的最后。只有前面的构建、测试、tag 和发布步骤全部成功后才会执行：

```yaml
- name: Notify s-plugins
  env:
    GH_TOKEN: ${{ secrets.S_PLUGINS_DISPATCH_TOKEN }}
    PLUGIN_REF: ${{ github.ref_name }}
  shell: bash
  run: |
    jq -n --arg ref "$PLUGIN_REF" '{
      event_type: "plugin-released",
      client_payload: {
        name: "design-rag",
        url: "https://github.com/tadazly/design-rag.git",
        path: "./plugins/design-rag",
        ref: $ref,
        category: "Productivity"
      }
    }' | gh api --method POST repos/tadazly/s-plugins/dispatches --input -
```

GitHub API 成功接收通知时返回 HTTP `204`。不要将 token 写入 workflow 或脚本正文。

## 添加插件

对于直接保存在本仓库的插件，使用 Codex 内置的 `$plugin-creator`，要求它：

1. 将插件创建到 `plugins/<plugin-name>/`。
2. 生成 `.codex-plugin/plugin.json`。
3. 更新 `.agents/plugins/marketplace.json`。
4. 验证插件和 marketplace。

插件名使用小写 kebab-case，并保持以下三处完全一致：

- `plugins/<plugin-name>` 目录名；
- `.codex-plugin/plugin.json` 中的 `name`；
- marketplace 条目中的 `name` 与 `source.path`。

## 校验

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

校验会检查 marketplace 格式、`local` 与 `git-subdir` source、插件目录映射、必需 manifest 字段、版本号以及未登记的本地插件目录。它只检查本仓库负责的数据，不重复验收已发送发布通知的上游插件。

Pull Request 和普通 `main` 分支推送会运行持续集成校验。自动更新 workflow 在提交前运行同一检查，因为 GitHub Actions 使用 `GITHUB_TOKEN` 产生的推送不会再次触发普通 `push` workflow。

## 参考

- [OpenAI：Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [OpenAI：Build plugins](https://learn.chatgpt.com/docs/build-plugins)
