"""Streamlit entrypoint for `streamlit run app.py`.

The actual dashboard implementation lives in `customer_support_agent/app.py`.

IMPORTANT: this must NOT be `from customer_support_agent.app import *`.
Streamlit reruns THIS file (app.py) from scratch on every user interaction
(button click, radio change, etc.), but a plain `import` only executes a
module's top-level code the FIRST time — Python caches it in sys.modules
after that. Since the entire dashboard (sidebar, page routing, every
widget) lives at module level in customer_support_agent/app.py, a plain
`import *` meant reruns 2+ silently did nothing at all: no sidebar, no
page content, no error — a blank screen. `runpy.run_path` re-executes the
target file's code fresh every single call, which is what a Streamlit
multi-rerun entrypoint actually needs.
"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).parent / "customer_support_agent" / "app.py"), run_name="__main__")
