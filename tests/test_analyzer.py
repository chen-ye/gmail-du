from analyzer import GmailAnalyzer


def test_analyzer_empty():
    analyzer = GmailAnalyzer([])
    count, size = analyzer.summary()
    assert count == 0
    assert size == 0
    assert analyzer.group_by_sender().empty
    assert analyzer.group_by_month().empty


def test_analyzer_data():
    # Mock rows: id, size, sender, subject, date (timestamp in ms)
    # The analyzer expects dict-like objects (aiosqlite.Row)

    # We can mock rows as dicts since analyzer accesses them by key
    rows = [
        {
            "id": "1",
            "size": 100,
            "sender": "alice@example.com",
            "subject": "Hello",
            "internal_date": 1609459200000,  # 2021-01-01
        },
        {
            "id": "2",
            "size": 200,
            "sender": "bob@example.com",
            "subject": "Hi",
            "internal_date": 1612137600000,  # 2021-02-01
        },
        {
            "id": "3",
            "size": 300,
            "sender": "alice@example.com",
            "subject": "Re: Hello",
            "internal_date": 1609545600000,  # 2021-01-02
        },
    ]

    analyzer = GmailAnalyzer(rows)
    count, size = analyzer.summary()

    assert count == 3
    assert size == 600

    sender_data = analyzer.group_by_sender()
    assert sender_data["alice@example.com"] == 400
    assert sender_data["bob@example.com"] == 200

    month_data = analyzer.group_by_month()
    assert month_data["2021-01"] == 400
    assert month_data["2021-02"] == 200
