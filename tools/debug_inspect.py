import sys
from pathlib import Path
# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ranchoonline.user import routes
obj = routes.get()
print('type', type(obj))
children = getattr(obj, 'children', None)
print('children attr present:', children is not None)
if children:
    def walk(node, path="root"):
        from fastcore.xml import FT
        if isinstance(node, (str, bytes)):
            return
        if isinstance(node, bool):
            print('BOOL at', path, node)
        if hasattr(node, 'children') and node.children:
            for i, c in enumerate(node.children):
                walk(c, f"{path}/{i}")

    walk(obj)
else:
    print('no children')
from fastcore.xml import to_xml
try:
    s = to_xml(obj)
    print('to_xml succeeded, length', len(s))
except Exception as e:
    print('to_xml raised:', repr(e))
    # inspect top-level children
    for i, c in enumerate(getattr(obj, 'children', []) or []):
        print('child', i, 'type', type(c))
        try:
            print(' child to_xml len', len(to_xml(c)))
        except Exception as ee:
            print(' child to_xml error:', repr(ee))
        try:
            print(' child repr:', repr(c)[:200])
        except Exception:
            pass
