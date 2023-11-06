import board

class Display:
    CLK = board.GP6
    MISO = board.GP4
    MOSI = board.GP7
    CS = board.GP5
    DC = board.GP3
    RST = board.GP8
    Lite = board.GP9

class Touch:
    IRQ = board.GP2
    SDA = board.GP0
    SCL = board.GP1

BACK_BUTTON = board.GP19
