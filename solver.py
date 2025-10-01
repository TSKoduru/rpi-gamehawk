#!/usr/bin/env python3

import pickle
import time
import json
import os
import math
import dbus
from typing import List, Tuple, Dict, Set

Position = Tuple[int, int]
SOLVER_NUMWORDS_LIMIT = 500
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXED_DELTA = 10  # Fixed step size to fight acceleration

# ==== Load mouse_positions.json ====

def load_mouse_positions(filepath=None):
    if filepath is None:
        filepath = os.path.join(SCRIPT_DIR, "mouse_positions.json")
    with open(filepath, "r") as f:
        data = json.load(f)
    return {pos["cell"]: (pos["x"], pos["y"]) for pos in data}

# ==== Trie loader ====

def load_trie(filepath=None) -> dict:
    if filepath is None:
        filepath = os.path.join(SCRIPT_DIR, "trie.pkl")
    with open(filepath, "rb") as f:
        return pickle.load(f)

# ==== Word finder code ====

def get_neighbors(row: int, col: int, num_rows=4, num_cols=4) -> List[Position]:
    return [
        (r, c)
        for dr in [-1, 0, 1]
        for dc in [-1, 0, 1]
        if (dr != 0 or dc != 0) and 0 <= (r := row + dr) < num_rows and 0 <= (c := col + dc) < num_cols
    ]

def dfs(
    row: int,
    col: int,
    board: List[List[str]],
    node: dict,
    visited: Set[Position],
    current_word: str,
    current_path: List[Position],
    results: Set[str],
    paths: Dict[str, List[Position]],
):
    letter = board[row][col]
    next_node = node.get(letter)
    if not next_node:
        return

    visited.add((row, col))
    current_word += letter
    current_path.append((row, col))

    if "$" in next_node and len(current_word) >= 3:
        results.add(current_word)
        if current_word not in paths:
            paths[current_word] = list(current_path)

    for nrow, ncol in get_neighbors(row, col):
        if (nrow, ncol) not in visited:
            dfs(nrow, ncol, board, next_node, visited, current_word, current_path, results, paths)

    visited.remove((row, col))
    current_path.pop()

def find_words(board: List[List[str]], trie: dict) -> List[Dict]:
    results = set()
    paths = {}

    board_letters = {ch for row in board for ch in row}
    valid_starts = {ch: node for ch, node in trie.items() if ch in board_letters}

    for row in range(len(board)):
        for col in range(len(board[0])):
            dfs(row, col, board, valid_starts, set(), "", [], results, paths)

    sorted_words = sorted(results, key=lambda w: (-len(w), w))
    limited = sorted_words[:SOLVER_NUMWORDS_LIMIT]

    return [{"word": word, "coordinates": paths[word]} for word in limited]

# ==== MouseSE classes with fixed delta diagonal movement ====

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

            self.current_x += step_x
            self.current_y += step_y

            dx = x - self.current_x
            dy = y - self.current_y

            time.sleep(0.002)  # Small delay between steps for smoother movement

    def recalibrate_top_left(self):
        print("[INFO] Recalibrating to (0,0) - top-left corner")
        for _ in range(20):
            self._send(-127, 0)
        for _ in range(20):
            self._send(0, -127)
        self.current_x = 0
        self.current_y = 0

# ==== Helpers ====

def coord_to_index(coord: Position) -> int:
    return coord[0] * 4 + coord[1]  # row-major 0..15

def convert_coord_to_mouse_pos(coord: Position, mouse_positions) -> Tuple[int, int]:
    idx = coord_to_index(coord)
    return mouse_positions[idx]

# ==== Main flow ====

def main():
    trie = load_trie()
    mouse_positions = load_mouse_positions()

    mouse = MouseSE()

    while True:
        board_str = input("Enter 16 letters (row-wise, a-z): ").strip().lower()
        if len(board_str) != 16 or not board_str.isalpha():
            print("Invalid input, try again.")
            continue

        board = [list(board_str[i*4:(i+1)*4]) for i in range(4)]

        print("Solving board...")
        results = find_words(board, trie)
        print(f"Found {len(results)} words:")

        for r in results:
            print(f"{r['word']} at {r['coordinates']}")

        mouse.goto(*mouse_positions[0])  # Move mouse to top-left start position

        print("Starting mouse movements to select words...")

        for i, word in enumerate(results):
            coords = word["coordinates"]
            # Move mouse to first letter cell
            first_screen_pos = convert_coord_to_mouse_pos(coords[0], mouse_positions)
            mouse.goto(*first_screen_pos)
            mouse.current_button = 1  # press down
            mouse._send(0, 0)  # send button press event
            time.sleep(0.05)   # short delay after press

            for pos in coords[1:]:
                screen_pos = convert_coord_to_mouse_pos(pos, mouse_positions)
                mouse.goto(*screen_pos)
                time.sleep(0.07)  # small delay between letters

            mouse.current_button = 0  # release button
            mouse._send(0, 0)  # send release event
            time.sleep(0.05)   # short delay after release

            print(f"Selected word: {word['word']}")

            # Recalibrate every 3 words instead of every word
            if (i + 1) % 3 == 0:
                mouse.recalibrate_top_left()
                time.sleep(0.3)  # give some buffer before next batch

if __name__ == "__main__":
    main()
