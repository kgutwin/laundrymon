from asyncio import gather, run

import ui
import state
import iot


async def main():
    main_state = state.State()
    cloud = iot.IOT(main_state)
    interface = ui.UI(main_state, cloud, console=False)

    await gather(
        main_state.update(),
        interface.run(),
        cloud.run(),
    )

    
run(main())

#import time
#import board
#import analogio
#
#import busio
#import displayio
#import adafruit_ili9341
#
#from pins import Display
#
#spi = busio.SPI(Display.CLK, Display.MOSI, Display.MISO)
#
#display_bus = displayio.FourWire(
#    spi, command=Display.DC, chip_select=Display.CS
#)
#
#display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240)
#display.show(displayio.CIRCUITPYTHON_TERMINAL)
#
#inputs = [
#    analogio.AnalogIn(i)
#    for i in (board.GP26_A0, board.GP27_A1, board.GP28_A2)
#]
#
#while True:
#    last_sec = int(time.monotonic())
#    v = [i.value for i in inputs]
#    while last_sec == int(time.monotonic()):
#        n = [i.value for i in inputs]
#        v = [max(i, j) for i, j in zip(v, n)]
#    print(v)

