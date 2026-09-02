# T04 微信登录全链路

## Goal

打通微信小程序登录到后端 JWT 签发与前端持久化的全链路。完成后用户首次打开小程序可完成登录态建立，所有后续 API 调用都带 token。

## Requirements

### Backend

#### 模型 `app/models/user.py`（首次创建真实表）

```python
class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    openid: str = Field(unique=True, index=True, max_length=64)
    unionid: Optional[str] = Field(default=None, max_length=64)
    nickname: str = Field(default="微信用户", max_length=64)
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

- 档案字段（生日、性别、身高、体重、constitution_type、forbidden_tags）放扩展表 `UserProfile`，本任务**不**建，留给 T05

#### 替换 `app/core/deps.py` 中的 `get_current_user`

- 解析 JWT 拿 `sub`
- 查 `User` 表，返回真实 `User` 对象
- 找不到抛 `AuthError`

#### `app/services/wx_client.py`

- `code2session(code: str) -> dict`：调 `https://api.weixin.qq.com/sns/jscode2session`，传 `appid`/`secret`/`js_code`/`grant_type=authorization_code`
- 用 `httpx.AsyncClient(timeout=5)`
- 处理 `errcode != 0` → 抛 `AuthError`
- 返回 `{openid, session_key, unionid?}`

#### `app/schemas/auth.py`

```python
class WxLoginRequest(BaseModel):
    code: str
    nickname: Optional[str] = None
    avatarUrl: Optional[str] = None

class LoginResponse(BaseModel):
    token: str
    user: UserRead

class UserRead(BaseModel):
    id: int
    nickname: str
    avatar_url: Optional[str]
```

#### `app/api/v1/auth.py`

```python
@router.post("/wx-login", response_model=ApiResult[LoginResponse])
async def wx_login(req: WxLoginRequest, session: Session = Depends(get_db)):
    wx_data = await wx_client.code2session(req.code)
    user = user_service.upsert_by_openid(
        session,
        openid=wx_data["openid"],
        unionid=wx_data.get("unionid"),
        nickname=req.nickname,
        avatar_url=req.avatarUrl,
    )
    token = create_access_token(user.id)
    return success({"token": token, "user": UserRead.from_orm(user)})
```

- `app/api/v1/__init__.py` 聚合 router
- `app/main.py` 注册 v1 router 在 `/api/v1` 前缀

#### 测试

- `tests/test_api_v1/test_auth.py`：mock `wx_client.code2session`，测：
  - 首次登录（用户不存在）→ 创建用户、返回 token
  - 二次登录（用户存在）→ 复用、更新 nickname/avatar
  - code 无效 → 401

### Frontend

#### `src/pages/auth/auth.vue`（新增页面，不在 tabBar）

- 全屏引导：「点击登录，开启你的饮食建议」
- 一个按钮触发 `wx.login` → 拿 code → 调 `api.auth.wxLogin(code)` → 拿 token + user → 存 store → 跳回 `today`

#### `src/api/auth.ts`

```ts
import { request } from './request'
import type { LoginResponse } from '@/types/api'

export const wxLogin = (code: string) =>
  request<LoginResponse>({ url: '/auth/wx-login', method: 'POST', data: { code } })
```

#### `src/stores/user.ts` 扩展

- `login(): Promise<void>`：调用 `wxLogin` 流程并存储
- 未登录用户访问需登录页时 → `requireLogin()` 跳 `/pages/auth/auth`

#### `manifest.json` 填入真实 `appid`

#### 用户拒绝授权

- `wx.login` 几乎不失败；但 `getUserProfile` 用户拒绝 → toast 提示并保留登录态（用默认 nickname）

### 流程图

```
[小程序启动 App.vue onLaunch]
   ↓
[检查 token，无 token 时不强制登录，today 页可用]
   ↓ 用户点击需要登录的功能
[跳 /pages/auth/auth]
   ↓ 点登录按钮
[wx.login → code]
   ↓
[POST /auth/wx-login {code}]
   ↓
[backend code2session → openid → upsert user → JWT]
   ↓
[返回 {token, user}]
   ↓
[存 store + storage]
   ↓
[uni.navigateBack 或 uni.switchTab 到 today]
```

## Acceptance Criteria

- [ ] 首次打开小程序 → today 页可看（占位）→ 点「我的」tab → 跳登录页
- [ ] 登录按钮点击后成功拿到 token，回到原页面或 today
- [ ] 二次打开小程序若 token 未过期，直接到 today，无需再次登录
- [ ] token 过期后任意 API 调用 → 401 → 清 token → 引导登录页
- [ ] 后端 `pytest tests/test_api_v1/test_auth.py` 全绿
- [ ] `npm run type-check && npm run lint` 全绿

## Dependencies

- T02（FastAPI 基础设施：settings、security、deps、错误体系）
- T03（uni-app 基础设施：Pinia、request、store）

## Notes

- 微信开发者工具支持「未发布」小程序用真实 AppID 调试 `wx.login`，AppID 由开发者自备
- 如开发者暂未申请 AppID：T04 可用 `mock` 模式：前端写死 code，后端跳过 `code2session` 直接用 mock openid，但生产前必须切回
- 不实现 unionid 跨端打通（产品定位不需要）
- nickname 来源：建议用 `wx.getUserProfile`（已废弃但仍可用）或在前端让用户输入；本任务接受任一种
