import collections
import random
import time
import busio
import digitalio
import displayio
import adafruit_ili9341
import adafruit_focaltouch

from pins import Display, Touch, BACK_BUTTON

# display backlight
backlight = digitalio.DigitalInOut(Display.Lite)
backlight.switch_to_output()
backlight.value = False

# touch
i2c = busio.I2C(Touch.SCL, Touch.SDA)
ft = adafruit_focaltouch.Adafruit_FocalTouch(i2c, debug=False)

Point = collections.namedtuple('Point', ['x', 'y'])

def touch_screen_point():
    touches = ft.touches[:]
    if not touches:
        return None
    
    touch = touches[0]
    return Point(x=(320 - touch['y']), y=touch['x'])

# display
displayio.release_displays()

spi = busio.SPI(Display.CLK, Display.MOSI, Display.MISO)

display_bus = displayio.FourWire(
    spi, command=Display.DC, chip_select=Display.CS
)

display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240)

# back button
back_button = digitalio.DigitalInOut(BACK_BUTTON)
back_button.switch_to_input(digitalio.Pull.UP)
