"""Приём Telegram из шлюза основы (28.09): один парсер — один аккаунт, LARP берёт накопленное.

Держится:
1. Каналы игр уходят в подписку larp добавлением (POST), приглашения (`+…`) — нет.
2. Пост ложится в тот же источник `tg:<канал>`, что у tg_web: взятый через t.me/s второй раз не ляжет.
3. Курсор шлюза сохраняется; пустое и короткое не берётся; разметка шлюза → дисциплина и страна.
   НРИ и ролевые (решение владельца 28.09) не берутся; канал с тегом ларпа при них — берётся.
4. Шлюз лежит — ничего не меняется, курсор прежний.
"""
from __future__ import annotations

import json

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from hmb.importers import tg_gateway as tg
from hmb.models import Base, Game, InboxItem, Source


def make_db():
    eng = create_engine("sqlite://", future=True)
    Base.metadata.create_all(eng)
    return Session(eng)


def gateway(pages, calls):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, dict(req.url.params), req.content))
        if req.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        if req.url.path == "/subscriptions/larp":
            return httpx.Response(200, json={"added": ["igra_chan"]})
        return httpx.Response(200, json=pages[int(req.url.params["after"])])
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://gw")


def test_sync_and_pull(tmp_path, monkeypatch):
    monkeypatch.setattr(tg, "GATEWAY_URL", "http://gw")
    db = make_db()
    db.add_all([Game(id=1, name="Игра", telegram_channel="@Igra_Chan", deleted=False),
                Game(id=2, name="Закрытая", telegram_channel="+AbCdEf", deleted=False)])
    # пост 5 уже взят через t.me/s — тот же источник, тот же id
    db.add(Source(id="tg:igra_chan", kind="tg", title="@igra_chan", url="https://t.me/s/igra_chan"))
    db.add(InboxItem(source_id="tg:igra_chan", external_id="5", raw_text="старый пост", provenance="import:tg_web"))
    db.commit()
    pages = {0: {"posts": [
                {"channel": "igra_chan", "msg_id": 5, "date": "2026-09-27T10:00:00Z", "text": "старый пост", "tags": ["игры"]},
                {"channel": "sneaky_dice", "msg_id": 7, "date": "2026-09-28T10:00:00Z", "text": "Гайд мастеру\\nтекст",
                 "tags": ["нри", "нри/dnd"]},
                {"channel": "poickrp_chat", "msg_id": 3, "text": "Ищу игроков в ролевую", "tags": ["ролевые", "ролевые/поиск игроков"]},
                {"channel": "rsu_knights", "msg_id": 2, "text": "Игротека в пятницу", "tags": ["ларп", "нри"]},
                {"channel": "sneaky_dice", "msg_id": 8, "text": "+", "tags": ["нри"]}],
                 "cursor": 40, "more": True},
             40: {"posts": [{"channel": "fehtovanie_rs", "msg_id": 1, "text": "Тренировка в субботу", "tags": ["фехтование", "сербия"],
                             "attachments": [{"mime": "image/jpeg"}]}],
                  "cursor": 41, "more": False}}
    calls = []
    res = tg.run(db, state_file=tmp_path / "st.json", client=gateway(pages, calls))
    assert res["status"] == "ok" and res["cursor"] == 41 and res["pull"]["ignored_rpg"] == 2
    sub = [c for c in calls if c[1] == "/subscriptions/larp"][0]
    assert sub[0] == "POST" and [i["handle"] for i in json.loads(sub[3])["channels"]] == ["igra_chan"]
    items = {(i.source_id, i.external_id): i for i in db.scalars(select(InboxItem))}
    assert set(items) == {("tg:igra_chan", "5"), ("tg:rsu_knights", "2"), ("tg:fehtovanie_rs", "1")}
    assert db.get(Source, "tg:sneaky_dice") is None and db.get(Source, "tg:poickrp_chat") is None
    feh = items[("tg:fehtovanie_rs", "1")]
    assert feh.provenance == "import:tg_gateway" and feh.photos_count == 1
    assert (db.get(Source, "tg:rsu_knights").discipline, db.get(Source, "tg:fehtovanie_rs").country) == ("larp", "RS")
    assert json.loads((tmp_path / "st.json").read_text())["cursor"] == 41

    # второй запуск: синхронизация не раньше суток, курсор с места
    calls.clear()
    pages[41] = {"posts": [], "cursor": 41, "more": False}
    tg.run(db, state_file=tmp_path / "st.json", client=gateway(pages, calls))
    assert [c[1] for c in calls] == ["/health", "/posts"] and calls[1][2]["after"] == "41"


def test_gateway_down_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(tg, "GATEWAY_URL", "http://gw")
    (tmp_path / "st.json").write_text(json.dumps({"cursor": 9, "synced_at": 0}))

    def down(req):
        raise httpx.ConnectError("нет связи")

    res = tg.run(make_db(), state_file=tmp_path / "st.json", client=httpx.Client(transport=httpx.MockTransport(down)))
    assert res["status"] == "gateway_down" and res["cursor"] == 9
    assert json.loads((tmp_path / "st.json").read_text())["cursor"] == 9
