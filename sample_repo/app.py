"""Sample app: a billing helper that reads Stripe meter usage.

This is the 'customer repo' the maintainer watches. It intentionally
uses the OLD Billing Meter Usage field names from before Stripe's
2025-09-30 change: start_time, end_time, meter_id, data_refreshed_at,
bucket_start_time, bucket_end_time, bucket_value.

Note the docstring above mentions those old names on purpose: the
v2 maintainer patches ONLY AST call/dict/subscript sites, so this
docstring is deliberately left untouched. v1's global string replace
would have rewritten it. A human reviewer updates docs separately.

The client here is a thin wrapper in the tests (stubbed, no network,
no API keys). In a real repo this would be the Stripe SDK's
Billing Meter Usage retrieve call.
"""


def get_meter_usage(client, meter_id, start_time, end_time):
    response = client.retrieve_meter_usage(
        starts_at=start_time,
        ends_at=end_time,
        meters=[{"meter": meter_id}],
    )
    refreshed = response["refreshed_at"]
    rows = []
    # NOTE: response["data"] is a structural change in the new API -
    # data is now nested inside "rows". The maintainer flags this for
    # human review and does NOT auto-patch it. See output/PR.md.
    for row in response["data"]:
        rows.append({
            "start": row["starts_at"],
            "end": row["ends_at"],
            "value": row["value"],
            "meter": row["meter"],
        })
    return refreshed, rows
