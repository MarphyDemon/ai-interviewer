# 迭代方案：具身智能体默认凭证 DB 化

> 版本：v1.0 | 日期：2026-09-20 | 状态：已评审，进入实现

## 一、背景与问题

平台内同时存在"默认的"与"可配置的"两套具身智能体（数字人）配置：

| | 位置 | 能否热改 |
| --- | --- | --- |
| 默认 | `.env`：`AVATAR_APP_ID` / `AVATAR_APP_SECRET` / `AVATAR_GATEWAY_SERVER` / `AVATAR_DEFAULT_IMAGE` | ❌ 进程启动读一次，改完必须重启后端容器 |
| 可配置 | 数据库表 `avatarproviderconfig` | ✅ 实时查库 |

具身交互智能体服务不太稳定，上一版凭证可能随时失效，需要频繁更换。而"默认"却锁死在 `.env` 里，改一次要走"改服务器文件 → 重启容器"的运维流程，无法快速止损。

现状痛点：

1. **默认无法热改**：`.env` 由 `server/config.py` 的模块级单例 `settings` 承载，import 时构造一次，运行期不重读。
2. **数据库里的配置无法成为默认**：`AvatarProviderConfig` 没有 `is_default` 字段，只有 `is_active`，而 `is_active` 的语义是"首页展示"，且**非互斥**（对比 LLM 配置是互斥的）。
3. **用户端解析只有两级**：用户偏好 → `.env` 兜底，中间没有"数据库默认"这一层。
4. **删除接口不安全**：`DELETE /api/admin/avatar-config/{id}` 只删行，不清理引用。Postgres 下被 `user.preferred_avatar_config_id` 引用会直接 500，SQLite 下留下悬空引用（首页无任何选中项）。

## 二、目标

1. 默认凭证可在管理后台**热改，秒级生效，无需重启容器**
2. **删除 `.env` 中的默认凭证配置**，默认改为**自动从数据库选出**
3. 不做 `.env` 兜底：数据库没有可用配置时，前端**直接降级本地 Lottie 形象**
4. 删除配置不产生悬空引用、不返回 500

## 三、设计

### 3.1 默认的选取规则

默认不再来自 `.env`，而是每次请求实时从数据库选出，按优先级取第一条：

| 优先级 | 条件 | 说明 |
| --- | --- | --- |
| 1 | `is_default = True` | 管理员显式指定（互斥，全表唯一） |
| 2 | `is_active = True` | 自动选择：启用中最新创建的一条 |
| 3 | 任意记录 | 兜底：全表最新创建的一条 |
| 4 | 空 | 无默认 → 前端降级 Lottie |

优先级 1 保留人工覆盖能力，避免自动选择的随机性；优先级 2/3 即"自动从数据库内选择一个作为默认"。

### 3.2 运行时解析顺序

```
用户偏好（记录仍存在） → 数据库默认（3.1 的规则） → 无 → 本地 Lottie
```

`.env` 彻底退出运行时解析。

### 3.3 `.env` 现有凭证的处置：一次性搬迁

为避免切换过程中线上掉到 Lottie，`init_db()` 增加一次性 seed：

- 触发条件：`data/.avatar_env_seeded` 标记文件不存在（即**首次初始化**），且 `AVATAR_APP_ID` / `AVATAR_APP_SECRET` 环境变量存在，且表中**一条配置都没有**
- 动作：落库一条 `name="默认具身交互智能体"`、`is_default=True`、`is_active=True` 的记录，然后写下标记文件
- 之后 `.env` 中的这四个变量不再被任何代码读取，可从服务器 `.env` 中删除

> 这是**搬迁**，不是运行时兜底。用标记文件而非"表为空"判断，是为了避免管理员在后台**主动删光配置**（降级 Lottie）后，重启又把 `.env` 里的旧凭证复活。

### 3.4 管理端接口

| 接口 | 说明 |
| --- | --- |
| `POST /api/admin/avatar-config/{id}/set-default` | 设为默认：事务内先清全表 `is_default` 再置本条，并同时 `is_active=True` |
| `POST /api/admin/avatar-config/{id}/unset-default` | 取消默认：此后按 3.1 的规则 2/3 自动选择，或无可选则降级 Lottie |
| `DELETE /api/admin/avatar-config/{id}` | 删除前把引用它的 `user.preferred_avatar_config_id` 置 NULL，返回清理条数 |
| `GET /api/admin/avatar-config` | 返回值增加 `isDefault` |

### 3.5 首页形象列表

- 去掉写死的 `id=None`「默认具身交互智能体」synthetic 项
- 列表 = `is_active=True` 的记录；若解析出的默认不在其中，也一并带上（标 `isDefault`），避免"当前默认不可见"
- `isSelected`：偏好命中；或偏好为空且该项为默认

## 四、改动清单

### 后端

| 文件 | 改动 |
| --- | --- |
| `server/models/__init__.py` | `AvatarProviderConfig` 增 `is_default: bool = False` |
| `server/database.py` | 双库迁移各补一列；新增 `_seed_avatar_config_from_env()` 并在 `init_db()` 中调用 |
| `server/services/avatar_config_service.py` | 新增：`resolve_default_avatar_config` / `resolve_avatar_config_for_user` / `avatar_config_payload` |
| `server/routers/avatar.py` | `/config` 改用新服务并去掉 `.env` 兜底；`/homepage-avatars` 去 synthetic 项 |
| `server/routers/admin.py` | 新增 `set-default` / `unset-default`；`DELETE` 清理用户偏好；列表返回 `isDefault` |
| `server/main.py` | `avatarConfigured` 改为"数据库中是否存在可用配置" |
| `server/routers/settings.py` | `PUT /personal` 写偏好时校验配置存在性；显式传 `null` 表示清空偏好、回退默认 |
| `server/config.py` | `avatar_app_id` / `avatar_app_secret` / `avatar_gateway_server` / `avatar_default_image` 标记为废弃，仅作搬迁输入；**保留** `avatar_proxy_base_url`（brain 代理地址，与凭证无关） |

### 前端

| 文件 | 改动 |
| --- | --- |
| `src/api/admin.ts` | `AvatarProviderConfigItem` 增 `isDefault`；新增 `setDefaultAvatarConfig` / `unsetDefaultAvatarConfig` |
| `src/components/admin/AdminAvatarConfig.vue` | 列表加「默认」徽标与「设为默认 / 取消默认」按钮；删除确认提示将清空 N 个用户偏好 |
| `src/providers/digitalAvatarProvider.ts` | 配置缺失时直接抛错，交由 `useAvatar` 降级 Lottie（不做无意义的 SDK 初始化） |
| `src/i18n/locales/{zh,en}.ts` | 新增默认相关文案 |

### 配置与文档清理

`.env.example`、`server/.env.example`、`docker-compose.yml`、`docker-compose.local-llm.yml`、`README.md`、`docs/技术方案.md` 中删除 `AVATAR_APP_ID` / `AVATAR_APP_SECRET` / `AVATAR_GATEWAY_SERVER` / `AVATAR_DEFAULT_IMAGE` 的描述；`AVATAR_PROXY_BASE_URL` 保持。

## 五、上线顺序

1. 部署本次版本（含一次性搬迁 seed）
2. 管理后台确认默认记录存在、可编辑、可设为/取消默认；面试链路能正常拉起数字人
3. 清理服务器 `server/.env` 中的四个 `AVATAR_*` 变量并重启（此时已无引用）

> 搬迁标记落在 `data/.avatar_env_seeded`（`data/` 已挂载持久化卷），只跑一次；此后即便删光配置，重启也不会再用 `.env` 复活凭证。

若跳过第 1 步的搬迁，则必须**先**在后台建好可用配置，**再**部署删除 `.env` 的版本，否则中间存在 Lottie 降级窗口。

## 六、验收标准

1. `set-default` 互斥：设 A 为默认后，原默认 B 的 `is_default` 自动为 False
2. `unset-default` / 删除记录后：`GET /api/avatar/config` 返回未配置，前端降级 Lottie，无 500、无悬空偏好
3. 修改 `gatewayServer` 或凭证后**不重启**服务，新会话立即使用新值
4. `ruff` + `pytest` + 冒烟脚本 + `vue-tsc` + `eslint` + `build` 全绿

## 七、本次不做

- `src/providers/digitalAvatarProvider.ts` 中硬编码的 ASR `access_token` / `app_id`（独立安全问题，另行排期）
- `Avatar`、`InterviewTemplate` 两张无人引用的模型
- 首页"多条并列展示"（`is_active`）机制保持不变
- 自动健康探测与自动切换（本次仅提供人工「设为默认」与验证能力）
