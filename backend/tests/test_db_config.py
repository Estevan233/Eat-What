from app.db import build_engine_options


def test_sqlite_options() -> None:
    options = build_engine_options('sqlite:///./dev.db', debug=False)

    assert options['connect_args'] == {'check_same_thread': False}
    assert options['echo'] is False


def test_mysql_options() -> None:
    options = build_engine_options('mysql+pymysql://u:p@db/eat', debug=False)

    assert options['pool_pre_ping'] is True
    assert options['pool_recycle'] == 300
    assert 'connect_args' not in options
