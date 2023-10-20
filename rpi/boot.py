import board
import digitalio
import storage


# check for local load
local_load = digitalio.DigitalInOut(board.D1)  # TODO: assign pin

local_load.direction = digitalio.Direction.INPUT
local_load.pull = digitalio.Pull.UP

# if local_load is not low (value is True) then remount as readonly
storage.remount("/", local_load.value)

