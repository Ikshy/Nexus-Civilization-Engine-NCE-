#!/usr/bin/env python3
"""Generate all __init__.py files for NCE packages."""
import os

packages = [
    "/home/claude/nce/backend",
    "/home/claude/nce/backend/config",
    "/home/claude/nce/backend/core",
    "/home/claude/nce/backend/core/world",
    "/home/claude/nce/backend/core/agents",
    "/home/claude/nce/backend/core/cognitive",
    "/home/claude/nce/backend/core/economy",
    "/home/claude/nce/backend/core/social",
    "/home/claude/nce/backend/core/conflict",
    "/home/claude/nce/backend/core/governance",
    "/home/claude/nce/backend/core/information",
    "/home/claude/nce/backend/core/analytics",
    "/home/claude/nce/backend/core/scenarios",
    "/home/claude/nce/backend/services",
    "/home/claude/nce/backend/api",
    "/home/claude/nce/backend/api/routes",
    "/home/claude/nce/backend/data",
    "/home/claude/nce/backend/data/repositories",
]

for pkg in packages:
    init = os.path.join(pkg, "__init__.py")
    os.makedirs(pkg, exist_ok=True)
    if not os.path.exists(init):
        with open(init, "w") as f:
            f.write('"""NCE package."""\n')
        print(f"Created {init}")
    else:
        print(f"Exists  {init}")

print("Done.")
