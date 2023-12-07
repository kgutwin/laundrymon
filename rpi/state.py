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


class ChangeMixin:
    @property
    def changed(self):
        v = getattr(self, '_changed', False)
        self._changed = False
        return v

    @changed.setter
    def changed(self, value):
        self._changed = value


class AutoState(ChangeMixin):
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
                self.changed = True

            if all((
                self.washer_state == 'Running',
                self.washer.cycle_complete,
                not self.washer.lid_locked,
            )):
                self.washer_state = 'Done'
                self.washer_finished = time.monotonic()
                self.changed = True
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
                self.changed = True
                
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
            

class ManualState(ChangeMixin):
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
        self.changed = True

    def reset_washer(self):
        self.washer_state = 'Idle'
        self.washer_timeout = 0
        self.changed = True

    def start_dryer(self):
        self.dryer_state = 'Running'
        self.dryer_timeout = time.monotonic() + self.dryer_runtime
        self.changed = True

    def reset_dryer(self):
        self.dryer_state = 'Idle'
        self.dryer_timeout = 0
        self.changed = True

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
                self.changed = True
                self.alarm.alarm('Washer timer done')

            if self.dryer_timeout and time.monotonic() > self.dryer_timeout:
                self.dryer_state = 'Done'
                self.dryer_timeout = 0
                self.changed = True
                self.alarm.alarm('Dryer timer done')
                
            await sleep(1.0)


class AlarmState(ChangeMixin):
    def __init__(self):
        self.state = 'Idle'
        self.messages = set()
        self.snooze_until = None

    def alarm(self, message=None):
        self.state = 'Alarm'
        if message:
            self.messages.add(message)
        self.snooze_until = None
        self.changed = True

    def snooze(self, duration=30 * 60):
        if self.state != 'Alarm':
            return
        self.state = 'Snooze'
        self.snooze_until = time.monotonic() + duration
        self.changed = True

    def cancel(self):
        self.state = 'Idle'
        self.messages = set()
        self.changed = True

    @property
    def reported(self):
        return {
            "state": self.state,
            "snooze_until": self.snooze_until,
            "messages": sorted(list(self.messages)),
        }

    @property
    def desired(self):
        return self.reported

    def handle_delta(self, desired):
        if 'messages' in desired:
            self.messages = set(desired['messages'])
            self.changed = True
            
        if 'state' in desired:
            if desired['state'] == 'Idle':
                self.cancel()
            elif desired['state'] == 'Alarm':
                self.alarm()
            elif desired['state'] == 'Snooze':
                if 'snooze_until' in desired:
                    duration = desired['snooze_until'] - time.monotonic()
                self.snooze(duration)
    
    async def update(self):
        while True:
            if (
                    self.state == 'Snooze' and self.snooze_until
                    and time.monotonic() > self.snooze_until
            ):
                self.state = 'Alarm'
                self.snooze_until = None
                
            await sleep(5.0)

            
class State(ChangeMixin):
    def __init__(self):
        self.alarm_state = AlarmState()
        self.auto_state = AutoState(self.alarm_state)
        self.manual_state = ManualState(self.alarm_state)
        self.mode = 'Auto'
        self.max_free_mem = gc.mem_free()
        self.max_free_mem_time = time.monotonic()
        self.last_tickle = time.monotonic()

    @property
    def awake(self):
        if self.alarm_state.state == 'Alarm':
            return True
        
        if self.mode == 'Auto':
            if self.auto_state.washer_state != 'Idle':
                return True
            
        if self.mode == 'Manual':
            if self.manual_state.washer_state != 'Idle':
                return True
            if self.manual_state.dryer_state != 'Idle':
                return True
            
        return time.monotonic() < self.last_tickle + (5.0 * 60)

    def tickle(self):
        self.last_tickle = time.monotonic()

    def set_mode(self, mode):
        self.mode = mode
        self.changed = True
        
    def should_report_now(self):
        return any([
            self.changed,
            self.alarm_state.changed,
            self.auto_state.changed,
            self.manual_state.changed,
        ])
        
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

    def handle_delta(self, msg):
        desired = msg['state']
        if 'alarm' in desired:
            self.alarm_state.handle_delta(desired['alarm'])
