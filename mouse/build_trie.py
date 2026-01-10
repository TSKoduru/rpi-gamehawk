#!/usr/bin/env python3

import pickle
import sys
import os

def build_trie(txt_filename):
    print(f"Reading {txt_filename}...")
    
    trie = {}
    count = 0
    
    try:
        with open(txt_filename, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Clean the word: remove whitespace, make lowercase
                word = line.strip().lower()
                
                # Skip empty lines or words with numbers/symbols
                if not word or not word.isalpha():
                    continue
                
                # Skip words too short to matter (usually games require 3+)
                if len(word) < 3:
                    continue

                # Insert into Trie
                node = trie
                for char in word:
                    if char not in node:
                        node[char] = {}
                    node = node[char]
                # Mark end of word
                node['$'] = True
                count += 1
                
    except FileNotFoundError:
        print(f"Error: Could not find file '{txt_filename}'")
        sys.exit(1)

    output_file = "trie.pkl"
    print(f"Compiling Trie structure...")
    
    with open(output_file, 'wb') as f:
        pickle.dump(trie, f)
        
    print(f"Success! Processed {count} words.")
    print(f"Saved to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 build_trie.py <your_word_list.txt>")
    else:
        build_trie(sys.argv[1])