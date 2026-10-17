import datetime as dt

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_demo_today_blank_is_none():
    assert Settings(_env_file=None, demo_today="").demo_today is None


def test_demo_today_parsed():
    assert Settings(_env_file=None, demo_today="2026-12-01").demo_today == dt.date(2026, 12, 1)


def test_demo_today_garbage_rejected_at_startup():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, demo_today="hôm nay")


def test_gateway_cache_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gateway_cache="record")


def test_planner_mode_blank_is_single():
    assert Settings(_env_file=None, planner_mode="").planner_mode == "single"
    assert Settings(_env_file=None).planner_mode == "single"


def test_planner_mode_multi_accepted_and_garbage_rejected():
    assert Settings(_env_file=None, planner_mode="multi").planner_mode == "multi"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, planner_mode="nhieu")
