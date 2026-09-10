"""Accept-Language → 教练回复语言。"""

from app.core.locale import reply_locale_from_accept_language


def test_reply_locale_defaults_zh() -> None:
    assert reply_locale_from_accept_language(None) == "zh"
    assert reply_locale_from_accept_language("") == "zh"
    assert reply_locale_from_accept_language("zh-CN,en;q=0.8") == "zh"
    assert reply_locale_from_accept_language("zh-Hans") == "zh"


def test_reply_locale_en_from_accept_language() -> None:
    assert reply_locale_from_accept_language("en") == "en"
    assert reply_locale_from_accept_language("en-US") == "en"
    assert reply_locale_from_accept_language("en-GB,en;q=0.9") == "en"
