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

PIEZO_L = board.GP11
PIEZO_R = board.GP13

class Washer:
    CYCLE_COMPLETE = board.GP28_A2
    BLANK = board.GP27_A1
    LID_LOCKED = board.GP26_A0

class Dryer:
    TXD = board.GP21
    RXD = board.GP20
