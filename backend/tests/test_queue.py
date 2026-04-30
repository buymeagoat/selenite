import pytest
from app.queue import enqueue, _queue


def test_enqueue_puts_to_queue():
    while not _queue.empty():
        _queue.get_nowait()
        _queue.task_done()

    enqueue("test-job-id")
    assert _queue.qsize() == 1
    assert _queue.get_nowait() == "test-job-id"
    _queue.task_done()
