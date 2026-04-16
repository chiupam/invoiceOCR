# 分支管理规范

## 分支结构

```
main (生产分支)
  │
  └── develop (开发分支)
        │
        ├── feat/xxx 功能分支
        ├── fix/xxx 修复分支
        ├── refactor/xxx 重构分支
        └── hotfix/xxx 热修复分支
```

## 分支说明

| 分支 | 用途 | 命名规范 | 合并目标 |
|------|------|----------|----------|
| `main` | 生产环境代码，始终保持稳定可部署 | — | — |
| `develop` | 开发主分支，汇总所有已完成的功能 | — | → `main`（通过PR） |
| `feat/*` | 新功能开发分支 | `feat/功能简称` | → `develop`（通过PR） |
| `fix/*` | Bug修复分支 | `fix/问题简称` | → `develop`（通过PR） |
| `refactor/*` | 重构优化分支 | `refactor/模块名` | → `develop`（通过PR） |
| `hotfix/*` | 生产环境紧急修复 | `hotfix/问题简称` | → `main` + `develop`（通过PR） |

## 工作流程

### 1. 日常开发流程

```bash
# 1. 从 develop 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feat/置信度提示

# 2. 在功能分支上开发
git add .
git commit -m "feat: 添加置信度提示功能"

# 3. 推送功能分支到远程
git push -u origin feat/置信度提示

# 4. 在 GitHub 上创建 Pull Request
#    目标: develop ← feat/置信度提示

# 5. 代码审查通过后，合并到 develop
```

### 2. 生产环境热修复流程

```bash
# 1. 从 main 创建热修复分支
git checkout main
git pull origin main
git checkout -b hotfix/修复登录问题

# 2. 修复并测试
git commit -m "fix: 修复登录会话超时问题"

# 3. 创建两个 PR
#    PR1: main ← hotfix/修复登录问题
#    PR2: develop ← hotfix/修复登录问题

# 4. 合并两个 PR
```

## 分支保护规则

### main 分支保护（必须）

- ✅ 禁止直接推送（`git push main` 被拒绝）
- ✅ 必须通过 Pull Request 合并
- ✅ 需要至少 1 人代码审查通过
- ✅ CI 测试必须全部通过

### develop 分支保护（必须）

- ✅ 禁止直接推送
- ✅ 必须通过 Pull Request 合并
- ✅ CI 测试必须全部通过

## Commit 消息规范

格式：`type: 简短描述`

| 类型 | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 添加发票置信度提示` |
| `fix` | Bug修复 | `fix: 修复上传失败后不跳转` |
| `refactor` | 代码重构 | `refactor: 提取OCR客户端为独立模块` |
| `chore` | 日常维护 | `chore: 移除未使用依赖` |
| `docs` | 文档更新 | `docs: 更新部署文档` |
| `test` | 测试相关 | `test: 添加置信度功能测试` |
| `security` | 安全修复 | `security: 修复开放重定向漏洞` |

## 开发环境配置

```bash
# .env 文件（不要提交到仓库）
APP_ENV=development
SECRET_KEY=your-secret-key-here
TENCENT_SECRET_ID=your-tencent-secret-id
TENCENT_SECRET_KEY=your-tencent-secret-key
DATABASE_URL=sqlite:///data/invoices.db
```

## 生产环境部署

```bash
# docker-compose.yml 中设置
environment:
  - APP_ENV=production
  - SECRET_KEY=${SECRET_KEY}  # 必须设置！
```

## 快速命令参考

```bash
# 更新本地 develop
git checkout develop && git pull origin develop

# 创建功能分支
git checkout -b feat/新功能名

# 提交代码
git add .
git commit -m "feat: 描述"
git push

# 查看分支状态
git branch -a
```
