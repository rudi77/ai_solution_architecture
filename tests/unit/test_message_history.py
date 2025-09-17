from typing import List, Dict, Any

import pytest  # type: ignore


from capstone.agent_v2.agent import MessageHistory


def roles_of(messages: List[Dict[str, Any]]) -> List[str]:
    return [m["role"] for m in messages]


def contents_of(messages: List[Dict[str, Any]]) -> List[str]:
    return [m["content"] for m in messages]


def make_history_with_pairs(num_pairs: int) -> MessageHistory:
    mh = MessageHistory("sys")
    for i in range(1, num_pairs + 1):
        mh.add_message(f"u{i}", "user")
        mh.add_message(f"a{i}", "assistant")
    return mh


def test_init_contains_system_prompt_first():
    mh = MessageHistory("system text")
    assert len(mh.messages) == 1
    assert mh.messages[0]["role"] == "system"
    assert mh.messages[0]["content"] == "system text"


def test_add_message_appends_in_order():
    mh = MessageHistory("sys")
    mh.add_message("hello", "user")
    mh.add_message("hi", "assistant")
    assert roles_of(mh.messages) == ["system", "user", "assistant"]
    assert contents_of(mh.messages) == ["sys", "hello", "hi"]


def test_get_last_n_messages_returns_only_system_when_no_pairs():
    mh = MessageHistory("sys")
    out = mh.get_last_n_messages(2)
    assert roles_of(out) == ["system"]


def test_get_last_n_messages_n_zero_returns_only_system():
    mh = make_history_with_pairs(2)
    out = mh.get_last_n_messages(0)
    assert roles_of(out) == ["system"]


def test_get_last_n_messages_one_pair():
    mh = make_history_with_pairs(2)
    out = mh.get_last_n_messages(1)
    assert roles_of(out) == ["system", "user", "assistant"]
    assert contents_of(out) == ["sys", "u2", "a2"]


def test_get_last_n_messages_two_pairs():
    mh = make_history_with_pairs(2)
    out = mh.get_last_n_messages(2)
    # Should include both pairs in chronological order
    assert roles_of(out) == ["system", "user", "assistant", "user", "assistant"]
    assert contents_of(out) == ["sys", "u1", "a1", "u2", "a2"]


def test_get_last_n_messages_more_than_available_returns_all_pairs():
    mh = make_history_with_pairs(2)
    out = mh.get_last_n_messages(5)
    assert roles_of(out) == ["system", "user", "assistant", "user", "assistant"]
    assert contents_of(out) == ["sys", "u1", "a1", "u2", "a2"]


def test_get_last_n_messages_ignores_incomplete_trailing_message():
    mh = MessageHistory("sys")
    mh.add_message("u1", "user")
    mh.add_message("a1", "assistant")
    mh.add_message("u2", "user")  # incomplete pair
    out = mh.get_last_n_messages(2)
    # Should include only the complete pair (u1, a1)
    assert roles_of(out) == ["system", "user", "assistant"]
    assert contents_of(out) == ["sys", "u1", "a1"]


def test___str___returns_json_and_preserves_unicode_characters():
    # Include non-ASCII to ensure ensure_ascii=False behavior
    mh = MessageHistory("sÿs")
    mh.add_message("héllo", "user")
    mh.add_message("wørld", "assistant")

    text = str(mh)
    assert isinstance(text, str)
    # Raw unicode characters should appear in the JSON string
    assert "sÿs" in text
    assert "héllo" in text
    assert "wørld" in text

    import json

    data = json.loads(text)
    assert isinstance(data, list)
    assert data[0]["role"] == "system"
    assert data[0]["content"] == "sÿs"
    assert data[1]["role"] == "user"
    assert data[1]["content"] == "héllo"
    assert data[2]["role"] == "assistant"
    assert data[2]["content"] == "wørld"


