# GitHub 操作说明

本地仓库必须先准备、检查并提交，再连接远程。推荐创建为私有仓库，待题目版权、优秀论文授权和团队隐私全部审查后再考虑公开。

## 目标账号

远程仓库只能创建在用户指定的 `dcy0419-ddddcy` 账号下。任何工具显示其他账号时立即停止，不得继续创建或推送。

## 推荐仓库名

`cumcm-blind-modeling-lab`

## 使用 GitHub CLI

安装 GitHub CLI 后，在 PowerShell 中执行：

```powershell
gh auth login --hostname github.com --web --git-protocol https
gh auth status
```

浏览器会显示一次性授权页面。登录和授权必须由用户本人完成，不要把验证码、密码或令牌交给模型。`gh auth status` 必须明确显示 `dcy0419-ddddcy` 后，才能执行：

```powershell
gh repo create dcy0419-ddddcy/cumcm-blind-modeling-lab --private --source . --remote origin --push
```

创建前再次检查 `.gitignore`，确认 `tools/blind_mapping.local.json`、`管理员区/`、`tmp/` 和当年未授权优秀论文不会进入提交。
