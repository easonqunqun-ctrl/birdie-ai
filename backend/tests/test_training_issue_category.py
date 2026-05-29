"""M10-05 · category-aware drill pick."""

from app.services.training.issue_category import category_for_issue


def test_putting_issue_maps_to_putting_category():
    assert category_for_issue("putting_head_moved") == "putting"


def test_chipping_issue_maps_to_chipping_category():
    assert category_for_issue("chipping_thin") == "chipping"


def test_full_swing_issue_maps():
    assert category_for_issue("casting") == "full_swing"
