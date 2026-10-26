"""Contract test for the sample app.

Stubs the meter-usage client in the test itself, so no network call
and no API key is needed. The stub returns the OLD-format response,
and the test asserts the OLD request/response field names - which is
why the maintainer patches this file too when a field is renamed:
test fixtures and assertions must track the vendor spec.

The one thing the stub does NOT change is response["data"]: that
nesting change is flagged for human review in output/PR.md, so the
stub still returns "data" and the app still reads it in this demo.
"""

from app import get_meter_usage


class FakeMeterClient:
    last_kwargs = None

    def retrieve_meter_usage(self, **kwargs):
        FakeMeterClient.last_kwargs = kwargs
        return {
            "data_refreshed_at": "2025-09-01T00:00:00Z",
            "data": [
                {
                    "bucket_start_time": 1000,
                    "bucket_end_time": 2000,
                    "bucket_value": 42,
                    "meter_id": "mtr_123",
                }
            ],
        }


def test_get_meter_usage_uses_old_fields():
    client = FakeMeterClient()
    refreshed, rows = get_meter_usage(client, "mtr_123", 1000, 2000)
    assert FakeMeterClient.last_kwargs["start_time"] == 1000
    assert FakeMeterClient.last_kwargs["end_time"] == 2000
    assert FakeMeterClient.last_kwargs["meters"][0]["meter_id"] == "mtr_123"
    assert refreshed == "2025-09-01T00:00:00Z"
    assert rows[0]["start"] == 1000
    assert rows[0]["end"] == 2000
    assert rows[0]["value"] == 42
    assert rows[0]["meter"] == "mtr_123"
