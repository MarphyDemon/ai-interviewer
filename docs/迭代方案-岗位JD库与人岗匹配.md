# 迭代方案：岗位 JD 库 + 人岗匹配

## 背景
现有面试基于通用 `position` 枚举（frontend/backend/...）出题与评估，报告里的 `jobFit` 和简历 `positionMatch` 都对照通用岗位，无法针对具体岗位要求做精确匹配。本次新增「岗位 JD 库」，让面试官按具体 JD 出题追问，报告按 JD 逐条评估人岗匹配度。

## 决策（已确认）
1. JD 同时影响「实时出题」和「最终报告匹配」。
2. JD 输入：多行文本框粘贴 + 文件上传（PDF / Markdown / Word）。
3. JD 持久化：独立可复用 JD 库（新表 + CRUD + 管理界面）。
4. 报告产出：匹配总分(0-100) + 逐条要求拆解(✓满足/◐部分/✗不足 + 证据) + 总评文本。
5. position 保留用于 RAG 知识检索；JD 只进出题+报告 prompt，不改动检索层。
6. JD 管理界面放 `/setup`（与简历一致），面试时可选选用；JD 为可选项，无 JD 时退回现有通用 jobFit 行为。

## 数据模型
### 新增 `JobDescription`
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| user_id | str | 归属用户 |
| title | str | JD 名称（用户命名，便于列表识别） |
| content | Text | JD 正文 |
| position | str? | 可选岗位标签（用于归类，不强制） |
| created_at / updated_at | datetime | |

### Interview 改造
- 新增 `jd_id`（nullable FK → JobDescription）

### Report 改造
- 新增 `match_score`（int, nullable）：0-100 人岗匹配总分
- 新增 `match_breakdown`（JSON/Text, nullable）：逐条要求拆解 `[{requirement, status, evidence}]`
- 保留现有 `job_fit`：用作总评文本

## 后端
- `server/routers/jd.py`：
  - `GET /api/jd` 列表
  - `POST /api/jd` 粘贴创建（title + content）
  - `POST /api/jd/upload` 文件上传（pdf/md/word → 解析 → 创建）
  - `DELETE /api/jd/{id}`
- `server/services/jd_service.py`：文件解析，复用 `pdf_service`（PDF）+ `resume_service.parse_resume_file`（DOCX）+ 新增 .md 纯文本读取
- `interview_service.start_interview`：按 `jd_id` 载入 JD 文本（截断 ~3000 字），传入系统提示词
- `_build_system_prompt`：加 JD 段——"目标岗位 JD：…" + 指示面试官针对 JD 要求追问
- `generate_report`：有 JD 时改用结构化匹配 prompt，产出 `{matchScore, matchBreakdown, jobFit}`；无 JD 退回原逻辑
- `main.py` 注册 jd router

## 前端
- `src/api/jd.ts` + `src/stores/jd.ts`：CRUD + 上传
- `src/types.ts`：`JobDescription` 类型；`InterviewStartPayload` 加 `jdId`；`Report` 加 `matchScore / matchBreakdown`
- `InterviewSetupView.vue`：JD 管理区（粘贴文本框 + 文件上传）+ JD 选择下拉（可选），`start` 传 `jdId`
- `ReportView.vue`：有 JD 时渲染结构化匹配（总分 + 逐条要求表格 + 证据 + 总评）
- i18n 补 JD 相关文案

## 风险与对策
1. JD 过长 → prompt 内截断到 ~3000 字。
2. LLM 抽取 JD 要求不准 → prompt 要求"逐条对应 JD 明确列出的要求"。
3. 报告 schema 变更 → ReportView 判空兼容旧报告。
4. DB 迁移 → SQLite ALTER TABLE ADD COLUMN（nullable），现有行不受影响。

## 实施顺序
1. 后端 JD 库：模型 + router + service（CRUD + 上传解析）
2. 后端出题接入 JD：Interview.jd_id + 系统提示词加 JD 段
3. 后端报告结构化匹配：Report 字段 + generate_report 产出 matchScore/breakdown
4. 前端 JD 管理 + 选择：setup 页 JD 区 + 传 jdId
5. 前端报告渲染：结构化匹配展示
