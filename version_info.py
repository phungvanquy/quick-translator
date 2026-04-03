# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller version info for QuickTranslator.

Embeds proper metadata into the .exe so Windows can display publisher info,
file description, and version — which helps with SmartScreen / Smart App Control
reputation scoring.
"""

VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,          # VOS_NT_WINDOWS32
        fileType=0x1,        # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",   # lang=US-English, charset=Unicode
                    [
                        StringStruct("CompanyName",      "QuickTranslator"),
                        StringStruct("FileDescription",  "Quick Translator — desktop translator and AI chat assistant"),
                        StringStruct("FileVersion",      "1.0.0.0"),
                        StringStruct("InternalName",     "QuickTranslator"),
                        StringStruct("LegalCopyright",   "Copyright (c) 2024-2026 QuickTranslator contributors"),
                        StringStruct("OriginalFilename", "QuickTranslator.exe"),
                        StringStruct("ProductName",      "QuickTranslator"),
                        StringStruct("ProductVersion",   "1.0.0.0"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
