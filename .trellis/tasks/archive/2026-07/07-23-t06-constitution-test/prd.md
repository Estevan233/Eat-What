# T06 体质测试问卷与判定

## Goal

让用户做 9 题问卷，判定其属于九种中医体质（平和/气虚/阳虚/阴虚/痰湿/湿热/血瘀/气郁/特禀）中的哪一种（或多主+兼夹），存入档案。结果供推荐算法参考。

## Requirements

### 判定依据

- 来源：中华中医药学会《中医体质分类与判定》（ZYYXH/T157-2009）
- 9 题问卷，每题 5 级 Likert（1=没有 → 5=总是）
- 每题对应一种偏颇体质（除平和质用反向题）
- 算法：
  - 每种体质转化分 = (该体质题原始分 - 该题数) / (题数 × 4) × 100
  - 转化分 ≥ 60 → 是该体质
  - 取所有 ≥ 60 的体质，主体质 = 转化分最高；其余为兼夹
  - 全 < 60 且平和质转化分 ≥ 60 → 主体质「平和」
  - 全 < 60 → fallback「平和」（不区分）

### Backend

#### `app/services/constitution.py`

```python
QUESTIONS = [
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

def judge(scores: dict[int, int]) -> ConstitutionResult:
    """scores: {question_id: 1-5}"""
    ...
```

返回 `ConstitutionResult`：
- `primary: str`（如 "pinghe"）
- `secondary: list[str]`
- `scores_normalized: dict[str, int]`（每体质转化分 0-100）

#### `app/schemas/constitution.py`

- `ConstitutionQuestionnaire`：9 个 1-5 的整数
- `ConstitutionResult`：上述结构

#### 路由

- `POST /profile/constitution` → 接收问卷、判定、存到 `UserProfile.constitution_type`（如 `"qixu;shire"` 主+兼夹用分号串）
- 返回 `ConstitutionResult`
- `GET /profile/constitution` → 返回上次结果（不存在返回 404）

#### 数据迁移

- 已有 `UserProfile` 表加 `constitution_type: Optional[str] = Field(default=None, max_length=64)`
- 开发期：删 `dev.db` 重建

#### 测试

- `tests/services/test_constitution.py`：
  - 全 1（平和反向）→ 平和
  - 题 2=5，其余=1 → 主气虚
  - 多种 ≥ 60 → 取最高为主、其余为兼夹

### Frontend

#### `src/pages/constitution/constitution.vue`

- 9 题单页或分页，每题 5 个 radio 按钮
- 进度条显示
- 提交按钮 → `api.constitution.submit(answers)`
- 成功后展示结果：主体质 + 兼夹 + 转化分柱状图（用 uview-plus 的 `<u-line-chart>` 或自实现 div bar）
- 「重新测试」按钮

#### `src/api/constitution.ts`

```ts
export const submit = (answers: Record<number, number>) =>
  request<ConstitutionResult>({ url: '/profile/constitution', method: 'POST', data: { answers } })
export const getResult = () =>
  request<ConstitutionResult>({ url: '/profile/constitution' })
```

#### `src/types/api.ts` 扩展

- `ConstitutionResult`、9 种体质枚举常量与中文名映射

## Acceptance Criteria

- [ ] 9 题全部填写后能提交
- [ ] 重新测试会覆盖之前的体质
- [ ] 后端判定结果与 spec 中判定规则一致（单测覆盖 4 个分支）
- [ ] 主+兼夹体质写入 `user_profiles.constitution_type`，如 `"qixu;shire"`
- [ ] 前端结果页展示主体质与兼夹，转化分柱状图能显示
- [ ] 未登录 → 401；登录用户访问 `mine` tab 时若未测，给出引导「去测体质」

## Dependencies

- T05（UserProfile 表与档案接口）

## Notes

- 9 题题面文本不可随意改，必须忠于标准
- 5 级 Likert 选项文案：1「没有」2「很少」3「有时」4「经常」5「总是」
- 平和质反向题：分数越高 → 平和转化分越低（spec 中已说明）
- 不引入「体质 = 单一」强约束，要支持兼夹
