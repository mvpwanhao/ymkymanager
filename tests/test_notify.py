# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""notify 模块：填报成功通知与通道回退测试。"""

from app.services import notify


def _enable_push(monkeypatch, *, serverchan: bool = False):
    """仅启用自建推送通道，并把发送函数替换为记录器。"""
    calls = {}

    def fake_send_wechat_push(*, title: str, content: str):
        calls["push"] = (title, content)
        return True, "微信提醒已发送"

    monkeypatch.setattr(notify, "_push_available", lambda: True)
    monkeypatch.setattr(notify, "_serverchan_available", lambda: serverchan)
    monkeypatch.setattr(notify, "send_wechat_push", fake_send_wechat_push)
    return calls


def test_notify_submit_actual_message(monkeypatch):
    calls = _enable_push(monkeypatch)
    ok, _msg = notify.notify_submit_actual(
        mine="小发路煤矿",
        prod_date="2026-08-04",
        reporter="张三",
        production=1234.5,
        note="设备检修",
    )
    assert ok is True
    title, content = calls["push"]
    assert "填报成功" in title
    assert "小发路煤矿 2026-08-04 产量1234.50吨" in content
    assert "填报人：张三" in content
    assert "设备检修" in content
    assert "提交时间" in content


def test_notify_submit_energy_message(monkeypatch):
    calls = _enable_push(monkeypatch)
    ok, _msg = notify.notify_submit_energy(
        mine="小发路煤矿",
        prod_date="2026-08-04",
        reporter="张三",
        production=1234.5,
        sales=998.1,
    )
    assert ok is True
    _title, content = calls["push"]
    assert "产1234.50吨 销998.10吨" in content
    assert "填报人：张三" in content


def test_notify_submit_sales_with_mine(monkeypatch):
    calls = _enable_push(monkeypatch)
    ok, _msg = notify.notify_submit_sales(
        mine="小发路煤矿",
        week_range="2026-07-27 至 2026-08-02",
        reporter="管理员",
        sales=5000.0,
    )
    assert ok is True
    _title, content = calls["push"]
    assert "小发路煤矿 周销量5000.00吨" in content
    assert "统计周期：2026-07-27 至 2026-08-02" in content


def test_notify_submit_sales_without_mine(monkeypatch):
    calls = _enable_push(monkeypatch)
    ok, _msg = notify.notify_submit_sales(
        mine="",
        week_range="2026-07-27 至 2026-08-02",
        reporter="管理员",
        year_blended=100.5,
        year_purchased=200.25,
    )
    assert ok is True
    _title, content = calls["push"]
    assert "年累计掺配煤100.50吨 外购200.25吨" in content
    assert "煤矿" not in content


def test_notify_submit_falls_back_to_serverchan(monkeypatch):
    monkeypatch.setattr(notify, "_push_available", lambda: True)
    monkeypatch.setattr(notify, "_serverchan_available", lambda: True)
    monkeypatch.setattr(
        notify,
        "send_wechat_push",
        lambda **kwargs: (False, "微信提醒发送失败：模拟失败"),
    )
    sent = []

    def fake_serverchan(*, title: str, desp: str):
        sent.append((title, desp))
        return True, "微信提醒已发送"

    monkeypatch.setattr(notify, "send_serverchan", fake_serverchan)
    ok, _msg = notify.notify_submit_actual(
        mine="小发路煤矿", prod_date="2026-08-04", reporter="张三", production=100.0
    )
    assert ok is True
    assert sent
    assert "填报成功" in sent[0][0]


def test_notify_submit_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(notify, "_push_available", lambda: False)
    monkeypatch.setattr(notify, "_serverchan_available", lambda: False)
    ok, msg = notify.notify_submit_actual(
        mine="小发路煤矿", prod_date="2026-08-04", reporter="张三", production=100.0
    )
    assert ok is False
    assert "未配置" in msg
