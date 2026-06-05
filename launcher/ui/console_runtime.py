"""Runtime konsoli launchera i batchowanego logowania."""

import tkinter as tk
from tkinter import scrolledtext


__all__ = ["create_console_widget", "log", "flush_logs"]


def create_console_widget(app, parent):
        """Tworzy widget konsoli z ciemnym motywem."""
        console = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, bg="#1e1e1e", fg="#e0e0e0",
            font=("Consolas", app.base_font_size),
            insertbackground="#ffffff", selectbackground="#3a3a3a",
            selectforeground="#ffffff", height=10
        )
        console.pack(fill=tk.BOTH, expand=True)
        console.configure(state="disabled")
        return console

def log(app, message, console=None):
        """Wypisuje wiadomość do konsoli (zoptymalizowane z batchingiem)."""
        target_console = console or app.main_console

        # Dodaj do bufora zamiast natychmiastowego zapisu
        console_id = id(target_console)
        if console_id not in app._log_buffer:
            app._log_buffer[console_id] = {'console': target_console, 'messages': []}

        app._log_buffer[console_id]['messages'].append(message)

        # Zaplanuj flush jeśli jeszcze nie zaplanowano
        if not app._log_flush_pending:
            app._log_flush_pending = True
            app.after(10, app._flush_logs)  # Flush co 10ms (szybkie odświeżanie)

def flush_logs(app):
        """Flush wszystkich zabuforowanych logów na raz."""
        try:
            for console_id, data in app._log_buffer.items():
                console = data['console']
                messages = data['messages']

                if messages:
                    # Jeden update zamiast wielu
                    console.configure(state="normal")
                    console.insert(tk.END, ''.join(messages))
                    console.see(tk.END)
                    console.configure(state="disabled")

                    data['messages'].clear()
        finally:
            app._log_flush_pending = False
