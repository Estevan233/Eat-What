# T05 Design — 用户档案模型与编辑页

## 1. 边界

本任务只交付「用户档案的 CRUD 与编辑页」，不涉及：
- 体质测试（`constitution_type` 字段留空，T06 实现）
- 星座计算（`zodiac_sign` 字段在 `ProfileRead` 里占位返回 `null`，T08 实现）
- 昵称编辑接口（PRD 明确留给将来；profile 页只读展示 store 的 nickname）

## 2. 数据模型

### 2.1 UserProfile 表（1:1 与 User）

```python
# app/models/user_profile.py
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    # 外键 + 主键：1:1 关系靠「user_id 既是外键又是主键」实现
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    birthday: str = Field(max_length=10)            # ISO YYYY-MM-DD 字符串
    gender: str = Field(max_length=8)               # 'male'|'female'|'other'
    height_cm: Optional[int] = Field(default=None)
    weight_kg: Optional[float] = Field(default=None)
    forbidden_tags: list[str] = Field(default=[], sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

**为什么 1:1 用 user_id 当主键**：单字段既是外键又是主键，DB 层强制 1:1（一个 user 只能有一行 profile），不需要额外唯一约束，最简洁。

**为什么 forbidden_tags 用 JSON 列**：MVP 阶段不需要按 tag 反查（如「查所有忌海鲜的人」），只读写整个 list。JSON 列够用，关联表过度设计。

**为什么 birthday 用 str 不用 Date**：PRD 明确「避免时区问题」。SQLite 的 Date 适配器在不同 driver 下行为有差异，字符串最稳。

### 2.2 模型注册

`app/models/__init__.py` 加一行 import，让 `init_db()` 能看到 UserProfile：

```python
from app.models.user import User
from app.models.user_profile import UserProfile

__all__ = ["User", "UserProfile"]
```

## 3. 后端 API 契约

### 3.1 schemas `app/schemas/profile.py`

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

Gender = Literal["male", "female", "other"]


class ProfileUpsert(BaseModel):
    """PUT /profile 请求体。"""
    birthday: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    gender: Gender
    height_cm: int | None = Field(default=None, ge=80, le=250)
    weight_kg: float | None = Field(default=None, ge=30, le=300)
    forbidden_tags: list[str] = Field(default_factory=list)


class ProfileRead(BaseModel):
    """GET /profile 返回的 profile 部分。"""
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    birthday: str
    gender: str
    height_cm: int | None = None
    weight_kg: float | None = None
    forbidden_tags: list[str] = []
    zodiac_sign: str | None = None   # 占位，T08 计算
    updated_at: datetime


class UserRead(BaseModel):
    """扩展版 UserRead，合并 profile 字段。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    avatar_url: str | None = None
    profile: ProfileRead | None = None
```

**注意：**
- `UserRead` 在 `schemas/auth.py` 已有同名定义（id/nickname/avatar_url），本任务**重写** `schemas/profile.py` 里的 `UserRead` 包含 `profile` 字段。为避免冲突，`schemas/auth.py` 的 `UserRead` 改名为 `AuthUserRead`（仅登录响应用），`schemas/profile.py` 的 `UserRead` 是档案场景的「user + profile」组合。
- `zodiac_sign` 在 `ProfileRead` 里永远是 `None`（直到 T08），用 `@model_validator` 或 `from_orm` 钩子都不必，service 层直接构造时填 `None`。

### 3.2 service `app/services/profile_service.py`

```python
def get_profile(session, user_id) -> ProfileRead | None
def upsert_profile(session, user_id, data: ProfileUpsert) -> ProfileRead
```

- `get_profile`：`SELECT * FROM user_profiles WHERE user_id=?`，找不到返回 None。
- `upsert_profile`：
  1. 找现有记录
  2. 找到 → 更新所有字段（包括 forbidden_tags 整体覆盖）
  3. 找不到 → `UserProfile(user_id=..., ...)` 新建
  4. commit + refresh
  5. 构造 `ProfileRead`（zodiac_sign=None）返回
- **忌口标签校验**：service 层再次校验 `forbidden_tags` 都在 `FORBIDDEN_TAGS` 常量集合内；不在就抛 `ValidationError`。Pydantic schema 校验不了「值在动态集合内」，必须 service 层做。

### 3.3 路由 `app/api/v1/profile.py`

```python
router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("", response_model=...)
def get_profile_route(user: User = Depends(get_current_user), session = Depends(get_db)) -> ...:
    profile = profile_service.get_profile(session, user.id)
    user_read = UserRead(id=user.id, nickname=user.nickname, avatar_url=user.avatar_url, profile=profile)
    return success(data=user_read.model_dump())

@router.put("", response_model=...)
def upsert_profile_route(
    body: ProfileUpsert,
    user: User = Depends(get_current_user),
    session = Depends(get_db),
) -> ...:
    profile = profile_service.upsert_profile(session, user.id, body)
    return success(data=profile.model_dump())
```

**统一响应包装**：用 `response_model=dict[str, Any]` + `success(data=...)` 返回，与 `auth.py` 一致（避免 FastAPI 的 `response_model` 二次包装）。

### 3.4 路由注册

`app/api/v1/__init__.py`：

```python
from app.api.v1.profile import router as profile_router
api_router.include_router(profile_router)
```

### 3.5 常量 `app/core/constants.py`（新建）

```python
FORBIDDEN_TAGS: tuple[str, ...] = (
    "pork", "beef", "seafood", "spicy", "raw_cold",
    "greasy", "gluten", "lactose", "nut", "diabetic_sugar",
)
FORBIDDEN_TAGS_SET = frozenset(FORBIDDEN_TAGS)
```

## 4. 前端契约

### 4.1 字段命名策略 — 前端 camelCase，后端 snake_case，request 层做转换

**决策**：前端 TS 类型用 camelCase（`avatarUrl`, `heightCm`, `weightKg`, `forbiddenTags`, `constitutionType`, `zodiacSign`, `userId`, `updatedAt`），与现有 `UserProfile` 接口一致；后端 API 用 snake_case；`request.ts` 拦截器层做双向转换。

**理由**：
1. 现有 `types/api.ts` 的 `UserProfile` 接口已是 camelCase，前端代码风格统一更易读
2. JS/TS 社区惯例是 camelCase，与微信小程序原生 API（`avatarUrl` 等）也一致
3. 后端不动 snake_case（Python PEP 8 + SQL 习惯）
4. 转换层只在 `request.ts` 一处，集中维护不扩散

**改动**：
- `request.ts` 的 `success` 分支里，对 `body.data` 调用 `snakeToCamel()` 递归转换；对入参 `opts.data` 在发请求前调 `camelToSnake()` 递归转换
- 新建 `miniapp/src/utils/case.ts`，实现 `snakeToCamel` / `camelToSnake`（含对象、数组、嵌套）
- `types/api.ts` 的 `UserProfile` 字段不动（已是 camelCase），新增 `ProfileRead` / `UserWithProfile` / `ProfileUpsert` 都用 camelCase
- 注意：现有 `UserRead`（id/nickname/avatar_url）**例外**，它是 T04 直接对后端字段的映射，本任务**不改**它，避免回归；`UserProfile`（avatarUrl 等）才是档案场景的 camelCase 主线

**注**：字段名 `id`/`token`/`nickname` 等无下划线的字段，转换函数应原样返回（不能误改）。

### 4.2 类型定义 `types/api.ts` 扩展

```ts
export interface ProfileRead {
  userId: number
  birthday: string
  gender: Gender
  heightCm?: number
  weightKg?: number
  forbiddenTags: string[]
  zodiacSign?: string | null
  updatedAt: string
}

export interface UserWithProfile {
  id: number
  nickname: string
  avatarUrl?: string
  profile: ProfileRead | null
}

export interface ProfileUpsert {
  birthday: string
  gender: Gender
  heightCm?: number
  weightKg?: number
  forbiddenTags: string[]
}
```

### 4.3 API 封装 `api/profile.ts`

```ts
import { request } from './request'
import type { ProfileRead, UserWithProfile, ProfileUpsert } from '@/types/api'

// 注意：request 层会自动 camelToSnake 入参、snakeToCamel 出参
export const getProfile = () => request<UserWithProfile>({ url: '/v1/profile' })
export const upsertProfile = (data: ProfileUpsert) =>
  request<ProfileRead>({ url: '/v1/profile', method: 'PUT', data })
```

### 4.4 user store 扩展

`stores/user.ts` 加：
- `profile: ref<ProfileRead | null>`（注意：这是档案详情，不是 `UserRead`；与现有 `profile: ref<UserRead | null>` 不同名 → 重命名现有 `profile` 为 `user`，新增 `profile` 指代档案）
  - **决策**：现有 `profile.value = data.user` 在 `login()` 里赋的是 UserRead；为避免语义混淆，本任务**保留**现有 `profile` 命名（指 UserRead），**新增** `userProfile: ref<ProfileRead | null>` 指代档案详情
  - 这样 `auth-guard`、`request.ts` 里的 `userStore.profile` 不需改
- `fetchUserProfile()`：调 `getProfile()`，存 `userProfile`
- `saveUserProfile(data)`：调 `upsertProfile(data)`，更新 `userProfile`

### 4.5 profile.vue 编辑页

- 表单字段：生日 picker / 性别 radio / 身高 input number / 体重 input number / 忌口 chip 多选
- 生日用 `<picker mode="date">`，v-model 绑 string
- 性别用 radio group，三个 option
- 身高/体重用 `<input type="number">`
- 忌口 chip 用 `forbidden_tags` 常量列表渲染，点击 toggle
- onLoad：若 store 里没 `userProfile` 就 `await fetchUserProfile()`；有则预填
- 提交：`await saveUserProfile(formData)` → 成功 toast + `uni.switchTab({ url: '/pages/today/today' })`
- 若未登录，调 `requireLogin('/pages/profile/profile')` 引导登录

### 4.6 常量同步 `constants/forbidden-tags.ts`

```ts
export const FORBIDDEN_TAGS = [
  'pork', 'beef', 'seafood', 'spicy', 'raw_cold',
  'greasy', 'gluten', 'lactose', 'nut', 'diabetic_sugar',
] as const

export type ForbiddenTag = typeof FORBIDDEN_TAGS[number]
```

注意 PRD 里把 "gluten" 拼成了 "gluten"（应为 "gluten" 实为 "gluten" 实为 "gluten" — 实际拼写为 "gluten"，正确拼写是 "gluten"）。**保持与后端常量一致**，两边都写 `gluten`（即使拼写不标准也以常量为准）。**修正**：实际拼写是 `gluten` 应为 `gluten` — 让我重新核对：PRD 写的是 `"gluten"`，这是 "gluten"（麸质）的拼写错误，正确是 `gluten`。**决策**：两边都用正确拼写 `gluten`。

## 5. 测试策略

### 5.1 后端 `tests/test_api_v1/test_profile.py`

| 测试 | 验证 |
|---|---|
| `test_get_profile_unauthenticated_returns_401` | 不带 token GET /profile → 401 |
| `test_get_profile_returns_null_when_no_profile` | 登录后 GET，profile=null |
| `test_put_profile_creates` | PUT 创建，再 GET 能拿到 |
| `test_put_profile_updates_height` | 二次 PUT 改 height，再 GET 是新值 |
| `test_put_profile_invalid_height_returns_422` | height_cm=300 → 422 |
| `test_put_profile_invalid_gender_returns_422` | gender='unknown' → 422 |
| `test_put_profile_invalid_forbidden_tag_returns_422` | forbidden_tags=['unknown'] → 422 |

测试复用 conftest 的 `client` + `session` fixture。构造登录 token 的方式：先调 `/auth/wx-login` mock 端点拿 token，再带 `Authorization: Bearer` 调 profile 端点。

### 5.2 前端

无单测（uni-app 测试基础设施未建）。靠 type-check + lint + build + 手动 E2E。

## 6. 兼容性与回归

- **User 重命名**：`schemas/auth.py` 的 `UserRead` 改名为 `AuthUserRead`；`auth.py` 路由的 `UserRead` import 改为 `AuthUserRead`；`LoginResponse.user` 类型改为 `AuthUserRead`。所有改动在 T04 已 commit 的代码内，但本任务一并改完。
- **前端 UserRead 不动**：`types/api.ts` 的 `UserRead`（id/nickname/avatar_url）保持不变；新增 `UserWithProfile` 与 `ProfileRead`。
- **DB 迁移**：开发期 `init_db()` 用 `create_all`，新表会自动建；现有 dev.db 删了重建即可。生产环境未来用 Alembic，不在本任务范围。
- **port 不一致 bug**：`miniapp/src/api/request.ts` 的 `BASE_URL = 'http://localhost:8000'` 与后端实际跑的 8765 不一致。**本任务不修**，但记录现状：
  - 后端开发实际端口：8765（`launch.json` 默认 8000，但 `tasks.json` 与本机实际启动习惯是 8765）
  - 前端 `BASE_URL`：8000（与后端不一致）
  - 影响：本任务的 E2E 脚本直接用 httpx 打 8765，不经过前端；前端开发期需手动改 `BASE_URL` 或开发者工具勾选「不校验合法域名」+ 启动后端在 8000
  - 设计逻辑清晰：转换层（camelCase↔snake_case）独立于 BASE_URL 配置；BASE_URL 是环境配置层，留给后续任务或 T08 接 OpenAPI 时统一处理

## 7. 取舍记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 1:1 关系实现 | user_id 既外键又主键 | DB 层强制唯一，最简洁 |
| forbidden_tags 存储 | JSON 列 | MVP 不需反查，关联表过度设计 |
| birthday 类型 | str (ISO) | 避时区问题，SQLite driver 行为最稳 |
| 字段命名 | 前端 camelCase + request 层转换 | 现有 UserProfile 已 camel；JS 惯例；微信原生也 camel；后端不动 snake |
| zodiac_sign | 占位返回 null | T08 实现，本任务不实现 |
| 昵称编辑 | 不在本任务 | PRD 明确留给将来 |
| UserRead 重名 | auth.py 改名 AuthUserRead | 避免与 profile 场景的 UserRead 冲突 |
| BASE_URL 修复 | 本任务不动 | 环境配置层，独立于本任务代码逻辑；E2E 脚本直接打 8765 不经过前端 |
