from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import tkinter as tk
from collections.abc import Sequence
from contextlib import suppress
from tkinter import messagebox, ttk
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

LOCK_TIMEOUT_SECONDS = 15.0
LOCK_POLL_SECONDS = 0.2


class SettingsLockError(RuntimeError):
    """Raised when a settings lock cannot be acquired."""


def ensure_settings_file(settings_path: str, template_path: str) -> None:
    """Ensure settings.yaml exists, creating it from the template when needed."""
    if os.path.exists(settings_path):
        return

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found at {template_path}")

    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    shutil.copy2(template_path, settings_path)
    print("\nCreated new settings file from template.")
    print("Please review and update the settings with your API keys and preferences.")


class CollapsibleSection(ttk.Frame):
    """Expandable/collapsible container for grouped settings."""

    def __init__(self, parent: tk.Misc, title: str, *, collapsed: bool = False) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.collapsed = collapsed

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        self.toggle_button = ttk.Button(
            header,
            width=3,
            text="▶" if collapsed else "▼",
            command=self.toggle,
            cursor="hand2",
        )
        self.toggle_button.grid(row=0, column=0, padx=(2, 6))

        ttk.Label(header, text=title, font=("Segoe UI", 11, "bold")).grid(row=0, column=1, sticky="w")

        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="ew")
        if collapsed:
            self.body.grid_remove()

    def expand(self) -> None:
        if self.collapsed:
            self.toggle()

    def collapse(self) -> None:
        if not self.collapsed:
            self.toggle()

    def toggle(self) -> None:
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.grid_remove()
            self.toggle_button.configure(text="▶")
        else:
            self.body.grid(row=1, column=0, sticky="ew")
            self.toggle_button.configure(text="▼")


class SettingsEditor:
    """Tkinter-based settings editor with YAML round-tripping."""

    def __init__(self, settings_path: str) -> None:
        self.settings_path = settings_path
        self.lock_path = settings_path + ".lock"
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.config_data = self._load_settings()
        self.doc_comments = self._extract_document_comments()
        self.content_max_width = 960

        self.root = tk.Tk()
        self.root.title("Goldflipper Settings")
        self.root.geometry("1100x720")
        self.root.minsize(960, 600)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.fields: list[dict[str, Any]] = []
        self.sections: list[CollapsibleSection] = []

        self.style = ttk.Style()
        self.style.configure(
            "Comment.TLabel",
            font=("Segoe UI", 9),
            foreground="#555555",
        )

        self._build_ui()
        self._focus_window()

    def run(self) -> None:
        """Start the Tkinter mainloop."""
        self.root.mainloop()

    def _load_settings(self) -> CommentedMap:
        with open(self.settings_path, encoding="utf-8") as handle:
            data = self.yaml.load(handle)  # type: ignore[assignment]
        if data is None:
            data = CommentedMap()
        if not isinstance(data, CommentedMap):
            raise ValueError("settings.yaml must contain a mapping at the top level.")
        return data

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root)
        top_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(6, 2))
        top_frame.columnconfigure(0, weight=1)

        header = ttk.Label(
            top_frame,
            text="Goldflipper Settings",
            font=("Segoe UI", 11, "bold"),
        )
        header.pack(anchor="w")

        button_bar = ttk.Frame(top_frame)
        button_bar.pack(anchor="w", pady=(4, 2))

        button_kwargs = {"padx": (0, 6), "pady": 2}
        ttk.Button(button_bar, text="Expand All", width=15, command=self._expand_all).pack(side="left", **button_kwargs)
        ttk.Button(
            button_bar,
            text="Collapse All",
            width=15,
            command=self._collapse_all,
        ).pack(side="left", **button_kwargs)
        ttk.Button(
            button_bar,
            text="Jump to Top",
            width=15,
            command=lambda: self.canvas.yview_moveto(0),
        ).pack(side="left", **button_kwargs)
        ttk.Button(
            button_bar,
            text="Jump to Bottom",
            width=15,
            command=lambda: self.canvas.yview_moveto(1),
        ).pack(side="left", **button_kwargs)

        container_row = 1
        self.root.rowconfigure(container_row, weight=1)

        container = ttk.Frame(self.root)
        container.grid(row=container_row, column=0, sticky="nsew", padx=12, pady=(0, 4))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0)
        self.canvas = canvas
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.form_frame = ttk.Frame(canvas)
        self.form_frame.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas_frame = canvas.create_window((0, 0), window=self.form_frame, anchor="nw")

        def _resize_canvas(event: tk.Event) -> None:
            target_width = min(event.width, self.content_max_width)
            canvas.itemconfigure(canvas_frame, width=target_width)
            offset = max((event.width - target_width) // 2, 0)
            canvas.coords(canvas_frame, offset, 0)

        canvas.bind("<Configure>", _resize_canvas)
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        if self.doc_comments:
            intro_section = CollapsibleSection(self.form_frame, "Overview", collapsed=False)
            intro_section.pack(fill="x", expand=False, padx=8, pady=(0, 10), anchor="n")
            self._add_comment_label(
                intro_section.body,
                self.doc_comments,
                padding=(8, 4, 8, 6),
            )

        for key, value in self.config_data.items():
            self._render_field(self.form_frame, key, value, self.config_data)

        button_row = ttk.Frame(self.root)
        button_row.grid(row=container_row + 1, column=0, sticky="ew", padx=16, pady=(0, 12))
        button_row.columnconfigure(0, weight=1)

        ttk.Button(button_row, text="Save Changes", command=self._save).grid(row=0, column=1, padx=4)
        ttk.Button(button_row, text="Close", command=self.root.destroy).grid(row=0, column=2, padx=4)

    def _focus_window(self) -> None:
        try:
            if self.root.state() == "iconic":
                self.root.deiconify()
            self.root.update_idletasks()
            self.root.lift()
            self.root.focus_set()
        except tk.TclError:
            pass

    def _on_mousewheel(self, event: tk.Event) -> None:
        if isinstance(event.widget, tk.Text):
            return
        if event.delta == 0:
            return
        steps = int(-1 * (event.delta / 120))
        if steps:
            self.canvas.yview_scroll(steps, "units")

    def _render_field(
        self,
        parent: tk.Misc,
        key: str,
        value: Any,
        container: CommentedMap,
    ) -> None:
        comments = self._get_comments(container, key)

        if isinstance(value, (dict, CommentedMap)):
            collapsed = parent is self.form_frame
            section = CollapsibleSection(parent, key, collapsed=collapsed)
            section.pack(fill="x", expand=False, padx=8, pady=6, anchor="n")
            if parent is self.form_frame:
                self.sections.append(section)
            if comments:
                self._add_comment_label(section.body, comments)
            for child_key, child_value in value.items():
                self._render_field(section.body, child_key, child_value, value)  # type: ignore[arg-type]
            return

        if isinstance(value, (list, tuple, CommentedSeq)):
            if comments:
                self._add_comment_label(parent, comments)
            self._add_list_field(parent, key, list(value), container)
            return

        if isinstance(value, bool):
            if comments:
                self._add_comment_label(parent, comments)
            self._add_bool_field(parent, key, value, container)
            return

        if comments:
            self._add_comment_label(parent, comments)
        self._add_scalar_field(parent, key, value, container)

    def _add_scalar_field(
        self,
        parent: tk.Misc,
        key: str,
        value: Any,
        container: CommentedMap,
    ) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=12, pady=4)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text=key).grid(row=0, column=0, sticky="w", padx=(0, 12))
        var = tk.StringVar(value="" if value is None else str(value))
        entry = ttk.Entry(frame, textvariable=var, width=45)
        entry.grid(row=0, column=1, sticky="w")
        self.fields.append(
            {
                "kind": "scalar",
                "container": container,
                "key": key,
                "var": var,
                "value_type": type(value),
            }
        )

    def _add_bool_field(
        self,
        parent: tk.Misc,
        key: str,
        value: bool,
        container: CommentedMap,
    ) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=12, pady=4)
        var = tk.BooleanVar(value=value)
        ttk.Checkbutton(frame, text=key, variable=var).pack(anchor="w")
        self.fields.append(
            {
                "kind": "bool",
                "container": container,
                "key": key,
                "var": var,
            }
        )

    def _add_list_field(
        self,
        parent: tk.Misc,
        key: str,
        value: Sequence[Any],
        container: CommentedMap,
    ) -> None:
        frame = ttk.LabelFrame(parent, text=key)
        frame.pack(anchor="w", padx=12, pady=6)
        text_frame = ttk.Frame(frame)
        text_frame.pack(anchor="w")
        text = tk.Text(
            text_frame,
            height=min(max(len(value), 3), 10),
            wrap="none",
            width=80,
        )
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=text_scroll.set)
        text.pack(side="left")
        text_scroll.pack(side="right", fill="y")
        text.insert("1.0", "\n".join("" if item is None else str(item) for item in value))
        element_type = self._infer_list_type(value)
        self.fields.append(
            {
                "kind": "list",
                "container": container,
                "key": key,
                "widget": text,
                "element_type": element_type,
            }
        )

    def _add_comment_label(
        self,
        parent: tk.Misc,
        comments: list[str],
        padding: tuple[int, int, int, int] | None = None,
        *,
        use_grid: bool = False,
        grid_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not comments:
            return
        left, top, right, bottom = padding or (12, 6, 12, 2)
        label = ttk.Label(
            parent,
            text="\n".join(comments),
            style="Comment.TLabel",
            justify="left",
            wraplength=900,
        )
        if use_grid:
            kwargs = {"padx": (left, right), "pady": (top, bottom), "sticky": "ew"}
            if grid_kwargs:
                kwargs.update(grid_kwargs)
            label.grid(**kwargs)
        else:
            label.pack(fill="x", padx=(left, right), pady=(top, bottom))

    @staticmethod
    def _infer_list_type(value: Sequence[Any]) -> type:
        for item in value:
            if item is not None:
                return type(item)
        return str

    def _extract_document_comments(self) -> list[str]:
        ca = getattr(self.config_data, "ca", None)
        if not ca:
            return []
        comments = self._flatten_comment_tokens(getattr(ca, "comment", None))
        return self._filter_doc_comment_lines(comments)

    def _get_comments(self, container: CommentedMap, key: str) -> list[str]:
        ca = getattr(container, "ca", None)
        if not ca:
            return []
        meta = ca.items.get(key)
        if not meta:
            return []
        comments: list[str] = []
        for item in meta:
            comments.extend(self._flatten_comment_tokens(item))
        return [line for line in comments if line]

    def _flatten_comment_tokens(self, token: Any) -> list[str]:
        lines: list[str] = []
        if token is None:
            return lines
        if isinstance(token, list):
            for inner in token:
                lines.extend(self._flatten_comment_tokens(inner))
            return lines
        value = getattr(token, "value", None)
        if not isinstance(value, str):
            return lines
        for raw_line in value.splitlines():
            cleaned = self._clean_comment_line(raw_line)
            if cleaned is not None:
                lines.append(cleaned)
        return lines

    @staticmethod
    def _clean_comment_line(raw_line: str) -> str | None:
        stripped = raw_line.lstrip()
        if not stripped:
            return None
        if stripped.startswith("# "):
            stripped = stripped[2:]
        elif stripped.startswith("#"):
            stripped = stripped[1:]
        content = stripped.strip()
        if not content:
            return None
        noise_chars = set("#-=*_~`")
        if set(content) <= noise_chars:
            return None
        return content.rstrip()

    def _expand_all(self) -> None:
        for section in self.sections:
            section.expand()

    def _collapse_all(self) -> None:
        for section in self.sections:
            section.collapse()

    def _filter_doc_comment_lines(self, lines: list[str]) -> list[str]:
        """Remove redundant section headings from the document-level comments."""
        filtered: list[str] = []
        for line in lines:
            normalized = line.strip().lower()
            if normalized.endswith("settings"):
                continue
            filtered.append(line)
        return filtered

    def _save(self) -> None:
        try:
            self._apply_changes()
            self._write_settings_file()
        except SettingsLockError as exc:
            messagebox.showerror("Lock error", str(exc))
        except ValueError as exc:
            messagebox.showerror("Validation error", str(exc))
        except Exception as exc:  # pragma: no cover - safeguard for unexpected issues
            messagebox.showerror("Save failed", str(exc))
        else:
            messagebox.showinfo("Saved", "Settings saved successfully.")

    def _apply_changes(self) -> None:
        for field in self.fields:
            container = field["container"]
            key = field["key"]
            if field["kind"] == "bool":
                container[key] = bool(field["var"].get())
            elif field["kind"] == "scalar":
                raw_value = field["var"].get().strip()
                value_type = field["value_type"]
                container[key] = self._convert_scalar(raw_value, value_type)
            elif field["kind"] == "list":
                widget: tk.Text = field["widget"]
                raw_content = widget.get("1.0", "end-1c")
                lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
                element_type = field["element_type"]
                converted = CommentedSeq([self._convert_scalar(line, element_type) for line in lines])
                container[key] = converted

    def _convert_scalar(self, raw_value: str, value_type: type) -> Any:
        if value_type is bool:
            true_values = {"1", "true", "yes", "on"}
            false_values = {"0", "false", "no", "off"}
            lowered = raw_value.lower()
            if lowered in true_values:
                return True
            if lowered in false_values:
                return False
            raise ValueError(f"Invalid boolean value: {raw_value}")

        if value_type in (int, float):
            if not raw_value:
                raise ValueError("Numeric fields cannot be empty.")
            try:
                return value_type(raw_value)
            except ValueError as exc:
                raise ValueError(f"Invalid number: {raw_value}") from exc

        if value_type is type(None):
            return None if not raw_value else raw_value

        return raw_value

    def _write_settings_file(self) -> None:
        start_time = time.monotonic()
        while True:
            try:
                lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except FileExistsError as e:
                if time.monotonic() - start_time >= LOCK_TIMEOUT_SECONDS:
                    raise SettingsLockError(f"Could not obtain lock on settings file within {LOCK_TIMEOUT_SECONDS} seconds.") from e
                time.sleep(LOCK_POLL_SECONDS)

        try:
            dir_name = os.path.dirname(self.settings_path)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=dir_name, suffix=".tmp") as temp_file:
                self.yaml.dump(self.config_data, temp_file)
                temp_name = temp_file.name
            os.replace(temp_name, self.settings_path)
        finally:
            os.close(lock_fd)
            with suppress(FileNotFoundError):
                os.remove(self.lock_path)


def open_settings() -> bool:
    """Launch the interactive settings editor.

    Uses exe-aware path utilities to properly resolve settings.yaml location
    in both frozen (exe) and source modes.
    """
    # Use exe-aware path utilities for frozen mode compatibility
    from goldflipper.utils.exe_utils import get_settings_path, get_settings_template_path

    settings_path = str(get_settings_path())
    template_path = str(get_settings_template_path())

    try:
        ensure_settings_file(settings_path, template_path)
    except Exception as error:
        print(f"Unable to prepare settings file: {error}")
        return False

    try:
        editor = SettingsEditor(settings_path)
        editor.run()
    except Exception as error:
        print(f"\nError launching settings editor: {error}")
        return False

    return True


def main() -> None:
    if not open_settings():
        sys.exit(1)


if __name__ == "__main__":
    main()
