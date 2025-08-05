#!/usr/bin/env python

"""
CaptiOCR - Debug version
"""
import sys
import os

print("=== CAPTIOCR DEBUG ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Script location: {os.path.abspath(__file__)}")
print(f"Script directory: {os.path.dirname(os.path.abspath(__file__))}")

# Controlla se la cartella captiocr esiste
captiocr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captiocr")
print(f"\nCercando captiocr in: {captiocr_path}")
print(f"La cartella captiocr esiste? {os.path.exists(captiocr_path)}")

if os.path.exists(captiocr_path):
    print(f"Contenuto di captiocr: {os.listdir(captiocr_path)}")
    
    # Controlla se main.py esiste
    main_path = os.path.join(captiocr_path, "main.py")
    print(f"main.py esiste? {os.path.exists(main_path)}")

# Aggiungi al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
print(f"\nPython path: {sys.path[0]}")

try:
    print("\nProvando ad importare captiocr...")
    import captiocr
    print("✓ captiocr importato con successo")
    
    print("\nProvando ad importare captiocr.main...")
    from captiocr.main import main
    print("✓ captiocr.main importato con successo")
    
    print("\nProvando ad eseguire main()...")
    main()
    
except Exception as e:
    print(f"\n❌ ERRORE: {e}")
    import traceback
    traceback.print_exc()

input("\n\nPremi ENTER per chiudere...")