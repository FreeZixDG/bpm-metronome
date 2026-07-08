import ast
import math
import os
import subprocess
import sys
from pathlib import Path


def format_float(x, max_decimals=6):
        s = f"{x:.{max_decimals}f}"
        return s.rstrip("0").rstrip(".")


def parse_float_expression(text):
        text = text.replace(",", ".").strip()

        if not text:
                raise ValueError("La valeur est vide.")

        try:
                tree = ast.parse(text, mode="eval")
        except SyntaxError:
                raise ValueError("Expression numérique invalide.")

        def eval_node(node):
                if isinstance(node, ast.Expression):
                        return eval_node(node.body)

                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                        return float(node.value)

                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                        value = eval_node(node.operand)
                        return value if isinstance(node.op, ast.UAdd) else -value

                if isinstance(node, ast.BinOp):
                        left = eval_node(node.left)
                        right = eval_node(node.right)

                        if isinstance(node.op, ast.Add):
                                return left + right
                        if isinstance(node.op, ast.Sub):
                                return left - right
                        if isinstance(node.op, ast.Mult):
                                return left * right
                        if isinstance(node.op, ast.Div):
                                return left / right

                raise ValueError("Seuls les nombres et les opérations +, -, *, / sont acceptés.")

        try:
                value = eval_node(tree)
        except ZeroDivisionError:
                raise ValueError("Division par zéro.")

        if not math.isfinite(value):
                raise ValueError("Le résultat doit être un nombre fini.")

        return value


def sanitize_filename(name):
        invalid = '<>:"/\\|?*'
        for c in invalid:
                name = name.replace(c, "_")

        name = name.strip()

        if not name:
                name = "metronome.wav"

        if not name.lower().endswith(".wav"):
                name += ".wav"

        return name


def open_file(path):
        path = Path(path)

        if sys.platform.startswith("win"):
                os.startfile(str(path))
        elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
        else:
                subprocess.Popen(["xdg-open", str(path)])
