"""Tests for src/hashtags — the shared contact-tag filter."""

from src.hashtags import all_hashtags, is_contact_hashtag, marketing_hashtags


def test_all_hashtags_returns_every_tag_lowercased():
    assert all_hashtags("طقم #كارتير #استيل, للطلب #+967777000111.") == [
        "#كارتير",
        "#استيل",
        "#+967777000111",
    ]
    assert all_hashtags("") == []
    assert all_hashtags(None) == []


def test_is_contact_hashtag_separates_phones_from_marketing_tags():
    assert is_contact_hashtag("#+967777000111")
    assert is_contact_hashtag("#0777000000")
    assert is_contact_hashtag("#777000")
    assert not is_contact_hashtag("#كارتير")
    assert not is_contact_hashtag("#Dior2026")  # letters still dominate
    assert not is_contact_hashtag("#Butterfly")
    assert not is_contact_hashtag("#set2")  # a single digit is marketing


def test_marketing_hashtags_drops_contact_tags_only():
    assert marketing_hashtags("للطلب #+967777000111 #كارتير #صنعاء") == ["#كارتير", "#صنعاء"]


def test_marketing_hashtags_empty_when_all_tags_are_contact_info():
    assert marketing_hashtags("#+967777000111 #777000222") == []
