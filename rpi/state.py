import gc
import time
from asyncio import sleep, gather


class ManualState:
    def __init__(self):
        self.washer_state = 'Idle'
        self.dryer_state = 'Idle'
        self.washer_runtime = 60 * 60
        self.dryer_runtime = 60 * 60
        self.washer_timeout = 0
        self.dryer_timeout = 0
        
    def start_washer(self):
        self.washer_state = 'Running'
        self.washer_timeout = time.monotonic() + self.washer_runtime

    def reset_washer(self):
        self.washer_state = 'Idle'
        self.washer_timeout = 0

    def start_dryer(self):
        self.dryer_state = 'Running'
        self.dryer_timeout = time.monotonic() + self.dryer_runtime

    def reset_dryer(self):
        self.dryer_state = 'Idle'
        self.dryer_timeout = 0

    @property
    def washer_remaining(self):
        if self.washer_timeout == 0:
            return ''

        rv = ''
        remain = int(self.washer_timeout - time.monotonic())
        if remain > 3600:
            rv += str(remain // 3600) + 'h '
            remain %= 3600
        rv += str(remain // 60) + 'm ' + str(remain % 60) + 's'
        return rv
        
    @property
    def dryer_remaining(self):
        if self.dryer_timeout == 0:
            return ''

        rv = ''
        remain = int(self.dryer_timeout - time.monotonic())
        if remain > 3600:
            rv += str(remain // 3600) + 'h '
            remain %= 3600
        rv += str(remain // 60) + 'm ' + str(remain % 60) + 's'
        return rv
    
    async def update(self):
        while True:
            if self.washer_timeout and time.monotonic() > self.washer_timeout:
                self.washer_state = 'Done'
                self.washer_timeout = 0

            if self.dryer_timeout and time.monotonic() > self.dryer_timeout:
                self.dryer_state = 'Done'
                self.dryer_timeout = 0
                
            await sleep(1.0)


class State:
    def __init__(self):
        self.manual_state = ManualState()
        self.mode = 'Manual'
        self.max_free_mem = gc.mem_free()
        self.max_free_mem_time = time.monotonic()

    async def local_update(self):
        while True:
            if time.monotonic() > self.max_free_mem_time + 5:
                self.max_free_mem = gc.mem_free()
                self.max_free_mem_time = time.monotonic()
            else:
                self.max_free_mem = max(self.max_free_mem, gc.mem_free())

            await sleep(0.1)
        
    async def update(self):
        await gather(
            self.local_update(),
            self.manual_state.update()
        )
