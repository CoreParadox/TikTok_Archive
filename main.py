"""Main entry point for TikTok Archiver"""
import tkinter as tk
from src.gui.main_window import TikTokArchiverGUI

def main():
    root = tk.Tk()
    app = TikTokArchiverGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
