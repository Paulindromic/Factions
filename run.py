#!/usr/bin/env python3
"""
Factions – Cold War Shadow War
Launch script.
"""
import sys
import os

# Ensure game_state_ref is importable from root
sys.path.insert(0, os.path.dirname(__file__))

from game.main import run_game

if __name__ == "__main__":
    import random
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.randint(1, 9999)
    print(f"Starting game with seed {seed}")
    run_game(seed=seed)
