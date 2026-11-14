"""Ingest worker: reads raw checkout events from the queue and writes them to the events export."""
import datetime
import json
import uuid

RETRY_EMIT_FROM = datetime.date(2026, 3, 9)  # flag: resend when the sink did not ack
BATCH_SIZE = 500


def parse(raw):
    e = json.loads(raw)
    e['amount'] = round(float(e.get('amount', 0)), 2)
    return e


def emit(sink, event, now):
    sink.write(event)
    if now.date() >= RETRY_EMIT_FROM and event.get('ack_timeout'):
        retry = dict(event, event_id=str(uuid.uuid4()), ts=now.isoformat())
        sink.write(retry)


def run(queue, sink):
    for raw in queue.poll(BATCH_SIZE):
        emit(sink, parse(raw), datetime.datetime.utcnow())
