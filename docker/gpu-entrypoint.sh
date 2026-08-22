#!/bin/sh
set -eu

python -m backend.workers.gpu_entrypoint
exec python -m arq backend.workers.gpu_worker.WorkerSettings
