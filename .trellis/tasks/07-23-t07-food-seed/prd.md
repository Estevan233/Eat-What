# T07 食物库冷启动数据

## Goal

为推荐算法准备约 200 道家常菜的结构化数据，作为冷启动数据集。每道菜含营养、性味归经、适宜天气/体质标签，可被推荐算法使用。

## Requirements

### 数据规模

- **≥ 200 道菜**，覆盖：
  - 主食（米饭、面条、馒头、杂粮粥、馄饨、包子 等）
  - 蛋白质（鸡、鸭、鱼、虾、猪、牛、豆腐、蛋类）
  - 蔬菜（叶菜、根茎、瓜茄、菌菇）
  - 汤/粥（小米粥、银耳羹、酸梅汤 等）
  - 凉菜 vs 热菜比例 ~20% vs 80%

### Schema（`backend/data/food_seed.json`）

```json
[
  {
    "name": "番茄炒蛋",
    "category": "stir_fry",
    "ingredients": ["番茄", "鸡蛋", "葱"],
    "calories_kcal_per_100g": 86,
    "nutrition": {
      "protein_g": 5.5,
      "fat_g": 5.0,
      "carb_g": 4.5,
      "fiber_g": 1.2
    },
    "nature": "neutral",                     // cold | cool | neutral | warm | hot
    "flavor": ["sour", "sweet"],              // subset of [sour, bitter, sweet, spicy, salty, bland]
    "organ_meridians": ["stomach", "spleen"], // 可空
    "suitable_constitutions": ["pinghe", "qixu", "yangxu"],
    "suitable_weathers": ["any"],            // cold | hot | rainy | dry | any
    "forbidden_for": ["shizhuo_banned_if_soup"],  // 标记某些场景禁忌，可空
    "tags": ["vegetarian", "egg", "quick"],  // 通用标签
    "cooking_method": "stir_fry",            // steam | boil | stir_fry | deep_fry | cold | soup | congee | other
    "cooking_time_min": 15,
    "image_url": null,                       // 可空，后续补
    "seasonal_solar_terms": ["xiaoshu", "dachu"],  // 适合的节气，可空
    "description": "番茄炒蛋是家常下饭菜，酸甜开胃。"
  }
]
```

### 字段约束

- `nature`：寒/凉/平/温/热 五种之一（中文键映射到英文）
- `flavor`：子集，5 味 + 淡味
- `suitable_constitutions`、`forbidden_for`：值在 9 体质枚举内
- `cooking_method`：枚举值
- `tags`：自由字符串，建议来自一个固定集合（vegetarian/egg/fish/pork/beef/seafood/quick/easy/cold_dish/soup）

### Backend

#### 模型 `app/models/food.py`

```python
class Food(SQLModel, table=True):
    __tablename__ = "foods"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=64)
    category: str = Field(max_length=32)
    ingredients_json: List[str] = Field(default=[], sa_column=Column(JSON))
    calories_kcal_per_100g: Optional[float]
    nutrition_json: dict = Field(default={}, sa_column=Column(JSON))
    nature: str = Field(max_length=16)
    flavor_json: List[str] = Field(default=[], sa_column=Column(JSON))
    organ_meridians_json: List[str] = Field(default=[], sa_column=Column(JSON))
    suitable_constitutions_json: List[str] = Field(default=[], sa_column=Column(JSON))
    suitable_weathers_json: List[str] = Field(default=[], sa_column=Column(JSON))
    forbidden_for_json: List[str] = Field(default=[], sa_column=Column(JSON))
    tags_json: List[str] = Field(default=[], sa_column=Column(JSON))
    cooking_method: str = Field(max_length=32)
    cooking_time_min: Optional[int]
    image_url: Optional[str] = Field(default=None, max_length=512)
    seasonal_solar_terms_json: List[str] = Field(default=[], sa_column=Column(JSON))
    description: Optional[str]
```

#### service `app/services/food_seed.py`

- `import_seed(session, json_path="data/food_seed.json") -> int`：清表后导入，返回条数
- `food_service.get_all(session) -> list[Food]`
- `food_service.get_by_id(session, id) -> Food | None`
- `food_service.search(session, q) -> list[Food]`

#### 路由 `app/api/v1/food.py`

- `GET /food` → 分页（默认 20，最多 50，按 category 过滤）
- `GET /food/{id}` → 详情
- `GET /food/search?q=` → 名称模糊搜索

#### CLI 入口

- `app/cli.py` 或 `pyproject.toml [tool.poetry.scripts]`：
  - `python -m app.cli seed-food` → 跑 `food_seed.import_seed`

#### 测试

- `tests/services/test_food_seed.py`：从 in-memory JSON 导入 → 查询条数
- `tests/test_api_v1/test_food.py`：导入后 GET /food 返回 20 条

### 数据来源

- 营养数据：USDA FoodData Central API + 中文菜谱网站的人工整理（可由 AI 辅助生成）
- 性味归经、适宜体质：参考《中华本草》《中医食疗学》及国家中医药管理局公开资料
- 烹饪方法、时间：参考下厨房等公开菜谱元数据

### 质量要求

- 每道菜必须有 name、category、nature、cooking_method、calories_kcal_per_100g
- ≥ 90% 的菜必须有 suitable_constitutions（至少一个）
- ≥ 80% 的菜必须有 nutrition 完整四项
- ≥ 50% 的菜必须有 seasonal_solar_terms

## Acceptance Criteria

- [ ] `data/food_seed.json` 至少 200 道菜，字段符合 schema
- [ ] 跑 `python -m app.cli seed-food` 后 `SELECT COUNT(*) FROM foods` = 数据条数
- [ ] `GET /food?page=1&size=20` 返回 20 条
- [ ] `GET /food/{id}` 返回详情
- [ ] `GET /food/search?q=番茄` 返回匹配项
- [ ] 数据校验脚本通过（schema、字段约束）
- [ ] pytest 全绿

## Dependencies

- T02（FastAPI 基础设施、SQLModel metadata.create_all）

## Notes

- 本任务**不**实现图片上传与 CDN，image_url 留 null
- 不在 Food 表上做食物的「用户提交」，所有数据来自 seed
- 数据生成时不要杜撰营养数值，宁可少标
- 重复导入应 idempotent（用 `name` 唯一约束 + upsert）
