import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Skill payload lives under skills/collect-tacit-knowledge/ (plugin layout).
SCRIPTS = os.path.join(ROOT, "skills", "collect-tacit-knowledge", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
