import gc
#import time
from asyncio import sleep
from array import array
import bitmaptools
import displayio
import terminalio
import vectorio
import wifi
#from adafruit_display_shapes.line import Line
from adafruit_display_shapes.roundrect import RoundRect
#from adafruit_display_shapes.sparkline import Sparkline
from adafruit_display_text.bitmap_label import Label

from display import display, backlight, touch_screen_point, back_button, beep


palette = displayio.Palette(8)
BLACK_V = palette[0] = 0
WHITE_V = palette[1] = 0xFFFFFF
RED_V = palette[2] = 0xFF0000
GREEN_V = palette[3] = 0x00FF00
BLUE_V = palette[4] = 0x0000FF
YELLOW_V = palette[5] = 0x888800
BLACK_I, WHITE_I, RED_I, GREEN_I, BLUE_I, YELLOW_I = range(6)

LEFT, CENTER, RIGHT = 0, 0.5, 1

def label(text, pos, color=WHITE_V, scale=1, align=LEFT):
    rv = Label(
        terminalio.FONT,
        text=text,
        color=color,
        scale=scale
    )
    if align != LEFT:
        rv.anchor_point = (align, 0.5)
        rv.anchored_position = pos
    else:
        rv.x, rv.y = pos
    return rv

WIFI_ICON = [
    '  ..####..    ',
    '.#^^ .. ^^#.  ',
    '^ .##^^##. ^  ',
    '  ^ .##. ^    ',
    '    ^  ^      ',
    '     ##       ',
    '              ',    
]


def icon(rows, background=0):
    width, height = len(rows[0]), len(rows) * 2
    bitmap = displayio.Bitmap(width, height, 8)
    buf = array('b')
    for row in rows:
        for c in row:
            buf.append(1 if c in '^#' else background)
        for c in row:
            buf.append(1 if c in '.#' else background)
    bitmaptools.arrayblit(bitmap, buf)
    return bitmap


class WifiIcon:
    wifi_icon_bitmap = icon(WIFI_ICON, background=BLUE_I)
    
    def __init__(self):
        self.group = displayio.Group(x=280, y=4)
        self.group.append(displayio.TileGrid(
            self.wifi_icon_bitmap, pixel_shader=palette, x=0, y=0
        ))

    def set_status(self, status):
        self.group.hidden = not status


class ConfirmBox:
    def __init__(self, message):
        self.group = displayio.Group(x=10, y=60)
        self.group.append(vectorio.Rectangle(
            pixel_shader=palette,
            width=300, height=120,
            x=0, y=0, color_index=WHITE_I
        ))
        self.group.append(vectorio.Rectangle(
            pixel_shader=palette,
            width=296, height=116,
            x=2, y=2, color_index=BLACK_I
        ))
        self.group.append(label(message, (150, 20), align=CENTER))
        # TODO: memory save: pay close attention to memory used by
        # RoundRect, replace with boring vectorio.Rectangle if needed
        confirm = RoundRect(
            x=60, y=70, width=80, height=30, r=3,
            fill=GREEN_V, outline=WHITE_V, stroke=1
        )
        self.group.append(confirm)
        self.group.append(
            label('Confirm', (100, 85), color=BLACK_V, align=CENTER)
        )
        cancel = RoundRect(
            x=170, y=70, width=80, height=30, r=3,
            fill=RED_V, outline=WHITE_V, stroke=1
        )
        self.group.append(cancel)
        self.group.append(label('Cancel', (210, 85), align=CENTER))

    def touch_zones(self, confirm, cancel):
        def do_confirm():
            confirm()
            cancel()
            
        return {
            (45, 125, 135, 165): do_confirm,
            (155, 125, 245, 165): cancel,
        }
        

class Page:
    def __init__(self, title):
        self.group = displayio.Group()
        top_bar = displayio.Group()
        top_bar_bg = vectorio.Rectangle(
            pixel_shader=palette,
            width=320, height=20,
            x=0, y=0, color_index=BLUE_I
        )
        top_bar.append(top_bar_bg)
        top_bar.append(label(title, (160, 9), align=CENTER))
        top_bar.append(label('<', (4, 9)))
        top_bar.append(label('>', (316, 9), align=RIGHT))
        self.wifi = WifiIcon()
        top_bar.append(self.wifi.group)
        self.group.append(top_bar)
        #self.group.append(Line(160, 20, 160, 240, WHITE))
        self.touch_zones = {}

    def update(self):
        pass

    def touch(self, pos):
        for rect in self.touch_zones:
            if rect[0] <= pos.x <= rect[2] and rect[1] <= pos.y <= rect[3]:
                beep()
                self.touch_zones[rect]()
                return True
            
        return False


class PageStandard(Page):
    def __init__(self, title):
        super().__init__(title)
        self.left_bg = vectorio.Rectangle(
            pixel_shader=palette,
            width=160, height=220,
            x=0, y=20
        )
        self.right_bg = vectorio.Rectangle(
            pixel_shader=palette,
            width=160, height=220,
            x=160, y=20
        )
        self.group.append(self.left_bg)
        self.group.append(self.right_bg)
        
        self.group.append(label('Washer', (80, 40), scale=2, align=CENTER))

        self.group.append(label('Status:', (80, 100), align=CENTER))
        self.washer_status = label('Idle', (80, 120), align=CENTER)
        self.washer_status_waiting = label(
            'Waiting for Dryer', (80, 136), align=CENTER
        )
        self.group.append(self.washer_status)

        self.washer_status_elapsed = label(
            'Elapsed time:', (80, 180), align=CENTER
        )
        self.washer_status_elapsed_time = label(
            '10h 39m 20s', (80, 200), align=CENTER
        )

        self.group.append(label('Dryer', (240, 40), scale=2, align=CENTER))

        self.group.append(label('Status:', (240, 100), align=CENTER))
        self.dryer_status = label('Idle', (240, 120), align=CENTER)
        self.group.append(self.dryer_status)
        
        self.dryer_status_elapsed = label(
            'Elapsed time:', (240, 180), align=CENTER
        )
        self.dryer_status_elapsed_time = label(
            '10h 39m 20s', (240, 200), align=CENTER
        )

    def set_washer_state(self, state, waiting=False):
        if state != self.washer_status.text:
            self.washer_status.text = state
            if state == 'Idle':
                self.left_bg.color_index = BLACK_I
            elif state == 'Running':
                self.left_bg.color_index = GREEN_I
            elif state == 'Done' and waiting:
                self.left_bg.color_index = YELLOW_I
            elif state == 'Done' and not waiting:
                self.left_bg.color_index = RED_I
            
        if waiting and self.washer_status_waiting not in self.group:
            self.group.append(self.washer_status_waiting)
        elif not waiting and self.washer_status_waiting in self.group:
            self.group.remove(self.washer_status_waiting)

    def set_washer_elapsed(self, elapsed):
        if not elapsed:
            if self.washer_status_elapsed in self.group:
                self.group.remove(self.washer_status_elapsed)
                self.group.remove(self.washer_status_elapsed_time)
        else:
            if self.washer_status_elapsed not in self.group:
                self.group.append(self.washer_status_elapsed)
                self.group.append(self.washer_status_elapsed_time)
            self.washer_status_elapsed_time.text = elapsed
    
    def set_dryer_state(self, state):
        if state != self.dryer_status.text:
            self.dryer_status.text = state
            if state == 'Idle':
                self.right_bg.color_index = BLACK_I
            elif state == 'Running':
                self.right_bg.color_index = GREEN_I
            elif state == 'Done':
                self.right_bg.color_index = RED_I
            
    def set_dryer_elapsed(self, elapsed):
        if not elapsed:
            if self.dryer_status_elapsed in self.group:
                self.group.remove(self.dryer_status_elapsed)
                self.group.remove(self.dryer_status_elapsed_time)
        else:
            if self.dryer_status_elapsed not in self.group:
                self.group.append(self.dryer_status_elapsed)
                self.group.append(self.dryer_status_elapsed_time)
            self.dryer_status_elapsed_time.text = elapsed
            
        
class PageAuto(PageStandard):
    def __init__(self, auto_state):
        super().__init__('Auto')
        self.auto_state = auto_state

    def update(self):
        self.set_washer_state(self.auto_state.washer_state)
        self.set_washer_elapsed(self.auto_state.washer_elapsed)
        
        
class PageStats(Page):
    def __init__(self, state):
        super().__init__('Stats')
        self.state = state
        self.group.append(label('Mem Alloc:', (10, 100)))
        self.group.append(label('Mem Free:', (10, 120)))
        self.mem_alloc = label('', (100, 100))
        self.mem_free = label('', (100, 120))
        #self.mem_sparkline = Sparkline(
        #    width=160, height=40, max_items=64, y_min=0, y_max=65535,
        #    x=150, y=100
        #)
        self.group.append(self.mem_alloc)
        self.group.append(self.mem_free)
        #self.group.append(self.mem_sparkline)

        self.group.append(label('Washer Sensors:', (10, 150)))
        self.washer_sensors = label('', (100, 150))
        self.group.append(self.washer_sensors)
        
    def update(self):
        self.mem_alloc.text = str(gc.mem_alloc())
        self.mem_free.text = str(self.state.max_free_mem)
        #display.auto_refresh = False
        #self.mem_sparkline.add_value(gc.mem_free())
        #display.auto_refresh = True
        self.washer_sensors.text = ' '.join(
            f'{i.value}' for i in (
                self.state.auto_state.washer.cycle_complete_raw,
                self.state.auto_state.washer.blank_raw,
                self.state.auto_state.washer.lid_locked_raw,
            )
        )


class PageManual(PageStandard):
    
    def __init__(self, manual_state):
        super().__init__('Manual')
        self.manual_state = manual_state
        self.default_touch_zones = self.touch_zones = {
            (0, 30, 160, 240): self.touch_washer,
            (160, 30, 320, 240): self.touch_dryer,
        }
        self.washer_status_elapsed.text = 'Remaining:'
        self.dryer_status_elapsed.text = 'Remaining:'
        self.confirm = None

    def update(self):
        self.set_washer_state(self.manual_state.washer_state)
        self.set_washer_elapsed(self.manual_state.washer_remaining)
        self.set_dryer_state(self.manual_state.dryer_state)
        self.set_dryer_elapsed(self.manual_state.dryer_remaining)

    def close_confirm(self):
        if self.confirm:
            # something weird, if you just remove the group, sometimes
            # fragments of it remain. This seems to consistently work.
            self.confirm.group.hidden = True
            display.refresh()
            self.group.remove(self.confirm.group)
            self.touch_zones = self.default_touch_zones
            self.confirm = None
        
    def touch_washer(self):
        if self.manual_state.washer_state == 'Idle':
            self.manual_state.start_washer()
        elif self.manual_state.washer_state == 'Done':
            self.manual_state.reset_washer()
        elif self.manual_state.washer_state == 'Running':
            self.confirm = ConfirmBox(
                'Are you sure you want to stop the washer timer?'
            )
            self.group.append(self.confirm.group)
            self.touch_zones = self.confirm.touch_zones(
                confirm=self.manual_state.reset_washer,
                cancel=self.close_confirm
            )

    def touch_dryer(self):
        if self.manual_state.dryer_state == 'Idle':
            self.manual_state.start_dryer()
        elif self.manual_state.dryer_state == 'Done':
            self.manual_state.reset_dryer()
        elif self.manual_state.dryer_state == 'Running':
            self.confirm = ConfirmBox(
                'Are you sure you want to stop the dryer timer?'
            )
            self.group.append(self.confirm.group)
            self.touch_zones = self.confirm.touch_zones(
                confirm=self.manual_state.reset_dryer,
                cancel=self.close_confirm
            )

            
def show_console():
    backlight.value = True
    display.show(displayio.CIRCUITPYTHON_TERMINAL)

            
class UI:
    def __init__(self, state):
        self.state = state
        self._set_page(0)

    def _set_page(self, index):
        self.page_index = index
        gc.collect()
        if index == 0:
            self.page = PageAuto(self.state.auto_state)
            self.state.set_mode('Auto')
        elif index == 1:
            self.page = PageStats(self.state)
        elif index == 2:
            self.page = PageManual(self.state.manual_state)
            self.state.set_mode('Manual')
        display.show(self.page.group)
        gc.collect()

    async def run(self):
        touched = False
        back_button_released = back_button.value
        while True:
            backlight.value = self.state.awake
            self.page.wifi.set_status(wifi.radio.connected)
            display.auto_refresh = False
            self.page.update()
            display.auto_refresh = True
            if touch := touch_screen_point():
                self.state.tickle()
                if touched:
                    pass
                elif not self.state.awake:
                    touched = True
                elif touch.x < 30 and touch.y < 30:
                    beep()
                    self._set_page((self.page_index - 1) % 3)
                    touched = True
                elif touch.x > 210 and touch.y < 30:
                    beep()
                    self._set_page((self.page_index + 1) % 3)
                    touched = True
                else:
                    touched = self.page.touch(touch)
                    
            else:
                touched = False

            if back_button.value == False:
                if back_button_released:
                    display.show(displayio.CIRCUITPYTHON_TERMINAL)
                    print('Reset...')
                    
                    await sleep(0.15)
                    
                    import microcontroller

                    microcontroller.reset()
            else:
                back_button_released = True

            await sleep(0.15)
