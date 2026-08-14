# 变更日志

## v2.0 (2026-08-14) · 二期完成

### P1 · 体验增强与陪练完善

| 需求项 | 文件变更 | 说明 |
|-------|----------|------|
| 数字人陪练增加语音输入 | ✅ 已完成（P1 开始时即就绪） | ChatView 已集成麦克风 + ASR |
| 增加全屏功能 | [ChatView.vue](src/views/ChatView.vue#L261-L279) | 全屏按钮 + Fullscreen API 实现 |
| 面试增加摄像头视频 | [InterviewView.vue](src/views/InterviewView.vue#L125-L160) | PiP 小窗 + 设备调试 + 前置摄像头预览 |
| 简历独立评分报告 | [ResumeReportView.vue](src/views/ResumeReportView.vue) + [report.py](server/routers/report.py) | 独立页面 `/resume/:id/report`，前端 PDF 导出 |
| 分享面试报告链接 | [SharedReportView.vue](src/views/SharedReportView.vue) + [share.ts](src/api/share.ts) + [report.py](server/routers/report.py#L86-L165) | 生成分享 token + 公开只读路由 `/share/:token` |
| 岗位方向增加测试/测试开发 | [InterviewSetupView.vue](src/views/InterviewSetupView.vue) | FALLBACK_POSITIONS 数组扩展 |

### P2 · 用户体系与配置化

| 需求项 | 文件变更 | 说明 |
|-------|----------|------|
| 用户登录注册体系 | [auth.py](server/routers/auth.py), [auth_service.py](server/services/auth_service.py), [LoginView.vue](src/views/LoginView.vue), [RegisterView.vue](src/views/RegisterView.vue), [user.ts](src/stores/user.ts) | PBKDF2 密码哈希 + HMAC 令牌 + 用户隔离 |
| LLM 管理页配置多套 ASR/TTS | [AvatarProviderConfig](server/models/__init__.py#L126-L145), [avatar.py](server/routers/avatar.py), [AdminView.vue](src/views/AdminView.vue) | 镜像 LLMConfig 模式，CRUD 管理 |
| 多套数字人形象选择 | [Avatar](server/models/__init__.py#L148-L163), [HomeView.vue](src/views/HomeView.vue) | Avatar 表种子预置 2 个形象，用户可选择偏好 |

### P3 · 代码与算法能力

| 需求项 | 文件变更 | 说明 |
|-------|----------|------|
| 代码/算法练习模块 | [CodePracticeView.vue](src/views/CodePracticeView.vue), [algorithm.ts](src/api/algorithm.ts), [judge_service.py](server/services/judge_service.py), [code.py](server/routers/code.py), [AlgorithmProblem](server/models/__init__.py#L147-L160), [CodeSubmission](server/models/__init__.py#L163-L176) | Monaco 编辑器 + Judge0 CE 判题 + 8 语言支持 |
| 面试增加算法题 | [interview.py](server/routers/interview.py#L139-L219), [InterviewView.vue](src/views/InterviewView.vue#L324-L377) | 面试中 `algorithm` action，内嵌代码编辑器面板 |

### P4 · 基建升级与回放

| 需求项 | 文件变更 | 说明 |
|-------|----------|------|
| PostgreSQL 配置与迁移 | [config.py](server/config.py), [requirements.txt](server/requirements.txt), [migrate_to_pg.py](server/scripts/migrate_to_pg.py) | `psycopg2-binary` 依赖，环境变量配置，迁移脚本 |
| 文件存储抽象层 | [storage_service.py](server/services/storage_service.py), [files.py](server/routers/files.py), [resume.py](server/routers/resume.py) | LocalStorage + S3Storage 双后端，自动切换 |
| 媒体录制模块 | [useMediaRecorder.ts](src/composables/useMediaRecorder.ts), [recordings.ts](src/api/recordings.ts), [Recording](server/models/__init__.py), [recordings.py](server/routers/recordings.py) | MediaRecorder 封装 composable + 后端存储 |
| 面试添加录制开关 | [InterviewView.vue](src/views/InterviewView.vue#L400-L408) | 导航栏新增录制按钮，面试结束自动 flush 上传 |
| 回放页面与历史入口 | [RecordingPlaybackView.vue](src/views/RecordingPlaybackView.vue), [HistoryView.vue](src/views/HistoryView.vue), [router/index.ts](src/router/index.ts) | 每条面试记录新增「回放」按钮 |

### 新增文件清单

```
server/
  services/
    auth_service.py          # 认证服务：密码哈希、令牌生成、当前用户获取
    storage_service.py      # 文件存储抽象层：本地/S3 兼容
  scripts/
    migrate_to_pg.py         # SQLite → PostgreSQL 迁移脚本
  routers/
    auth.py                 # 注册/登录/我的接口
    code.py                 # 算法题/判题接口
    recordings.py           # 录制上传/播放接口
    files.py                # 本地文件服务路由
  models/
    # 新增 6 个模型：User 扩展、AvatarProviderConfig、Avatar、AlgorithmProblem、CodeSubmission、Recording
src/
  api/
    recordings.ts           # 录制 API
    share.ts                # 分享 API
    algorithm.ts            # 算法题 API
  composables/
    useMediaRecorder.ts     # MediaRecorder 封装
  views/
    LoginView.vue           # 登录页
    RegisterView.vue        # 注册页
    CodePracticeView.vue   # 算法练习页
    RecordingPlaybackView.vue  # 回放页
    SharedReportView.vue   # 分享报告页
  stores/
    user.ts                 # Pinia 用户状态存储
```

## v1.0 (2026-08-11) · MVP 完成

初始 MVP 版本，包含核心功能：
- 题库管理（Markdown 上传 + RAG 检索）
- 简历解析 + 轻量分析
- 数字人面试流程 + 状态机
- 点评报告 + PDF 导出 + 历史记录
- LLM 管理页（口令保护）
- 桌面 + 移动端响应式