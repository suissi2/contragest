import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.geometry("800x400")

# Treeview
tree_frame = tk.Frame(root)
tree_frame.pack(fill="both", expand=True, pady=(30, 0)) # Leaves room for floating entries

tree = ttk.Treeview(tree_frame, columns=[f"C{i}" for i in range(10)], show="headings")
# Set a fixed narrow width for each column to force scrolling
for i in range(10):
    tree.heading(f"C{i}", text=f"Col {i}")
    tree.column(f"C{i}", width=150, minwidth=150, stretch=False)
tree.pack(side="top", fill="both", expand=True)

# Add horizontal scrollbar
xs = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
xs.pack(side="bottom", fill="x")

for j in range(5):
    tree.insert("", "end", values=[f"Val {i}" for i in range(10)])

# Filter Canvas
filter_canvas = tk.Canvas(root, height=25, bg="red", highlightthickness=0)
filter_canvas.place(x=0, y=0, relwidth=1)

filter_inner = tk.Frame(filter_canvas)
filter_canvas.create_window((0, 0), window=filter_inner, anchor="nw")

entries = []
for i in range(10):
    e = ttk.Entry(filter_inner, width=1)
    e.pack(side="left")
    entries.append(e)

def sync_width(*args):
    # sync width of entries
    total_w = 0
    for i in range(10):
        w = tree.column(f"C{i}", "width")
        entries[i].place(x=total_w, width=w, y=0, height=25)
        total_w += w
    filter_canvas.configure(scrollregion=(0, 0, total_w, 25))
    
def sync_scroll(*args):
    # tree scroll
    xs.set(*args)
    # The arguments args are two fractions, e.g. ("0.0", "0.5")
    filter_canvas.xview_moveto(args[0])

tree.configure(xscrollcommand=sync_scroll)
root.bind("<Configure>", sync_width)

root.after(8000, root.destroy)
root.mainloop()
