import busio
import displayio
import adafruit_ili9341

from pins import Display

spi = busio.SPI(Display.CLK, Display.MOSI, Display.MISO)
display_bus = displayio.FourWire(
    spi, command=Display.DC, chip_select=Display.CS
)

display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240)
display.show(displayio.CIRCUITPYTHON_TERMINAL)
