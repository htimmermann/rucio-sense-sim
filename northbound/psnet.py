import time
import yaml
from threading import Lock
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

psnet = FastAPI()
lock = Lock()

connections = {}

with open("config.yaml", "r") as f_in:
    config = yaml.safe_load(f_in).get("psnet", {})
    time_dilation = config.get("time_dilation", 1.0)

def now():
    return time_dilation*(time.time_ns()/10**9)

class Promise:
    def __init__(self, bandwidth):
        self.bandwidth = bandwidth
        self.start_time = now()
        self.end_time = None

    @property
    def bytes(self):
        return self.duration*self.bandwidth

    @property
    def duration(self):
        if not self.start_time:
            return 0
        elif not self.end_time:
            return now() - self.start_time
        else:
            return self.end_time - self.start_time

class Connection:
    def __init__(self, nonsense_id, total_data):
        self.total_data = total_data
        self.nonsense_id = nonsense_id
        self.promises = []

    @property
    def end_time(self):
        data_remaining = self.total_data
        for promise in self.promises[:-1]:
            data_remaining -= promise.bytes
        return self.promises[-1].start_time + data_remaining/self.promises[-1].bandwidth

    @property
    def is_finished(self):
        return self.end_time <= now()

    def update(self, bandwidth):
        promise = Promise(bandwidth)
        if len(self.promises) > 0:
            self.promises[-1].end_time = promise.start_time
        self.promises.append(promise)

@psnet.get("/connections/")
async def check_connection(burro_id: str, src: str, dst: str):
    """
    Check status of PSNet Connection

    - **burro_id**: identifier for connection from Burro (rule ID)
    - **src**: name of source site (RSE name)
    - **dst**: name of destination site (RSE name)
    """
    nonsense_id = f"{burro_id}_{src}_{dst}"
    if nonsense_id not in connections:
        raise HTTPException(
            status_code=404,
            detail=f"connection with {nonsense_id} not found"
        )
    else:
        return {"result": connections[nonsense_id].is_finished}

@psnet.post("/connections/")
async def create_connection(burro_id: str, src: str, dst: str, total_data: float):
    """
    Create PSNet Connection

    - **burro_id**: identifier for connection from Burro (rule ID)
    - **src**: name of source site (RSE name)
    - **dst**: name of destination site (RSE name)
    - **total_data**: total amount of data to be transfered from src to dst in bytes
    """
    lock.acquire()
    nonsense_id = f"{burro_id}_{src}_{dst}"
    connections[nonsense_id] = Connection(nonsense_id, total_data)
    lock.release()

@psnet.put("/connections/")
async def update_connection(nonsense_id: str, bandwidth: float):
    """
    Update PSNet Connection with a given ID with new bandwidth

    - **nonsense_id**: identifier for connection from NONSENSE
    - **bandwidth**: bandwidth provision in bytes/sec
    """
    lock.acquire()
    connections[nonsense_id].update(bandwidth)
    lock.release()