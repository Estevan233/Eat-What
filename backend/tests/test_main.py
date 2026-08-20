"""Application metadata tests."""


def test_openapi_uses_fanbubu_product_name(client) -> None:
    from app.main import app

    assert app.title == "饭卜卜 API"
