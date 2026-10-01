"""On-demand CSV reports from the append-only EventSub JSONL log."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


COMMON_COLUMNS = (
    'log_line', 'received_at', 'run_id', 'message_timestamp', 'event_type', 'message_id',
    'subscription_id', 'user_id', 'user_login', 'user_name', 'broadcaster_user_id',
    'reason', 'timer_delta_seconds', 'requested_seconds',
)
SUB_COLUMNS = ('tier', 'is_gift', 'cumulative_months', 'duration_months', 'message')
GIFT_COLUMNS = ('tier', 'total', 'is_anonymous', 'cumulative_total')
BITS_COLUMNS = ('bits', 'message', 'power_up_type')
POINTS_COLUMNS = ('redemption_id', 'reward_id', 'reward_title', 'reward_cost',
                  'user_input', 'status', 'redeemed_at')
CSV_REPORTS = {
    'subscriptions.csv': (('channel.subscribe', 'channel.subscription.message'), SUB_COLUMNS),
    'gifted_subs.csv': (('channel.subscription.gift',), GIFT_COLUMNS),
    'bits.csv': (('channel.bits.use',), BITS_COLUMNS),
    'channelpoints.csv': (('channel.channel_points_custom_reward_redemption.add',), POINTS_COLUMNS),
    # The combined report also retains unrecognised event types.
    'events.csv': (None, tuple(dict.fromkeys(SUB_COLUMNS + GIFT_COLUMNS + BITS_COLUMNS + POINTS_COLUMNS))),
}


def _field(record, *keys):
    for key in keys:
        if not isinstance(record, dict):
            return ''
        record = record.get(key)
    return '' if record is None else record


def _csv_cell(value):
    # Keep user-supplied messages/names as text when opened in a spreadsheet.
    if isinstance(value, str) and (
            value.lstrip().startswith(('=', '+', '-', '@')) or
            value.startswith(('\t', '\r', '\n'))):
        return "'" + value
    return value


def export_csv_logs(jsonl_path):
    """Return (export directory, row counts, skipped line numbers).

    Read a snapshot before writing any reports. A malformed or unfinished line
    is reported as skipped; the JSONL source and previous exports stay intact.
    """
    source = Path(jsonl_path)
    # Bound the read so ongoing EventSub appends cannot extend this export.
    with source.open('rb') as log:
        snapshot = log.read(source.stat().st_size)
    rows, skipped = [], []
    for line_number, line in enumerate(snapshot.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, UnicodeError):
            skipped.append(line_number)
            continue
        # Configuration snapshots stay in JSONL; CSV reports contain timer events.
        if _field(record, 'record_type') == 'startup':
            continue
        if not isinstance(_field(record, 'payload', 'event'), dict):
            skipped.append(line_number)
            continue

        event = record['payload']['event']
        row = {column: _field(event, column) for column in
               set(SUB_COLUMNS + GIFT_COLUMNS + BITS_COLUMNS + POINTS_COLUMNS)}
        row.update(
            log_line=line_number, received_at=_field(record, 'received_at'),
            run_id=_field(record, 'run_id'),
            message_timestamp=_field(record, 'payload', 'metadata', 'message_timestamp'),
            event_type=(_field(record, 'payload', 'subscription', 'type') or
                        _field(record, 'payload', 'metadata', 'subscription_type')),
            message_id=_field(record, 'payload', 'metadata', 'message_id'),
            subscription_id=_field(record, 'payload', 'subscription', 'id'),
            user_id=_field(event, 'user_id'), user_login=_field(event, 'user_login'),
            user_name=_field(event, 'user_name'),
            broadcaster_user_id=_field(event, 'broadcaster_user_id'),
            reason=_field(record, 'reason'),
            timer_delta_seconds=_field(record, 'timer_delta_seconds'),
            requested_seconds=_field(record, 'requested_seconds'),
            message=_field(event, 'message', 'text'),
            power_up_type=_field(event, 'power_up', 'type'),
            redemption_id=_field(event, 'id'),
            reward_id=_field(event, 'reward', 'id'),
            reward_title=_field(event, 'reward', 'title'),
            reward_cost=_field(event, 'reward', 'cost'),
        )
        row['tier'] = {'1000': 1, '2000': 2, '3000': 3}.get(row['tier'], row['tier'])
        rows.append(row)

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    directory = source.parent / 'exports' / stamp
    directory.mkdir(parents=True)
    counts = {}
    for filename, (event_types, extra_columns) in CSV_REPORTS.items():
        columns = COMMON_COLUMNS + extra_columns
        counts[filename] = 0
        with (directory / filename).open('w', newline='', encoding='utf-8-sig') as output:
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                if event_types is None or row['event_type'] in event_types:
                    writer.writerow({column: _csv_cell(row[column]) for column in columns})
                    counts[filename] += 1
    return directory, counts, skipped
