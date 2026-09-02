# T05 用户档案模型与编辑页

## Goal

让用户能填写与维护自己的健康档案（生日、性别、身高、体重、忌口标签），这些字段是后续推荐算法的输入。

## Requirements

### Backend

#### 数据模型扩展

- 新建 `app/models/user_profile.py`：
  ```python
  class UserProfile(SQLModel, table=True):
      __tablename__ = "user_profiles"
      user_id: int = Field(foreign_key="users.id", primary_key=True)
      birthday: str = Field(max_length=10)            # ISO YYYY-MM-DD
      gender: str = Field(max_length=8)               # 'male'|'female'|'other'
      height_cm: Optional[int] = Field(default=None)
      weight_kg: Optional[float] = Field(default=None)
      forbidden_tags: List[str] = Field(default=[], sa_column=Column(JSON))
      updated_at: datetime = Field(default_factory=datetime.utcnow)
  ```
- User 与 UserProfile 是 1:1，通过 `user_id` 外键

#### schemas `app/schemas/profile.py`

- `ProfileUpsert`：生日必填、gender 必填枚举、height 80-250、weight 30-300
- `ProfileRead`：完整字段
- `UserWithProfile`：合并 `User` + `ProfileRead`

#### service `app/services/profile_service.py`

- `upsert_profile(session, user_id, data) -> ProfileRead`
- `get_profile(session, user_id) -> ProfileRead | None`

#### 路由 `app/api/v1/profile.py`

- `GET /profile` → 返回 `UserWithProfile`（profile 不存在时 profile=null）
- `PUT /profile` → upsert，返回更新后 `ProfileRead`
- 需 `Depends(get_current_user)`，从 user 取 user_id

#### 忌口标签预定义

- `app/core/constants.py` 新建 `FORBIDDEN_TAGS`：`["pork", "beef", "seafood", "spicy", "raw_cold", "greasy", "gluten", "lactose", "nut", "diabetic_sugar"]`
- 前端用此列表做 picker，后端只校验值在常量集合内

#### 测试

- `tests/test_api_v1/test_profile.py`：
  - 未登录 GET 401
  - 登录后 GET 返回 null profile
  - PUT 创建
  - PUT 再更新身高

### Frontend

#### `src/pages/profile/profile.vue`

- 表单：
  - 昵称（可编辑，调 `PUT /profile/nickname` 不在本任务，留给将来；暂时用 store 的）
  - 生日 picker（`<picker mode="date">`）
  - 性别 radio
  - 身高 input number
  - 体重 input number
  - 忌口标签多选 chip（来自常量列表）
- 提交按钮 → `api.profile.upsert(formData)` → 成功 toast + 返回 today
- `onLoad` 若有 profile 则预填

#### `src/api/profile.ts`

```ts
export const getProfile = () => request<UserWithProfile>({ url: '/profile' })
export const upsertProfile = (data: ProfileUpsert) =>
  request<ProfileRead>({ url: '/profile', method: 'PUT', data })
```

#### `src/stores/user.ts` 扩展

- `profile: ref<UserProfile | null>`，`fetchProfile()` / `saveProfile()` action

#### 常量同步

- 前端 `src/constants/forbidden-tags.ts`：手抄（或后续通过 gen:api 自动拉，本任务手抄即可）

#### 星座自动算

- 本任务**不**实现星座计算（T08 后端做），但 `ProfileRead` 加 `zodiac_sign?: string` 字段，由后端 `ProfileRead.from_orm` 时计算（T08 实现）。本任务返回 `null`

## Acceptance Criteria

- [ ] 登录后进入档案页，能填写所有字段并提交
- [ ] 提交后再次进入页面，能看到上次填写的内容
- [ ] 忌口标签必须是预定义集合内的值（前端 picker + 后端校验）
- [ ] 身高超出 80-250 → 后端 422
- [ ] 未登录访问 GET /profile → 401
- [ ] 后端 pytest 全绿，前端 type-check / lint 全绿

## Dependencies

- T04（用户已登录、有 User 表）

## Notes

- forbidden_tags 用 JSON 字段，不要拆成关联表（MVP 阶段）
- `birthday` 用字符串存，不用 Date，避免时区问题
- `constitution_type` 字段不在本任务范围（T06 处理）
