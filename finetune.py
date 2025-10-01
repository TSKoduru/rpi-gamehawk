#!/usr/bin/env python3

import json
import os
import time
from typing import List, Dict, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOUSE_POS_FILE = os.path.join(SCRIPT_DIR, "mouse_positions.json")

# Minimal MouseSE class for moving mouse only
import math
import dbus

FIXED_DELTA = 1

class MouseClient:
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object('org.thanhle.btkbservice', '/org/thanhle/btkbservice')
        self.iface = dbus.Interface(self.btkservice, 'org.thanhle.btkbservice')

    def send_current(self, state):
        try:
            packet = bytes(state)
            self.iface.send_mouse(0, packet)
        except Exception as e:
            print(f"[ERROR] send_mouse failed: {e}")

class MouseSE:
    def __init__(self):
        self.current_x = 0
        self.current_y = 0
        self.current_button = 0
        self.client = MouseClient()
        self.recalibrate_top_left()

    def _send(self, dx, dy):
        dx_byte = dx & 0xFF
        dy_byte = dy & 0xFF
        state = [self.current_button, dx_byte, dy_byte, 0]
        self.client.send_current(state)
        time.sleep(0.01)

    def goto(self, x, y):
        dx = x - self.current_x
        dy = y - self.current_y

        while dx != 0 or dy != 0:
            step_x = 0
            step_y = 0

            if dx != 0:
                step_x = int(math.copysign(min(abs(dx), FIXED_DELTA), dx))
            if dy != 0:
                step_y = int(math.copysign(min(abs(dy), FIXED_DELTA), dy))

            self._send(step_x, step_y)

            dx -= step_x
            dy -= step_y

        self.current_x = x
        self.current_y = y

    def recalibrate_top_left(self):
        print("[INFO] Recalibrating to (0,0) - top-left corner")
        for _ in range(20):
            self._send(-127, 0)
        for _ in range(20):
            self._send(0, -127)
        self.current_x = 0
        self.current_y = 0

def load_positions(filepath) -> Dict[int, Tuple[int, int]]:
    with open(filepath, "r") as f:
        data = json.load(f)
    return {pos["cell"]: (pos["x"], pos["y"]) for pos in data}

def save_positions(filepath, positions: Dict[int, Tuple[int, int]]):
    # Convert back to list with dicts for JSON
    data = []
    for cell in sorted(positions.keys()):
        x, y = positions[cell]
        data.append({"cell": cell, "x": x, "y": y})
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[INFO] Saved adjusted positions to {filepath}")

def main():
    print("[INFO] Loading mouse positions...")
    positions = load_positions(MOUSE_POS_FILE)

    mouse = MouseSE()

    print("[INFO] Starting position calibration...")
    print("For each position, the mouse will move there.")
    print("Then enter offsets as integers (e.g., -2, 3) or 's' to skip adjusting.")
    print("Enter 'q' at any prompt to quit and save your progress.\n")

    for cell in sorted(positions.keys()):
        x, y = positions[cell]
        print(f"\nCell {cell}: moving mouse to ({x}, {y})")
        mouse.goto(x, y)
        time.sleep(0.5)

        while True:
            user_input = input(f"Enter offset x,y for cell {cell} (e.g. -2,3), 's' to skip, or 'q' to quit: ").strip()
            if user_input.lower() == 'q':
                print("[INFO] Quitting early, saving progress...")
                save_positions(MOUSE_POS_FILE, positions)
                return
            if user_input.lower() == 's' or user_input == '':
                print(f"[INFO] Skipping adjustment for cell {cell}.")
                break
            try:
                parts = user_input.split(',')
                if len(parts) != 2:
                    raise ValueError("Input must be two numbers separated by a comma")
                dx = int(parts[0].strip())
                dy = int(parts[1].strip())

                # Apply offset
                new_x = x + dx
                new_y = y + dy

                print(f"Moving mouse to adjusted position ({new_x}, {new_y})")
                mouse.goto(new_x, new_y)

                confirm = input("Is this position OK? (y/n): ").strip().lower()
                if confirm == 'y':
                    positions[cell] = (new_x, new_y)
                    print(f"[INFO] Position for cell {cell} updated.")
                    break
                else:
                    print("[INFO] Try entering offsets again.")
            except Exception as e:
                print(f"[ERROR] Invalid input: {e}")

    print("\n[INFO] Calibration done for all cells.")
    save_positions(MOUSE_POS_FILE, positions)

if __name__ == "__main__":
    main()
