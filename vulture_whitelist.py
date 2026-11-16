"""Names vulture reports as unused that are used, or kept on purpose.

Vulture reads this file alongside the package (see bin/lint-backend.sh); it's never
imported. Regenerate candidates with:

    uv run vulture metrontagger --make-whitelist

Only add a name after checking it really is a false positive. Anything else is dead
code and should be deleted instead.
"""

# ruff: noqa: B018, F821

# Set as a plugin option; read by pillow-jxl-plugin, not by our code.
_.DECODE_THREADS  # unused attribute (metrontagger/__init__.py)

# Metadata fields set by MetadataMapper and read by darkseid when writing the XML.
_.comments  # unused attribute (metrontagger/mapper.py)
_.gtin  # unused attribute (metrontagger/mapper.py)
_.community_rating  # unused attribute (metrontagger/mapper.py)
_.stories  # unused attribute (metrontagger/mapper.py)
_.story_arcs  # unused attribute (metrontagger/mapper.py)
_.web_link  # unused attribute (metrontagger/mapper.py)
_.prices  # unused attribute (metrontagger/mapper.py)

# Read-only counterparts of FileRenamer's setters, kept as part of its public API.
_.smart_cleanup  # unused property (metrontagger/filerenamer.py)
_.issue_zero_padding  # unused property (metrontagger/filerenamer.py)
