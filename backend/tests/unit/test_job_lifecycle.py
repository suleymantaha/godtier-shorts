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


def test_job_lifecycle_persists_download_progress_metadata():
    manager = ConnectionManager()
    ws = DummyWs()
    manager.active_connections[ws] = "subject-a"
    manager.jobs['j3'] = {'job_id': 'j3', 'status': 'queued', 'progress': 0, 'last_message': '', 'subject': 'subject-a'}

    asyncio.run(manager.broadcast_progress(
        'indiriliyor',
        15,
        'j3',
        'processing',
        extra={
            'download_progress': {
                'phase': 'download',
                'downloaded_bytes': 1024,
                'total_bytes': 2048,
                'percent': 50,
                'speed_text': '1.00MiB/s',
                'eta_text': '00:03',
                'status': 'downloading',
            },
        },
    ))

    assert manager.jobs['j3']['download_progress']['percent'] == 50.0
    assert manager.jobs['j3']['timeline'][0]['download_progress']['downloaded_bytes'] == 1024
    assert ws.sent[0]['download_progress']['eta_text'] == '00:03'
