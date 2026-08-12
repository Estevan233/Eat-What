from pydantic import BaseModel, Field


class RecipeIngredient(BaseModel):
    name: str
    amount: float | None = None
    unit: str
    optional: bool = False


class NutritionPerServing(BaseModel):
    energy_kcal: float = Field(gt=0)
    protein_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    carb_g: float = Field(ge=0)


class RecipeRead(BaseModel):
    food_id: int
    food_name: str
    meal_role: str
    visual_key: str
    servings: int
    ingredients: list[RecipeIngredient]
    steps: list[str]
    prep_time_min: int
    cook_time_min: int
    nutrition_per_serving: NutritionPerServing
    difficulty: str
    source_url: str | None
    nutrition_basis: str
    version: int
