#! encoding=utf-8
"""企业侧闭环 HTTP 冒烟测试（临时脚本，运行后删除）。

流程：HR 注册 → 建组织 → 发邀请 → 候选人免注册进入 → 作答 → 结束出报告
      → HR 看排名与报告 → 外部用户访问被拒 → 撤销邀请后链接失效
用 OFFLINE_MODE=true 跑，不调用任何外部模型。
"""
import os
import sys
import tempfile
import uuid

# 必须在导入 server.main 之前设置：走离线规则模式 + 临时 SQLite，
# 不依赖外部模型，也不碰本地/线上的真实数据库。
os.environ["OFFLINE_MODE"] = "true"
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="ai-interviewer-smoke-"), "app.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session as DbSession  # noqa: E402

from server.database import engine, init_db  # noqa: E402
from server.main import app  # noqa: E402
from server.models import Interview, KnowledgeDoc  # noqa: E402
from server.services import org_service  # noqa: E402
from server.services.interview_brain_service import build_interviewer_prompt  # noqa: E402

# TestClient 不在 with 语句里不会触发 startup 事件，这里显式建表
init_db()

client = TestClient(app)
suffix = uuid.uuid4().hex[:6]
failures = []


def check(label, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        failures.append(label)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# 1. HR 注册并开通组织
hr = client.post("/api/auth/register", json={"username": f"hr_{suffix}", "password": "pass12345"})
check("HR 注册", hr.status_code == 200, str(hr.status_code))
hr_token = hr.json()["token"]

org = client.get("/api/org/me", headers=auth(hr_token))
check("组织自助开通", org.status_code == 200, str(org.status_code))
org_body = org.json()
check("开通后角色为 owner", org_body.get("role") == "owner", str(org_body.get("role")))
check("可管理组织", org_body.get("canManage") is True)

# 1b. 企业招聘身份注册：注册时传 orgName，直接建组织并成为 owner
ent = client.post(
    "/api/auth/register",
    json={"username": f"ent_{suffix}", "password": "pass12345", "orgName": f"{suffix} 科技"},
)
check("企业身份注册", ent.status_code == 200, ent.text[:200])
ent_body = ent.json()
check(
    "企业注册返回 orgRole=owner",
    ent_body["user"].get("orgRole") == "owner",
    str(ent_body["user"].get("orgRole")),
)
ent_token = ent_body["token"]
ent_org = client.get("/api/org/me", headers=auth(ent_token))
check(
    "企业注册即开通组织",
    ent_org.status_code == 200 and ent_org.json()["name"] == f"{suffix} 科技",
    ent_org.text[:200],
)
check("企业注册者可直接管理组织", ent_org.json().get("canManage") is True)

# 1c. 个人身份注册：不建组织（orgRole 为空）
solo = client.post("/api/auth/register", json={"username": f"solo_{suffix}", "password": "pass12345"})
check("个人注册 orgRole 为空", solo.json()["user"].get("orgRole") is None, str(solo.json()["user"].get("orgRole")))

# 1d. /auth/me 返回 plan / orgRole，供前端路由守卫判定企业身份
me_ent = client.get("/api/auth/me", headers=auth(ent_token))
check(
    "me 返回 plan 与 orgRole",
    me_ent.json().get("plan") == "free" and me_ent.json().get("orgRole") == "owner",
    me_ent.text[:200],
)

# 2. 创建候选人邀请
inv = client.post(
    "/api/org/invites",
    headers=auth(hr_token),
    json={"position": "后端", "difficulty": "mid", "duration": 30, "note": "一面"},
)
check("创建邀请", inv.status_code == 200, inv.text[:200])
invite = inv.json()
token = invite["token"]
check("返回候选人路径", invite["path"] == f"/invite/{token}")

# 3. 候选人（未登录）读取邀请信息
anon = client.get(f"/api/invite/{token}")
check("匿名读邀请信息", anon.status_code == 200, anon.text[:200])
check("邀请信息含岗位与公司", anon.json().get("position") == "后端" and bool(anon.json().get("orgName")))

# 4. 候选人填姓名开始面试（免注册）
start = client.post(f"/api/invite/{token}/start", json={"name": "张三", "email": "z@example.com"})
check("候选人免注册开始面试", start.status_code == 200, start.text[:300])
start_body = start.json()
cand_token = start_body["token"]
interview_id = start_body["interviewId"]
check("返回候选人 token", bool(cand_token))
check("返回 config 供倒计时", start_body.get("config", {}).get("position") == "后端")
check("返回首题", bool(start_body.get("firstQuestion", {}).get("content")))

# 5. 候选人不占用用户名，且无法用密码登录
me = client.get("/api/auth/me", headers=auth(cand_token))
check("候选人 /me 可用", me.status_code == 200 and me.json().get("role") == "candidate", me.text[:200])
login = client.post("/api/auth/login", json={"username": "", "password": ""})
check("候选人无法登录（无用户名/密码）", login.status_code in (401, 422), str(login.status_code))

# 6. 候选人作答
ans = client.post(
    f"/api/interview/{interview_id}/answer",
    headers=auth(cand_token),
    json={"answer": "我负责过订单系统的重构，用 Redis 做主缓存，QPS 从 800 提升到 4000。"},
)
check("候选人作答", ans.status_code == 200, ans.text[:300])

# 7. 结束面试 → 生成报告
end = client.post(f"/api/interview/{interview_id}/end", headers=auth(cand_token))
check("结束面试并出报告", end.status_code == 200, end.text[:300])

# 8. HR 查看候选人排名
rank = client.get("/api/org/candidates", headers=auth(hr_token))
check("HR 查看排名", rank.status_code == 200, rank.text[:300])
rows = rank.json()
check("排名含候选人张三", len(rows) == 1 and rows[0]["name"] == "张三", str(rows)[:300])

# 9. HR 可读候选人报告；外部用户被拒
rep_hr = client.get(f"/api/report/{interview_id}", headers=auth(hr_token))
check("HR 可读候选人报告", rep_hr.status_code == 200, rep_hr.text[:200])

outer = client.post("/api/auth/register", json={"username": f"out_{suffix}", "password": "pass12345"})
outer_token = outer.json()["token"]
rep_out = client.get(f"/api/report/{interview_id}", headers=auth(outer_token))
check("外部用户读报告被拒(404)", rep_out.status_code == 404, str(rep_out.status_code))
det_out = client.get(f"/api/interview/{interview_id}", headers=auth(outer_token))
check("外部用户读面试详情被拒(404)", det_out.status_code == 404, str(det_out.status_code))
det_hr = client.get(f"/api/interview/{interview_id}", headers=auth(hr_token))
check("HR 可读面试详情", det_hr.status_code == 200, str(det_hr.status_code))

# 10. 撤销邀请后链接失效
rev = client.delete(f"/api/org/invites/{invite['id']}", headers=auth(hr_token))
check("撤销邀请", rev.status_code == 200, rev.text[:200])
after = client.get(f"/api/invite/{token}")
check("撤销后 info.active=False", after.status_code == 200 and after.json()["active"] is False)
retry = client.post(f"/api/invite/{token}/start", json={"name": "李四"})
check("撤销后不能再开始(410)", retry.status_code == 410, str(retry.status_code))

# ---------- 11. 企业侧：岗位 JD 组织化 ----------
hr_uid = client.get("/api/auth/me", headers=auth(hr_token)).json()["id"]
hr_org_id = org_body["id"]

jd = client.post(
    "/api/jd",
    headers=auth(hr_token),
    data={
        "title": f"{suffix} 后端 JD",
        "content": "负责订单系统设计，要求熟悉高并发与分布式",
        "position": "后端",
        "scope": "org",
    },
)
check("创建组织共享 JD", jd.status_code == 200, jd.text[:200])
jd_id = jd.json()["id"]
check("组织 JD 带 orgId", jd.json().get("orgId") == hr_org_id, str(jd.json().get("orgId")))

jd_personal = client.post(
    "/api/jd",
    headers=auth(hr_token),
    data={"title": f"{suffix} 私有 JD", "content": "私有内容", "scope": "personal"},
)
check(
    "个人 JD 不带 orgId",
    jd_personal.status_code == 200 and jd_personal.json().get("orgId") is None,
    jd_personal.text[:200],
)

# 个人用户加入组织（hr 角色）后可见组织 JD
client.post(
    "/api/auth/register", json={"username": f"mate_{suffix}", "password": "pass12345"}
)
mate_login = client.post(
    "/api/auth/login", json={"username": f"mate_{suffix}", "password": "pass12345"}
)
mate_token = mate_login.json()["token"]
addm = client.post(
    "/api/org/members", headers=auth(hr_token), json={"username": f"mate_{suffix}", "role": "hr"}
)
check("同事加入组织", addm.status_code == 200, addm.text[:200])
mate_jds = client.get("/api/jd", headers=auth(mate_token)).json()
check("同组织成员可见共享 JD", any(j["id"] == jd_id for j in mate_jds), str(mate_jds)[:200])

out_jds = client.get("/api/jd", headers=auth(outer_token)).json()
check("组织外用户看不到共享 JD", all(j["id"] != jd_id for j in out_jds), str(out_jds)[:200])
check(
    "组织外用户读共享 JD 被拒(404)",
    client.get(f"/api/jd/{jd_id}", headers=auth(outer_token)).status_code == 404,
)

# viewer 只读：不能创建组织共享 JD
client.post(
    "/api/auth/register", json={"username": f"view_{suffix}", "password": "pass12345"}
)
viewer_token = client.post(
    "/api/auth/login", json={"username": f"view_{suffix}", "password": "pass12345"}
).json()["token"]
client.post(
    "/api/org/members", headers=auth(hr_token), json={"username": f"view_{suffix}", "role": "viewer"}
)
deny_jd = client.post(
    "/api/jd",
    headers=auth(viewer_token),
    data={"title": "x", "content": "y", "scope": "org"},
)
check("viewer 建组织 JD 被拒(403)", deny_jd.status_code == 403, str(deny_jd.status_code))
deny_jd_view = client.get(f"/api/jd/{jd_id}", headers=auth(viewer_token))
check("viewer 可读组织 JD", deny_jd_view.status_code == 200, str(deny_jd_view.status_code))

# ---------- 12. 企业知识库归属与 RAG 隔离 ----------
# 直接落库，避免触发 embedding 外部调用（本段只验证归属与检索过滤逻辑）
with DbSession(engine) as s:
    org_doc = KnowledgeDoc(
        user_id=hr_uid,
        org_id=hr_org_id,
        filename=f"{suffix}-企业题库.md",
        content="# 订单系统\n\n- Redis 缓存热点数据",
        status="ready",
    )
    s.add(org_doc)
    s.commit()
    s.refresh(org_doc)
    org_doc_id = org_doc.id
    private_doc = KnowledgeDoc(
        user_id=hr_uid,
        org_id=None,
        filename=f"{suffix}-私有题库.md",
        content="# 私有\n\n仅本人可见",
        status="ready",
    )
    s.add(private_doc)
    s.commit()
    s.refresh(private_doc)
    private_doc_id = private_doc.id

hr_docs = client.get("/api/knowledge", headers=auth(hr_token)).json()
org_row = next((d for d in hr_docs if d["id"] == org_doc_id), None)
check("企业文档标注 scope=org", bool(org_row) and org_row.get("scope") == "org", str(org_row))
check("同组织成员可见企业知识库", any(d["id"] == org_doc_id for d in client.get("/api/knowledge", headers=auth(mate_token)).json()))
check("组织外用户看不到企业知识库", all(d["id"] != org_doc_id for d in client.get("/api/knowledge", headers=auth(outer_token)).json()))

deny_kb = client.post(
    "/api/knowledge/upload",
    headers=auth(viewer_token),
    files=[("files", ("x.md", "# x", "text/markdown"))],
    data={"scope": "org"},
)
check("viewer 上传企业知识库被拒(403)", deny_kb.status_code == 403, str(deny_kb.status_code))

out_uid = client.get("/api/auth/me", headers=auth(outer_token)).json()["id"]
with DbSession(engine) as s:
    allowed_hr = org_service.visible_knowledge_doc_ids(s, hr_uid, hr_org_id)
    allowed_out = org_service.visible_knowledge_doc_ids(s, out_uid, None)

check("本人可见集含自己的企业/私有文档", org_doc_id in allowed_hr and private_doc_id in allowed_hr)
check("组织外用户的可见集不含 HR 的文档", org_doc_id not in allowed_out and private_doc_id not in allowed_out)

chunks = [{"metadata": {"doc_id": org_doc_id}}, {"metadata": {"doc_id": 999999}}]
check(
    "检索结果按文档归属过滤（不串检）",
    org_service.filter_visible_chunks(chunks, allowed_out) == [],
)
check("本组织可见时保留命中片段", len(org_service.filter_visible_chunks(chunks, allowed_hr)) == 1)

# ---------- 13. 邀请考察重点 ----------
focus_text = "重点考察分布式与高并发，追问项目中的技术选型取舍"
inv2 = client.post(
    "/api/org/invites",
    headers=auth(hr_token),
    json={"position": "后端", "focus": focus_text},
)
check("创建带考察重点的邀请", inv2.status_code == 200, inv2.text[:200])
inv2_id = inv2.json()["id"]
inv2_token = inv2.json()["token"]
row2 = next((i for i in client.get("/api/org/invites", headers=auth(hr_token)).json() if i["id"] == inv2_id), None)
check("邀请列表回传考察重点", bool(row2) and row2.get("focus") == focus_text, str(row2))

anon2 = client.get(f"/api/invite/{inv2_token}")
check("候选人入口仍不泄露考察重点", "focus" not in anon2.json(), str(anon2.json())[:200])

start2 = client.post(f"/api/invite/{inv2_token}/start", json={"name": "王五"})
check("带考察重点的邀请可开始面试", start2.status_code == 200, start2.text[:200])
interview_id2 = start2.json()["interviewId"]
with DbSession(engine) as s:
    interview2 = s.get(Interview, interview_id2)
    check("考察重点落到面试记录", interview2.focus == focus_text, str(interview2.focus))
    prompt = build_interviewer_prompt(s, interview2)
check("面试 prompt 注入考察重点", focus_text in prompt, prompt[-400:])

print()
if failures:
    print(f"失败 {len(failures)} 项：{failures}")
    sys.exit(1)
print("全部冒烟项通过")
