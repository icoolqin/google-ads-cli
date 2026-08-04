# Google Ads CLI

[English](README.md) · [简体中文](README.zh-CN.md)

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Google Ads API v25](https://img.shields.io/badge/Google%20Ads%20API-v25-4285F4)
![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)

`gads` 是一个安全、可脚本化、适合 AI Agent 使用的 Google Ads API 命令行工具。它基于
Google 官方 Python 客户端，提供账号发现、GAQL 报表、Campaign 操作、App Campaign
创建、素材上传和通用 mutation 等实用能力。

仓库还包含一个 Codex skill，让 AI Agent 也遵循同一套安全流程，而不是临时拼接未经验证的
API 请求。

> [!IMPORTANT]
> 这是一个独立的开源项目，与 Google 没有关联，也未获得 Google 背书。Google Ads 是
> Google LLC 的商标。

## 为什么写操作分成三步

每个修改账号的命令都有三种明确模式：

| 模式 | 参数 | 实际行为 |
| --- | --- | --- |
| 计划 | 无 | 在本地构造并校验 protobuf 请求，然后打印操作计划；不需要凭证，也不会发起网络请求。 |
| 验证 | `--validate-only` | 把请求交给 Google Ads 校验，但不应用修改。 |
| 执行 | `--execute` | 真正应用修改，并在本地审计日志中记录经过脱敏的摘要。 |

默认是计划模式。复制粘贴一条命令不会仅仅因为语法正确就开始花钱。新建 App Campaign
永远从 `PAUSED` 状态开始，启用广告是一个独立、可复核的动作。

## 能做什么

- 完成单用户 OAuth 授权并创建私密的 `google-ads.yaml`
- 管理多个不含密钥的账号 profile
- 发现直接可访问账号和递归的经理账号层级
- 执行、校验任意 GAQL，并查询可用的 Google Ads 字段
- 输出表格、JSON、JSONL 或 CSV
- 执行账号、Campaign、Ad Group、广告、每日表现、转化、单素材评级和广告网络分布等常用报表
- 查看 Campaign、预算、Ad Group、广告、素材和转化操作
- 暂停、启用或移除 Campaign，修改每日预算
- 原子化创建包含预算、定向、Ad Group、App Ad 和素材的 App Campaign
- 上传图片素材、创建 YouTube 素材
- 查看 App Ad 真实挂载的素材，并原位增删，无需重建 Ad Group
- 查看账户余额、扣税后的可投净额和可投天数
- 查看账户变更历史（谁在什么时候改了什么）
- 查询地理位置和语言常量
- 执行带 API 版本的 `GoogleAdsService.Mutate` YAML 清单
- 用确定性的计划哈希保存不含密钥的 JSONL 审计记录

## 开始前需要准备

你需要：

1. Python 3.11 或更高版本。
2. [`uv`](https://docs.astral.sh/uv/getting-started/installation/)。
3. 拥有 developer token 的 Google Ads 经理账号。
4. 已启用 Google Ads API 的 Google Cloud 项目。
5. 一个 OAuth 2.0 **桌面应用**客户端 JSON。
6. 能访问目标 Ads 账号的 Google 用户。

Google 会给每个 developer token 分配访问级别：

| 访问级别 | 可访问账号 | 每日操作数 |
| --- | --- | ---: |
| Test | 测试账号 | 15,000 |
| Explorer | 测试和正式账号 | 正式账号 2,880；测试账号 15,000 |
| Basic | 测试和正式账号 | 15,000 |
| Standard | 测试和正式账号 | 大部分服务不限量 |

正式使用前，请以 Google 最新的
[developer token 指南](https://developers.google.com/google-ads/api/docs/api-policy/developer-token)
和[访问级别表](https://developers.google.com/google-ads/api/docs/api-policy/access-levels)为准。

## 五分钟安装

### 1. 安装 `uv`

macOS 使用 Homebrew：

```bash
brew install uv
```

Linux、Windows 或其他安装方式请查看
[uv 官方说明](https://docs.astral.sh/uv/getting-started/installation/)。

### 2. 下载仓库

克隆或下载仓库，然后进入仓库根目录：

```bash
cd google-ads-cli
```

### 3. 安装 CLI 和 Codex skill

```bash
./scripts/install-local.sh
gads --version
```

安装脚本会创建隔离的、可编辑的 `uv` tool，并把 `skills/google-ads` 链接到 Codex
skills 目录。只安装 CLI：

```bash
uv tool install .
```

只在仓库里开发、不安装全局命令：

```bash
uv sync --dev
uv run gads --help
```

## 配置 Google 访问权限

### 1. 获取 developer token

登录 Google Ads **经理账号**，打开
[API Center](https://ads.google.com/aw/apicenter)，申请 developer token。这里的“经理账号”
是账号类型（MCC），不是客户账号中的管理员角色。如果页面提示 API Center 只对经理账号
开放，请在 Google Ads 账号选择器中切换到 MCC，或先创建一个经理账号。

新申请可能会被自动批准为 Explorer 访问权限；否则会先获得测试账号访问权限。Explorer、
Basic 和 Standard 可以在各自限额内访问正式账号。具体以 Google 当前的
[developer token 访问权限说明](https://developers.google.com/google-ads/api/docs/api-policy/developer-token)
为准。

### 2. 创建 OAuth 桌面应用

在 Google Cloud 中：

1. 创建或选择一个项目。
2. 启用 **Google Ads API**。
3. 配置 OAuth consent screen。
4. 创建应用类型为 **Desktop app** 的 OAuth 客户端。
5. 下载客户端 JSON，并把它放在本仓库之外。

OAuth 应用的发布状态为 **Testing** 时，需要在 **Google Auth Platform → Audience →
Test users** 中加入每个将要授权 CLI 的 Google 用户。MCC 管理员不会自动成为 OAuth
测试用户。Ads scope 的测试授权（包括离线 refresh token）会在 7 天后过期；需要长期稳定
运行时，应把应用发布为 Production，并在 Google 要求时完成验证。

控制台步骤如有变化，请参考 Google 的
[OAuth 指南](https://developers.google.com/google-ads/api/docs/oauth/overview)。

### 3. 授权

运行：

```bash
gads auth login \
  --client-secrets /absolute/path/to/client_secret.json \
  --login-customer-id 1111111111 \
  --customer-id 2222222222
```

developer token 会通过隐藏输入框读取。命令会打开 Google OAuth 页面，创建权限为
`0600` 的凭证 YAML，并创建一个不含密钥的 CLI profile。登录页会强制显示账号选择器；
请选择能够直接访问 `--login-customer-id` 所指定 MCC 的 Google 用户。

- `customer_id` 是实际要管理 Campaign 和数据的客户账号。
- `login_customer_id` 是用来访问该客户账号的经理账号；直接访问客户账号时可以省略。
- 可以输入带连字符的 ID，CLI 会规范化为 10 位数字。

请区分下面四种身份：

| 项目 | 作用 |
| --- | --- |
| developer token 所有者 | 在 API Center 签发 token 的 MCC。 |
| OAuth 客户端 | Google Cloud 项目中的 Desktop app。 |
| OAuth Google 用户 | 实际同意授权的人，必须拥有相应 Google Ads 权限。 |
| login/target customer | 请求头中的 MCC，以及真正查询数据的客户账号。 |

无法自动打开浏览器时，加上 `--no-browser`。在能够访问同一本地回调地址的浏览器中打开
命令打印的 URL 并完成授权。

### 4. 验证连接

```bash
gads auth test
gads accounts accessible
gads accounts hierarchy --manager-id 1111111111
gads accounts show
```

`accounts accessible` 只列出直接访问的账号；经理账号下面的客户账号请用
`accounts hierarchy` 查看，并显式传入经理账号 ID，不要让它从客户账号 profile 开始。

## 第一次读取数据

全局参数必须放在命令组**之前**：

```bash
gads --profile default --customer-id 2222222222 --format json campaigns list
```

常用读取命令：

```bash
gads --format json accounts show
gads --format json budgets list
gads --format json adgroups list
gads --format json ads list
gads --format json assets list
gads --format json conversions list
```

预置报表：

```bash
gads reports list
gads --format json reports run campaigns --date-range LAST_30_DAYS
gads --format csv reports run daily --date-range 2026-07-01:2026-07-28
```

原始 GAQL：

```bash
gads query validate --file examples/app-campaign-performance.gaql
gads --format jsonl query run \
  --file examples/app-campaign-performance.gaql \
  --limit 1000
```

不确定字段名时直接查询：

```bash
gads --format json fields describe campaign.app_campaign_setting.app_id
gads --format json fields search 'metrics.%' --limit 50
```

## 第一次安全写入

同一条命令依次经过计划、验证、执行和回读：

```bash
# 1. 本地计划；账号不会变化
gads campaigns set-status 123456789 PAUSED

# 2. 交给 Google 校验；账号仍不会变化
gads campaigns set-status 123456789 PAUSED --validate-only

# 3. 真正应用
gads campaigns set-status 123456789 PAUSED --execute

# 4. 回读验证
gads campaigns get 123456789
```

`--execute` 和 `--validate-only` 不能同时使用。日常停投优先选择 `PAUSED`；移除是另一种
通常不可逆的 Google Ads 生命周期操作。

按账号币种修改预算：

```bash
gads budgets set-amount 987654321 50
gads budgets set-amount 987654321 50 --validate-only
gads budgets set-amount 987654321 50 --execute
```

修改前先运行 `gads accounts show`，确认账号币种。

## 创建 App Campaign

下面是通用 iOS 示例，默认只生成本地计划：

```bash
gads --format json campaigns create-app \
  --name "Example App · US · Install" \
  --app-id 000000000 \
  --app-store APPLE_APP_STORE \
  --daily-budget 50 \
  --goal installs \
  --target-cpa 2.50 \
  --headline "Create Something New" \
  --headline "Your Ideas, Made Simple" \
  --description "Turn an idea into something worth sharing." \
  --description "Create, refine, and share in just a few steps." \
  --location 2840 \
  --language 1000
```

请把示例 App Store ID、文案、定向、预算和出价全部替换为经过确认的真实值。Android
使用包名作为 `--app-id`，并传入 `--app-store GOOGLE_APP_STORE`。

计划会在一个原子请求中创建非共享预算、暂停状态的多渠道 Campaign、位置和语言条件、
启用的 Ad Group 以及启用的 App Ad。用相同参数加 `--validate-only` 校验，检查结果后再
加 `--execute` 执行。

启用花费前，必须确认账单、转化跟踪、账号币种、政策状态、定向、素材和应用商店页面。
使用应用内行为或价值出价前，先查看真实的转化资源：

```bash
gads --format json conversions list
```

## 上传创意素材

图片在上传前会在本地检查格式和尺寸：

```bash
gads assets upload-image /absolute/path/creative.png --name "US Creative 1"
gads assets upload-image /absolute/path/creative.png \
  --name "US Creative 1" \
  --validate-only
gads assets upload-image /absolute/path/creative.png \
  --name "US Creative 1" \
  --execute
```

计划输出不会包含图片二进制，只显示 SHA-256 摘要。

创建 YouTube 素材：

```bash
gads assets create-youtube VIDEO_ID --name "US Demo 15s"
```

Google Ads 素材通常不可修改。要停止某个素材投放，请修改引用它的广告或关联。

## 原位修改 App Ad 素材

App Ad 在同一 Ad Group 内不能新建第二条，也不能删除，但它的**素材字段是可以更新的**。
每改一次素材就重建 Ad Group 没有必要，而且会留下删不掉的广告。

查看广告真实挂载的素材，附带槽位占用和画幅覆盖度：

```bash
gads ads assets 111222333444
```

`ad_group_ad_asset_view` **不是**真相来源：它会保留历史关联，数量可能超过广告实际挂载的素材。
这两个命令读的是 `app_ad.*`。

素材字段是整字段替换：对 `app_ad.images` 用 `update_mask` 更新时，payload 里没列出的素材会被直接丢弃。
`set-assets` 会先读取当前素材，再把你的增删应用上去：

```bash
gads ads set-assets 111222333444 --add-video 555000111222 --remove-video 555000333444
gads ads set-assets 111222333444 --add-video 555000111222 --validate-only
gads ads set-assets 111222333444 --add-video 555000111222 --execute
```

`--set-image`、`--set-video`、`--set-headline`、`--set-description` 用于整体替换某个列表。
超出每 Ad Group 上限、素材重复、移除广告上没有的素材、把视觉素材清空——这些都会在请求发出前被拦下。

每次改动都会触发一次广告审核，所以请把素材变更攒成一次调用。

## 查看余额与可投天数

```bash
gads billing show
gads billing show --tax-rate 0.06
```

`account_budget` 返回的是**扣税后的可投净额**。预付充值在后台显示的是含税金额，到这里已经除过当地税率，
所以真实可投天数比后台数字看起来的短——`--tax-rate` 会额外打印一列含税等价金额用于对账。
可投天数默认按启用中 Campaign 的日预算之和估算，可用 `--daily-budget` 覆盖。

账户赠金（"花 X 送 X"）**完全不在 API 里**，只能在后台查看。

## 查看变更历史

```bash
gads changes list --days 14
gads changes list --days 7 --resource-type CAMPAIGN_BUDGET
gads changes list --campaign-id 123456789 --limit 500
```

`change_event` 只保留 30 天，且要求闭区间时间窗和 `LIMIT`；这个命令会自动补齐这三项。

## 使用通用 mutation 清单

常见操作都有专用命令。对于 `GoogleAdsService.Mutate` 支持的其他资源，可以使用带版本的
YAML 清单：

```bash
gads --format json mutate schema
gads mutate apply examples/pause-campaign.yaml
gads mutate apply examples/pause-campaign.yaml --validate-only
gads mutate apply examples/pause-campaign.yaml --execute
```

清单示例：

```yaml
label: pause-one-campaign
customer_id: "1234567890"
api_version: v25
partial_failure: false
response_content_type: RESOURCE_NAME_ONLY
operations:
  - resource: campaign
    action: update
    data:
      resourceName: customers/1234567890/campaigns/111
      status: PAUSED
    update_mask:
      - status
```

字段使用 protobuf JSON 名称，枚举使用字符串，并明确填写 update mask。同一原子请求中，
后面的操作引用前面新建的资源时，可以使用临时负数资源 ID。

## Profile 和环境变量

无需重复 OAuth 即可添加 profile：

```bash
gads config init \
  --name production \
  --credentials /absolute/path/to/google-ads.yaml \
  --login-customer-id 1111111111 \
  --customer-id 2222222222 \
  --api-version v25
```

用 `--profile production` 或 `GADS_PROFILE=production` 选择。

纯环境变量认证支持：

```text
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_LOGIN_CUSTOMER_ID
GOOGLE_ADS_JSON_KEY_FILE_PATH
GOOGLE_ADS_USE_APPLICATION_DEFAULT_CREDENTIALS
GADS_CUSTOMER_ID
GADS_API_VERSION
```

只设置所选认证方式对应的那组凭证。优先使用私密凭证文件，不要把密钥放进 shell 历史或
提交到仓库的 dotenv 文件。

查看本地路径但不显示密钥内容：

```bash
gads config path
gads config show
gads audit list
```

## 配合 Codex 使用

`./scripts/install-local.sh` 会把附带的 `google-ads` skill 链接到 Codex skills 目录。
例如：

```text
Use $google-ads to report campaign performance for the last 30 days.
```

Codex 会遵循读取 → 计划 → 验证 → 执行 → 回读的流程。skill 不会绕过 `--execute`、
Google 授权、developer token 访问级别或账号权限。

## 常见问题

| 现象 | 常见原因和下一步 |
| --- | --- |
| “API Center is only available to manager accounts” | 当前选中的是客户账号；请切换或创建经理账号（MCC）。客户账号的管理员权限不等于经理账号。 |
| OAuth `403 access_denied`，应用仍在测试 | 在 Google Auth Platform → Audience → Test users 添加当前 Google 用户，保存后重试。 |
| `DEVELOPER_TOKEN_NOT_APPROVED` | token 无权访问该正式账号；检查 API Center 中的访问级别。 |
| `USER_PERMISSION_DENIED` | OAuth 用户无权访问所选客户账号或经理账号；重新授权并选择正确用户，`gads auth test` 也会检查 MCC 的直接访问权限。 |
| login-customer 相关错误 | `login_customer_id` 不是该客户账号的上级经理，或两个 ID 填反了。 |
| OAuth `invalid_grant` | refresh token 被撤销、OAuth 客户端发生变化或授权过期；重新运行 `gads auth login`。 |
| `ServiceUnavailable`、DNS 或 “No route to host” | 检查 VPN、代理、防火墙和 IPv6 路由。macOS 会自动使用系统解析器；其他环境可尝试 `GRPC_DNS_RESOLVER=native gads auth test`。 |
| “Missing customer ID” | 在命令前传入 `--customer-id`，或把它保存到当前 profile。 |
| 全局参数无法识别 | 把 `--profile`、`--customer-id`、`--api-version` 和 `--format` 放在命令组之前。 |
| 本地计划成功但 Google 校验失败 | 查看结构化错误和 `request_id`，再用 `gads fields describe` 检查报错字段。 |

不要把凭证粘贴到 issue 中。私密报告方式见 [SECURITY.md](SECURITY.md)。

## 数据与安全模型

- Git 默认忽略密钥、OAuth 文件、key、dotenv、缓存和构建产物。
- 操作系统支持 POSIX 权限时，凭证和 profile 会以 `0600` 写入。
- CLI 不会打印凭证内容。
- 审计日志只记录客户 ID、API 版本、模式、结果、操作数、计划哈希、request ID 和脱敏错误，
  不记录 token 或完整 mutation 请求。
- Google Ads mutation 没有通用幂等键，因此工具不会额外添加笼统的自动重试。
- 单元测试不需要 Google 凭证，也不会连接或修改 Google Ads 账号。

用于正式账号前请阅读 [SECURITY.md](SECURITY.md)。账号权限、政策合规、广告花费，以及每条
带 `--execute` 的命令，最终都由操作者负责。

## 防止真实账号数据进入公共仓库

本仓库是公开的，**提交进去的值即使之后删掉也会永远留在 git 历史里**，所以真正起作用的关卡在提交之前，不是 CI：

```bash
cp .private-values.example .private-values   # 填入你自己账号的真实值
uv run pre-commit install
```

`.private-values` 已被 gitignore，永远不要提交。

示例、测试、文档一律只能用合成标识符——包括客户/系列/广告组/广告/素材 ID、账户预算与结算 ID、
付款账号、余额、邮箱、在投广告文案、内部素材命名。

`detect-secrets` 在这里帮不上忙：它认的是凭证，不是业务标识符——真实客户 ID 在它眼里只是十位数字。
`scripts/check_identifiers.py` 用两条规则补这个缺口：

- **黑名单**：`.private-values` 里的值一旦出现就失败。精确，但只能抓到你想得起来写下的值。
- **白名单**：所有 8 位以上数字、分组 ID、邮箱都必须在 `.identifier-allowlist.txt` 里。
  **这条才是抓住"你根本没意识到它是真值"的那一层。**

往白名单加一行是刻意设计成需要评审的动作——那一行正是有人该问"这个值是真的吗"的地方。
只有明显是假的值才能进白名单；来自真实账号的数字应该替换掉，而不是加进白名单。

## API 兼容性

`0.1.0` 默认使用 Google Ads API `v25` 和官方 Python 客户端 `31.x`。运行
`gads --version` 可以看到当前环境安装的全部 API schema。Google Ads 版本有固定下线时间，
请持续更新 CLI 和 lock 文件。

## 开发

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=google_ads_cli --cov-fail-under=55
git ls-files -z | xargs -0 uv run detect-secrets-hook --baseline .secrets.baseline
uv build
```

测试只使用本地 protobuf schema 和 fixture。需要真实账号的 `--validate-only` 或
`--execute` 检查不会在 CI 中运行。

主代码位于 `src/google_ads_cli/`，CLI 测试位于 `tests/`，通用示例位于 `examples/`，
Codex skill 位于 `skills/google-ads/`。

提交贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 和
[CHANGELOG.md](CHANGELOG.md)。

## 开源协议

本项目使用 [Apache License 2.0](LICENSE)。
