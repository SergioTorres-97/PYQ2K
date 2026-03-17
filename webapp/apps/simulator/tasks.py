import threading
from .services import execute_run, execute_pipeline


def launch_run_async(run_pk: int):
    t = threading.Thread(target=execute_run, args=(run_pk,), daemon=True)
    t.start()


def launch_pipeline_async(pipeline_pk: int):
    t = threading.Thread(target=execute_pipeline, args=(pipeline_pk,), daemon=True)
    t.start()
