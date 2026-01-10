#!/usr/bin/env python3

import pickle
import time
import os
import dbus
from typing import List, Tuple, Dict, Set

# ==== CONFIGURATION ====
# Coordinates (Top-Left and Bottom-Right of the 4x4 grid)
TOP_LEFT_X = 7500
TOP_LEFT_Y = 15750
BOTTOM_RIGHT_X = 25000
BOTTOM_RIGHT_Y = 24000

# Solver Settings
SOLVER_NUMWORDS_LIMIT = 500
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==== Grid Logic ====
def get_grid_coordinates():
    """
    Interpolates the center coordinates for all 16 cells (4x4).
    Returns a dict mapping (row, col) -> (x, y)
    """
    coords = {}
    
    # Calculate step size between centers (3 gaps between 4 items)
    step_x = (BOTTOM_RIGHT_X - TOP_LEFT_X) / 3
    step_y = (BOTTOM_RIGHT_Y - TOP_LEFT_Y) / 3

    for row in range(4):
        for col in range(4):
            x = int(TOP_LEFT_X + (col * step_x))
            y = int(TOP_LEFT_Y + (row * step_y))
            coords[(row, col)] = (x, y)
    
    return coords

# ==== Trie loader ====
def load_trie(filepath=None) -> dict:
    if filepath is None:
        filepath = os.path.join(SCRIPT_DIR, "trie.pkl")
    
    if not os.path.exists(filepath):
        print(f"[ERROR] trie.pkl not found at {filepath}")
        print("Please ensure your dictionary file is in the same folder.")
        exit(1)
        
    with open(filepath, "rb") as f:
        return pickle.load(f)

# ==== Word finder code (Standard DFS) ====
Position = Tuple[int, int]

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

# ==== Absolute Mouse Client ====
class AbsoluteMouse:
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object('org.thanhle.btkbservice', '/org/thanhle/btkbservice')
        self.iface = dbus.Interface(self.btkservice, 'org.thanhle.btkbservice')

    def send_cmd(self, buttons, x, y, wheel=0):
        # Clamp to valid absolute range (0-32767)
        x = max(0, min(32767, x))
        y = max(0, min(32767, y))
        
        # Split 16-bit integers into low/high bytes (Little Endian)
        x_low = x & 0xFF
        x_high = (x >> 8) & 0xFF
        y_low = y & 0xFF
        y_high = (y >> 8) & 0xFF
        
        # 8 Byte packet: [Buttons, X_lo, X_hi, Y_lo, Y_hi, Wheel]
        state = [buttons, x_low, x_high, y_low, y_high, wheel]
        
        try:
            self.iface.send_mouse(0, bytes(state))
        except Exception as e:
            print(f"[ERROR] DBus call failed: {e}")

# ==== Main flow ====
def main():
    print("Initializing Dictionary...")
    trie = load_trie()
    
    # Pre-calculate the screen coordinates for the 4x4 grid
    grid_coords = get_grid_coordinates()
    
    mouse = AbsoluteMouse()

    print("--- Word Hunt Solver (Absolute Mode) ---")
    print(f"Grid Config: TL={TOP_LEFT_X},{TOP_LEFT_Y} | BR={BOTTOM_RIGHT_X},{BOTTOM_RIGHT_Y}")

    while True:
        # User input: Accepts "AbCdEf..." or "a b c d ..." or "A,B,C,D..."
        raw_input = input("\nEnter 16 letters (row-by-row): ")
        
        # 1. Lowercase everything
        # 2. Keep ONLY valid letters (a-z)
        # 3. Join them into a single string
        board_str = "".join(c for c in raw_input.lower() if 'a' <= c <= 'z')

        if len(board_str) != 16:
            print(f"[!] Error: Parsed {len(board_str)} letters. I need exactly 16.")
            print(f"    (You typed: '{raw_input}' -> Parsed: '{board_str}')")
            continue

        # Create 4x4 board
        board = [list(board_str[i*4:(i+1)*4]) for i in range(4)]

        print("Solving board...")
        start_time = time.time()
        results = find_words(board, trie)
        print(f"Found {len(results)} words in {time.time() - start_time:.4f}s")
        
        input(">> Press ENTER to start swiping (Ensure game is open!) <<")
        
        # Buffer to move hand away from keyboard
        time.sleep(1.0)
        
        print("Executing swipes...")

        for i, word_obj in enumerate(results):
            path = word_obj["coordinates"]
            
            # 1. Move to first letter (HOVER)
            start_r, start_c = path[0]
            sx, sy = grid_coords[(start_r, start_c)]
            mouse.send_cmd(0, sx, sy) 
            time.sleep(0.015)

            # 2. Press Down
            mouse.send_cmd(1, sx, sy)
            time.sleep(0.02)

            # 3. Drag through the rest
            for r, c in path[1:]:
                tx, ty = grid_coords[(r, c)]
                mouse.send_cmd(1, tx, ty) # Button 1 held down
                time.sleep(0.035) 

            # 4. Release
            end_r, end_c = path[-1]
            ex, ey = grid_coords[(end_r, end_c)]
            mouse.send_cmd(0, ex, ey)
            time.sleep(0.02)

        print("Done! Ready for next round.")

if __name__ == "__main__":
    main()