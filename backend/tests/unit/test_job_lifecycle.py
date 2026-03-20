import asyncio

from backend.api.websocket import ConnectionManager


class DummyWs:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


def test_job_lifecycle_queued_processing_completed():
    manager = ConnectionManager()
    ws = DummyWs()
    manager.active_connections[ws] = "subject-a"
    manager.jobs['j1'] = {'job_id': 'j1', 'status': 'queued', 'progress': 0, 'last_message': '', 'subject': 'subject-a'}
    manager.seed_job_timeline('j1', message='queued', progress=0, status='queued', source='api')

    asyncio.run(manager.broadcast_progress('started', 10, 'j1'))
    asyncio.run(manager.broadcast_progress('done', 100, 'j1'))

    assert manager.jobs['j1']['status'] == 'completed'
    assert manager.jobs['j1']['progress'] == 100
    assert [event['id'] for event in manager.jobs['j1']['timeline']] == ['j1:queued', ws.sent[0]['event_id'], ws.sent[1]['event_id']]
    assert ws.sent[0]['status'] == 'queued'
    assert ws.sent[1]['status'] == 'completed'
    assert ws.sent[1]['source'] == 'worker'


def test_job_lifecycle_processing_error():
    manager = ConnectionManager()
    manager.jobs['j2'] = {'job_id': 'j2', 'status': 'queued', 'progress': 0, 'last_message': '', 'subject': 'subject-a'}

    asyncio.run(manager.broadcast_progress('fail', -1, 'j2'))

    assert manager.jobs['j2']['status'] == 'error'
    assert manager.jobs['j2']['timeline'][0]['status'] == 'error'
