from dbt_common.events.contextvars import log_contextvars, get_node_info, set_log_contextvars


def test_contextvars() -> None:
    node_info = {
        "unique_id": "model.test.my_model",
        "started_at": None,
        "finished_at": None,
    }
    with log_contextvars(node_info=node_info):
        assert node_info == get_node_info()
        new_node_info = {
            "unique_id": "model.test.my_model",
            "started_at": "01-01-2024",
            "finished_at": None,
        }
        set_log_contextvars(node_info=new_node_info)
        assert get_node_info() == new_node_info

    # Ensure that after the context manager ends, the node_info is gone
    assert get_node_info() == {}
