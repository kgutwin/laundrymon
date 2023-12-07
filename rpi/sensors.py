import time
import analogio
import microcontroller

from pins import Washer as WasherPins
from pins import Dryer as DryerPins


#def dft(x):
#    import math
#
#    N, yr, yi = len(x), [], []
#    for k in range(N):
#        real, imag = 0, 0
#        for n in range(N):
#            theta = -k * (2 * math.pi) * (float(n) / N)
#            real += x[n] * math.cos(theta)
#            imag += x[n] * math.sin(theta)
#        yr.append(real / N)
#        yi.append(imag / N)
#    return yr, yi


class MaxValue:
    period = 2.0
    
    def __init__(self, pin):
        self.current = analogio.AnalogIn(pin)
        self.history = []

    #def analyze(self):
    #    l = []
    #    end = 0
    #    start = time.monotonic_ns()
    #    while end < start + 100_000_000:
    #        microcontroller.delay_us(300)
    #        l.append(self.current.value)
    #        end = time.monotonic_ns()
    #    print('duration:', end - start)
    #    print('samples :', len(l))
    #    yr, yi = dft(l)
    #    syr = sorted([(v, i) for i, v in enumerate(yr[:len(l)//2])])
    #    print('syr[-4:]:', syr[-4:])
        
    @property
    def value(self):
        # after some analysis, I think that the light frequency is 250 Hz
        val = self.current.value
        for i in range(9):
            microcontroller.delay_us(1100)
            val = max(val, self.current.value)
            
        now = time.monotonic()
        oldest = now - self.period
        rv = val
        new_history = []
        for i in self.history:
            v, t = i
            if t > oldest and v >= val:
                new_history.append(i)
                rv = max(rv, v)
                
        new_history.append((val, now))
        self.history = new_history
        return rv


class Washer:
    def __init__(self):
        self.cycle_complete_raw = MaxValue(WasherPins.CYCLE_COMPLETE)
        self.blank_raw = MaxValue(WasherPins.BLANK)
        self.lid_locked_raw = MaxValue(WasherPins.LID_LOCKED)

    @property
    def cycle_complete(self):
        return self.cycle_complete_raw.value > (self.blank_raw.value * 1.7)

    @property
    def lid_locked(self):
        return self.lid_locked_raw.value > (self.blank_raw.value * 4)
