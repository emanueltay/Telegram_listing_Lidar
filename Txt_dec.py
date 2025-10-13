import tkinter as tk
from tkinter import filedialog, messagebox

def import_and_convert():
    file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
    if not file_path:
        return

    try:
        with open(file_path, 'r') as file:
            hex_data = file.read().strip()

        hex_values = hex_data.replace('\n', ' ').replace(',', ' ').split()

        decimal_values = []
        ascii_chars = []
        for h in hex_values:
            if h == "DIST1":
                decimal_values.append("DIST1")
                ascii_chars.append("DIST1")
            else:
                try:
                    val = int(h, 16)
                    decimal_values.append(str(val))
                    ascii_chars.append(chr(val) if 32 <= val <= 126 else '.')
                except ValueError:
                    decimal_values.append('?')
                    ascii_chars.append('?')

        ascii_string = ''.join(ascii_chars)
        dist1_start = ascii_string.find("DIST1")
        dist1_end = dist1_start + len("DIST1") if dist1_start != -1 else -1

        hex_output.delete("1.0", tk.END)
        dec_output.delete("1.0", tk.END)

        i = 0
        while i < len(hex_values):
            if dist1_start != -1 and i >= dist1_start and i < dist1_end:
                if i == dist1_start:
                    hex_output.insert(tk.END, "DIST1\n -> ", "highlight")
                    dec_output.insert(tk.END, "DIST1 Number of point\n -> ", "highlight")
                i += 1
            else:
                hex_output.insert(tk.END, hex_values[i] + " ")
                dec_output.insert(tk.END, decimal_values[i] + " ")
                i += 1

    except Exception as e:
        messagebox.showerror("Error", f"Failed to process file: {e}")

def clear_output():
    hex_output.delete("1.0", tk.END)
    dec_output.delete("1.0", tk.END)

# GUI setup
root = tk.Tk()
root.title("Hex to Decimal Converter")
root.geometry("800x600")
root.minsize(600, 400)

root.grid_rowconfigure(2, weight=1)
root.grid_columnconfigure(0, weight=1)

# Buttons
tk.Button(root, text="Import TXT and Convert", command=import_and_convert).grid(row=0, column=0, pady=10)
tk.Button(root, text="Clear", command=clear_output).grid(row=1, column=0, pady=10)

# Output frame
output_frame = tk.Frame(root)
output_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

output_frame.grid_columnconfigure(0, weight=1)
output_frame.grid_columnconfigure(1, weight=1)
output_frame.grid_rowconfigure(1, weight=1)

# Shared vertical scrollbar
v_scroll = tk.Scrollbar(output_frame, orient=tk.VERTICAL)
v_scroll.grid(row=1, column=2, sticky="ns")

# Hex Panel
hex_label = tk.Label(output_frame, text="Hex Values:")
hex_label.grid(row=0, column=0, sticky='w')
hex_output = tk.Text(output_frame, wrap=tk.WORD, yscrollcommand=v_scroll.set)
hex_output.tag_config("highlight", background="yellow", foreground="black")
hex_output.grid(row=1, column=0, sticky="nsew", padx=(0, 5))

# Decimal Panel
dec_label = tk.Label(output_frame, text="Decimal Values:")
dec_label.grid(row=0, column=1, sticky='w')
dec_output = tk.Text(output_frame, wrap=tk.WORD, yscrollcommand=v_scroll.set)
dec_output.tag_config("highlight", background="yellow", foreground="black")
dec_output.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

# Scroll synchronization
def on_scroll(*args):
    hex_output.yview(*args)
    dec_output.yview(*args)

v_scroll.config(command=on_scroll)

root.mainloop()
