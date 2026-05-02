#!/usr/bin/env python3
"""
NOUS Ingest — Manuel klassifikation
Brug: python3 nous-ingest-manual.py /sti/til/fil.pdf
"""

import sys
import requests

def select_scope():
    print("\n=== DOKUMENTKLASSIFIKATION ===")
    print("Hvem skal have adgang til dette dokument?")
    print("  1. SECRET    — Kun mig (børnesag, CPR, passwords)")
    print("  2. PRIVATE   — Mine egne enheder (rutiner, journal, private noter)")
    print("  3. SWARM     — Anonymiseret deling med trusted netværk")
    print("  4. PUBLIC    — Offentligt tilgængelig")
    
    while True:
        choice = input("Vælg (1-4): ").strip()
        scopes = {"1": "SECRET", "2": "PRIVATE", "3": "SWARM", "4": "PUBLIC"}
        if choice in scopes:
            return scopes[choice]

def select_wing():
    wings = {
        "1": "boernesag",
        "2": "jura",
        "3": "dans_profil",
        "4": "familie",
        "5": "nous_projekt",
        "6": "fbf-data"
    }
    print("\n=== WING ===")
    for k, v in wings.items():
        print(f"  {k}. {v}")
    print("  7. Andet")
    
    choice = input("Vælg (1-7): ").strip()
    if choice in wings:
        return wings[choice]
    if choice == "7":
        return input("Ny wing: ").strip().lower().replace(" ", "_")
    return "nous_projekt"

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else input("Fil-sti: ")
    scope = select_scope()
    wing = select_wing()
    print(f"\nKopierer {filepath} til /home/nous/incoming/{wing}/")
    print(f"Scope: {scope}, Wing: {wing}")
    print("Ingest service processerer automatisk.")
