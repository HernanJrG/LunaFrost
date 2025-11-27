import ast
import sys

filename = r"\\nas\files\LunaFrost\Translator\routes\api_routes.py"

try:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    ast.parse(content)
    print("No syntax errors found.")
except SyntaxError as e:
    print(f"SyntaxError: {e}")
    print(f"Line: {e.lineno}")
    print(f"Offset: {e.offset}")
    print(f"Text: {e.text}")
    
    # Print context
    lines = content.splitlines()
    if e.lineno:
        print(f"Line {e.lineno}: {lines[e.lineno-1]}")
        if e.lineno > 1:
            print(f"Line {e.lineno-1}: {lines[e.lineno-2]}")
except Exception as e:
    print(f"Error: {e}")
