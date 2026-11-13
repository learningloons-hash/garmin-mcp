from garmin_mcp.shape_dump import describe_value_shape


def test_describe_value_shape_nested() -> None:
    shape = describe_value_shape(
        {
            "hrvSummary": {"lastNightAvg": 50.1, "status": "balanced"},
            "hrvReadings": [{"hrvValue": 40}],
        }
    )
    assert shape["hrvSummary"] == {
        "lastNightAvg": "float",
        "status": "str",
    }
    assert shape["hrvReadings"][0] == "list"
    assert shape["hrvReadings"][1]["hrvValue"] == "int"
