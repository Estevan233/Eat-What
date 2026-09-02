# T06 Design — 体质测试问卷与判定

## 1. 边界

本任务交付「9 题问卷 + 判定算法 + 存档案 + 前端问卷页 + 结果展示」。**不**实现：
- 体质类型对推荐算法的影响（T10）
- 节气/星座/天气等其他 profile 字段的回填（T08/T09）
- 历史问卷记录（每次提交覆盖，不保留多版本）

## 2. 数据模型

### 2.1 UserProfile 表加字段

```python
# app/models/user_profile.py 追加字段
class UserProfile(SQLModel, table=True):
    # ... 已有字段 ...
    constitution_type: str | None = Field(default=None, max_length=64)
    # 存储格式："qixu;shire"（主+兼夹用分号串）或 "pinghe"（单一平和）
```

**字段说明**：
- 单字段存「主+兼夹」组合，避免关联表
- 主体质在前，兼夹按转化分降序排（同分按字典序）
- 格式约定：分号分隔，如 `"qixu;shire;xueyu"`

### 2.2 数据迁移

- 开发期：删 `dev.db`，`init_db()` 自动重建含新字段
- 生产环境未来用 Alembic 写 migration（不在本任务范围）
- `to_read_dict()` 加 `constitution_type` 字段输出

### 2.3 ProfileRead schema 扩展

`schemas/profile.py` 的 `ProfileRead` 加 `constitution_type: str | None` 字段。

## 3. 后端 API 契约

### 3.1 schemas `app/schemas/constitution.py`（新建）

```python
from pydantic import BaseModel, Field
from typing import Literal

# 9 种体质的 Python 标识符（与前端共享语义）
ConstitutionType = Literal[
    "pinghe", "qixu", "yangxu", "yinxu", "tanshi",
    "shire", "xueyu", "qiyu", "tebing",
]


class ConstitutionQuestionnaire(BaseModel):
    """POST /profile/constitution 请求体。
    answers 是 9 题的 {question_id(1-9): 1-5} 字典。
    """
    answers: dict[int, int] = Field(..., description="9 题答案，key=题号1-9，value=1-5")


class ConstitutionResult(BaseModel):
    """判定结果。"""
    primary: ConstitutionType                  # 主体质
    secondary: list[ConstitutionType]           # 兼夹（不含主）
    scores_normalized: dict[ConstitutionType, int]  # 每体质转化分 0-100
    constitution_type_str: str                  # 落库字符串，如 "qixu;shire"
```

### 3.2 service `app/services/constitution.py`（新建）

#### 9 题题库（常量）

```python
QUESTIONS: list[dict[str, Any]] = [
    {"id": 1, "text": "您精力充沛吗？", "type": "pinghe_reverse"},
    {"id": 2, "text": "您容易疲乏吗？", "type": "qixu"},
    {"id": 3, "text": "您手脚发凉吗？", "type": "yangxu"},
    {"id": 4, "text": "您手脚心发热吗？", "type": "yinxu"},
    {"id": 5, "text": "您体型偏胖、腹部松软吗？", "type": "tanshi"},
    {"id": 6, "text": "您面部或额头易出油、生痘吗？", "type": "shire"},
    {"id": 7, "text": "您皮肤易瘀青、有黑斑吗？", "type": "xueyu"},
    {"id": 8, "text": "您容易闷闷不乐、多愁善感吗？", "type": "qiyu"},
    {"id": 9, "text": "您过敏（鼻塞/皮疹）吗？", "type": "tebing"},
]

CONSTITUTION_NAMES: dict[str, str] = {
    "pinghe": "平和质", "qixu": "气虚质", "yangxu": "阳虚质", "yinxu": "阴虚质",
    "tanshi": "痰湿质", "shire": "湿热质", "xueyu": "血瘀质", "qiyu": "气郁质",
    "tebing": "特禀质",
}
```

#### 判定算法

```python
def judge(scores: dict[int, int]) -> ConstitutionResult:
    """scores: {question_id(1-9): 1-5}。"""
    # 1. 校验：必须 9 题，每题 1-5
    # 2. 按 type 聚合原始分
    # 3. 平和质是反向题：raw_pinghe = (6 - score_q1)  （反向：1→5, 5→1）
    #    等价于：raw_pinghe = 6 - scores[1]
    # 4. 转化分 = (原始分 - 题数) / (题数 × 4) × 100
    #    每体质只有 1 题，题数=1
    #    normalized = (raw - 1) / 4 * 100
    # 5. ≥ 60 的体质为「是」
    # 6. 主体质 = 转化分最高；兼夹 = 其余 ≥ 60 的（按分降序，同分按字典序）
    # 7. 全 < 60：
    #    - 若 pinghe 转化分 ≥ 60 → 主体质「平和」
    #    - 否则 → fallback「平和」
```

**注意点**：
- 平和质反向题：用户答「5=总是精力充沛」时，原始分应是最高（5），转化分 100 → 判为平和。所以 `raw_pinghe = scores[1]`（不反转），反向体现在「分数越高越平和」语义。
  - 重新核对：题 1 是「您精力充沛吗？」，5=总是精力充沛 → 平和。所以 raw_pinghe = scores[1] 直接用，**不反转**。
  - 但 spec 写「平和质反向题：分数越高 → 平和转化分越低」← 这与题 1 文本矛盾。重新解读 spec：spec 的意思是「**转化分**越高的题越偏离平和」，平和体质不是用题 1 的转化分判定，而是用「**所有偏颇体质转化分都 < 60**」推断。
  - **决策**：题 1（pinghe_reverse）也按偏颇体质一样计算 raw_pinghe = 6 - scores[1]（即用户答 5=总是精力充沛 → raw_pinghe = 1 → 转化分 0 → 不偏颇平和，与题文本一致：精力充沛意味着不偏颇）。这种处理让所有 9 种体质用同一套转化分公式，避免特殊路径。
  - 简化：题 1 用 `raw_pinghe = 6 - scores[1]`，转化分 `(raw - 1) / 4 * 100`，与其它 8 题对称。判平和的条件就是「9 体质转化分都 < 60」时 fallback 为平和。

#### service 接口

```python
def judge(scores: dict[int, int]) -> ConstitutionResult: ...
def save_constitution(session, user_id, result: ConstitutionResult) -> None:
    """把 constitution_type_str 写到 UserProfile.constitution_type。"""
def get_constitution(session, user_id) -> ConstitutionResult | None:
    """从 UserProfile.constitution_type 读回。但无法还原 scores_normalized。
    
    决策：GET 时只返回 constitution_type_str（解析成 primary + secondary 列表），
    scores_normalized 不返回（因为没存）。如需展示转化分，前端应在 POST 后自己存。
    
    替代方案： UserProfile 加 constitution_scores JSON 列存完整 result。
    决策：加 JSON 列存完整 result，避免「POST 拿到完整 → GET 只有字符串」的不对称。
    """
```

### 2.4 修订：UserProfile 加 constitution_scores JSON 列

```python
constitution_type: str | None = Field(default=None, max_length=64)
constitution_scores: dict[str, int] | None = Field(default=None, sa_column=Column(JSON))
# 存 {"pinghe": 0, "qixu": 100, ...} 完整转化分
```

`to_read_dict()` 加这两个字段输出。

### 3.3 路由 `app/api/v1/constitution.py`（新建）

```python
router = APIRouter(prefix="/profile/constitution", tags=["constitution"])

@router.post("", response_model=dict[str, Any])
def submit_constitution_route(
    body: ConstitutionQuestionnaire,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """提交问卷 → 判定 → 存档 → 返回 ConstitutionResult。"""
    result = constitution_service.judge(body.answers)
    constitution_service.save_constitution(session, user.id, result)
    return success(data=result.model_dump())

@router.get("", response_model=dict[str, Any])
def get_constitution_route(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """读上次判定结果。不存在 → 404 NotFoundError。"""
    result = constitution_service.get_constitution(session, user.id)
    if result is None:
        raise NotFoundError("constitution", user.id)
    return success(data=result.model_dump())
```

**注册到 `api/v1/__init__.py`**：与 profile_router 并列。

### 3.4 GET 题库路由（前端拉题面用）

```python
@router.get("/questions", response_model=dict[str, Any])
def get_questions_route() -> dict[str, object]:
    """返回 9 题题面 + 5 级 Likert 选项文案。前端首次进入问卷页时拉取。"""
    return success(data={
        "questions": QUESTIONS,
        "options": [
            {"value": 1, "label": "没有"},
            {"value": 2, "label": "很少"},
            {"value": 3, "label": "有时"},
            {"value": 4, "label": "经常"},
            {"value": 5, "label": "总是"},
        ],
    })
```

放在 `app/api/v1/constitution.py` 同一 router 下，路径 `/profile/constitution/questions`。无需登录（题库是公开静态数据）。

## 4. 前端契约

### 4.1 类型 `miniapp/src/types/api.ts` 扩展

```ts
export type ConstitutionType =
  | 'pinghe' | 'qixu' | 'yangxu' | 'yinxu' | 'tanshi'
  | 'shire' | 'xueyu' | 'qiyu' | 'tebing'

export interface ConstitutionQuestionnaire {
  answers: Record<number, number>  // key 1-9, value 1-5
}

export interface ConstitutionResult {
  primary: ConstitutionType
  secondary: ConstitutionType[]
  scoresNormalized: Record<ConstitutionType, number>
  constitutionTypeStr: string
}

export interface ConstitutionQuestionsPayload {
  questions: Array<{ id: number; text: string; type: string }>
  options: Array<{ value: number; label: string }>
}
```

### 4.2 常量 `miniapp/src/constants/constitution.ts`（新建）

```ts
export const CONSTITUTION_NAMES: Record<ConstitutionType, string> = {
  pinghe: '平和质', qixu: '气虚质', yangxu: '阳虚质', yinxu: '阴虚质',
  tanshi: '痰湿质', shire: '湿热质', xueyu: '血瘀质', qiyu: '气郁质',
  tebing: '特禀质',
}
```

### 4.3 API 封装 `miniapp/src/api/constitution.ts`（新建）

```ts
export const getQuestions = () =>
  request<ConstitutionQuestionsPayload>({ url: '/v1/profile/constitution/questions' })
export const submit = (answers: Record<number, number>) =>
  request<ConstitutionResult>({
    url: '/v1/profile/constitution',
    method: 'POST',
    data: { answers },  // request 层 camelToSnake 会转，但这里 key 是数字不动
  })
export const getResult = () =>
  request<ConstitutionResult>({ url: '/v1/profile/constitution' })
```

**注意**：`answers` 的 key 是数字（1-9），`camelToSnake` 不会动数字 key（只转 string key），所以安全。

### 4.4 user store 扩展

`stores/user.ts` 加：
- `constitution: ref<ConstitutionResult | null>`（与 userProfile 并列，独立缓存）
- `fetchConstitution()` / `saveConstitution(answers)` action
- 落 storage `eat_what_constitution`

### 4.5 问卷页 `pages/constitution/constitution.vue`（重写）

- onLoad：拉 `getQuestions()`，渲染 9 题 × 5 radio
- 进度条（已答题数 / 9）
- 提交按钮（disabled 直到 9 题答完）
- 提交成功 → 切到「结果视图」：主体质大字 + 兼夹 chip + 转化分柱状图（自实现 div bar，每条按体质类型显示中文 + 分值 + 进度条）
- 「重新测试」按钮 → 重置表单，回到问卷视图

### 4.6 mine.vue 引导（小改动）

`pages/mine/mine.vue` 增加一行：若 `userStore.constitution === null` 显示「未测体质，去测 →」按钮，点击 `uni.switchTab({ url: '/pages/constitution/constitution' })`。

## 5. 测试策略

### 5.1 后端 service 单测 `tests/services/test_constitution.py`

| 测试 | 输入 | 期望 |
|---|---|---|
| `test_all_ones_falls_back_to_pinghe` | 全 1 | primary=pinghe, secondary=[] |
| `test_q5_others_1_qixu_primary` | 题2=5，其余1 | primary=qixu, secondary=[] |
| `test_multi_high_scores_picks_highest_primary` | 题2=5、题6=4 | 主体质=转化分高的；副=另一个≥60 |
| `test_scores_below_60_with_high_pinghe_still_pinghe` | 平和反向高分 | primary=pinghe |
| `test_invalid_question_count_returns_422` | answers 缺题 | ValidationError 422 |
| `test_invalid_score_returns_422` | value=6 | 422 |

### 5.2 后端 API 集成测 `tests/test_api_v1/test_constitution.py`

| 测试 | 验证 |
|---|---|
| `test_submit_unauthenticated_returns_401` | 不带 token POST → 401 |
| `test_submit_creates_and_returns_result` | 登录后 POST 全 1 → 返回 pinghe；DB 有记录 |
| `test_submit_then_get_returns_same` | POST 后 GET 一致 |
| `test_get_without_prior_returns_404` | 登录用户无记录 GET → 404 |
| `test_questions_endpoint_no_auth_needed` | 不带 token GET /questions → 200 |

### 5.3 前端

无单测。靠 type-check + lint + build + 手动 E2E。

## 6. 兼容性与回归

- **UserProfile 表加 2 个字段**：`constitution_type` / `constitution_scores`，开发期删 dev.db 重建。
- **ProfileRead schema 加字段**：前端 `ProfileRead` 类型也要加 `constitutionType` / `constitutionScores` 字段（camelCase）。
- **`get_profile` service 不变**：通过 `to_read_dict()` 自动包含新字段。
- **常量同步**：前端 `constants/constitution.ts` 与后端 `services/constitution.py` 的 `CONSTITUTION_NAMES` 必须手抄同步。

## 7. 取舍记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 题库位置 | service 模块常量 | 题面是业务逻辑的一部分，与判定算法同源 |
| constitution_type 字段 | str 单字段，主+兼夹分号串 | 简单，避免关联表 |
| constitution_scores 字段 | JSON 列存完整转化分 | GET 需要展示完整结果，不能只存字符串 |
| 题库路由 | 公开 GET /questions | 题面是静态公开数据，不需登录 |
| 平和质判定 | 全 < 60 → fallback 平和 | spec 明确说明，避免「无体质」状态 |
| 平和质反向题 | raw_pinghe = 6 - scores[1] | 让所有 9 体质用同一公式，避免特殊路径 |
| 前端柱状图 | 自实现 div bar | 不引第三方图表库（uview-plus 不在 deps） |
