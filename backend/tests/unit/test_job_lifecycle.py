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
    manager.active_connections.append(ws)
    manager.jobs['j1'] = {'status': 'queued', 'progress': 0, 'last_message': ''}

    asyncio.run(manager.broadcast_progress('started', 10, 'j1'))
    asyncio.run(manager.broadcast_progress('done', 100, 'j1'))

    assert manager.jobs['j1']['status'] == 'completed'
    assert manager.jobs['j1']['progress'] == 100


def test_job_lifecycle_processing_error():
    manager = ConnectionManager()
    manager.jobs['j2'] = {'status': 'queued', 'progress': 0, 'last_message': ''}

    asyncio.run(manager.broadcast_progress('fail', -1, 'j2'))

    assert manager.jobs['j2']['status'] == 'error'
