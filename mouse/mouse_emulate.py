#!/usr/bin/python3

import sys
import dbus
import dbus.service
import dbus.mainloop.glib

class MouseClient():
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object(
            'org.thanhle.btkbservice', '/org/thanhle/btkbservice')
        self.iface = dbus.Interface(self.btkservice, 'org.thanhle.btkbservice')

    def send_absolute(self, buttons, x, y, wheel):
        # X and Y are 16-bit values (0-32767)
        # Split into Low and High bytes (Little Endian)
        x_low = x & 0xFF
        x_high = (x >> 8) & 0xFF
        y_low = y & 0xFF
        y_high = (y >> 8) & 0xFF
        
        # Structure: [Buttons, X_low, X_high, Y_low, Y_high, Wheel]
        state = [buttons, x_low, x_high, y_low, y_high, wheel]
        
        try:
            self.iface.send_mouse(0, bytes(state))
        except OSError as err:
            print(err)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: mouse_emulate [buttons] [x 0-32767] [y 0-32767] [wheel]")
        print("Example: mouse_emulate 0 16384 16384 0  (Moves to center)")
        exit()

    buttons = int(sys.argv[1])
    x = int(sys.argv[2])
    y = int(sys.argv[3])
    wheel = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    client = MouseClient()
    print(f"Sending Absolute Mouse: Buttons={buttons}, X={x}, Y={y}, Wheel={wheel}")
    client.send_absolute(buttons, x, y, wheel)