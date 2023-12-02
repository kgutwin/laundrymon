import gc
import time
from asyncio import sleep, gather

import sensors


def duration_str(s):
    if s <= 0:
        return ''
    s = int(s)
    
    rv = ''
    if s > 3600:
        rv += str(s // 3600) + 'h '
        s %= 3600
    rv += str(s // 60) + 'm ' + str(s % 60) + 's'
    return rv


class AutoState:
    def __init__(self, alarm):
        self.alarm = alarm
        self.washer = sensors.Washer()
        self.washer_state = 'Idle'
        self.washer_started = None
        self.washer_finished = None

    @property
    def reported(self):
        return {
            "washer": { 
                "state": self.washer_state,
                "washer_started": self.washer_started,
                "washer_finished": self.washer_finished,
                "lid_locked": self.washer.lid_locked,
                "cycle_complete": self.washer.cycle_complete,
                "raw": {
                    "lid_locked": self.washer.lid_locked_raw.value,
                    "cycle_complete": self.washer.cycle_complete_raw.value,
                    "blank": self.washer.blank_raw.value,
                }
            }
        }
        
    async def update(self):
        while True:
            if self.washer_state == 'Idle' and self.washer.lid_locked:
                self.washer_state = 'Running'
                self.washer_started = time.monotonic()

            if all((
                self.washer_state == 'Running',
                self.washer.cycle_complete,
                not self.washer.lid_locked,
            )):
                self.washer_state = 'Done'
                self.washer_finished = time.monotonic()
                self.alarm.alarm('Washer cycle complete')

            # it really shouldn't go idle until the dryer starts, but...
            if all((
                self.washer_state == 'Done',
                not self.washer.cycle_complete,
                not self.washer.lid_locked,
            )):
                self.washer_state = 'Idle'
                self.washer_started = None
                self.washer_finished = None
                
            await sleep(1.0)

    @property
    def washer_elapsed(self):
        if not self.washer_started:
            return ''
        
        if self.washer_finished:
            d = self.washer_finished - self.washer_started
        else:
            d = time.monotonic() - self.washer_started
            
        return duration_str(d)
            

class ManualState:
    def __init__(self, alarm):
        self.alarm = alarm
        self.washer_state = 'Idle'
        self.dryer_state = 'Idle'
        self.washer_runtime = 60 * 60
        self.dryer_runtime = 60 * 60
        self.washer_timeout = 0
        self.dryer_timeout = 0

    @property
    def reported(self):
        return {
            "washer": {
                "state": self.washer_state,
            },
            "dryer": {
                "state": self.dryer_state,
            }
        }
        
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
        return duration_str(self.washer_timeout - time.monotonic())
        
    @property
    def dryer_remaining(self):
        if self.dryer_timeout == 0:
            return ''
        return duration_str(self.dryer_timeout - time.monotonic())
    
    async def update(self):
        while True:
            if self.washer_timeout and time.monotonic() > self.washer_timeout:
                self.washer_state = 'Done'
                self.washer_timeout = 0
                self.alarm.alarm('Washer timer done')

            if self.dryer_timeout and time.monotonic() > self.dryer_timeout:
                self.dryer_state = 'Done'
                self.dryer_timeout = 0
                self.alarm.alarm('Dryer timer done')
                
            await sleep(1.0)


class AlarmState:
    def __init__(self):
        self.state = 'Idle'
        self.messages = set()
        self.snooze_until = None

    def alarm(self, message):
        self.state = 'Alarm'
        self.messages.add(message)
        self.snooze_until = None

    def snooze(self, duration=30 * 60):
        if self.state != 'Alarm':
            return
        self.state = 'Snooze'
        self.snooze_until = time.monotonic() + duration

    def cancel(self):
        self.state = 'Idle'
        self.messages = set()

    @property
    def reported(self):
        return {
            "state": self.state,
            "snooze_until": self.snooze_until,
            "messages": sorted(list(self.messages)),
        }

    async def update(self):
        while True:
            if (
                    self.state == 'Snooze' and self.snooze_until
                    and time.monotonic() > self.snooze_until
            ):
                self.state = 'Alarm'
                self.snooze_until = None
                
            await sleep(5.0)

            
class State:
    def __init__(self):
        self.alarm_state = AlarmState()
        self.auto_state = AutoState(self.alarm_state)
        self.manual_state = ManualState(self.alarm_state)
        self.mode = 'Manual'
        self.max_free_mem = gc.mem_free()
        self.max_free_mem_time = time.monotonic()
        self.last_tickle = time.monotonic()

    @property
    def awake(self):
        return time.monotonic() < self.last_tickle + (5.0 * 60)

    def tickle(self):
        self.last_tickle = time.monotonic()
        
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
            self.manual_state.update(),
            self.auto_state.update()
        )
