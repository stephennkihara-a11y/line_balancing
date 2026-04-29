"""Sample operation bulletin for a basic pique polo shirt (35 ops).

SAM values are illustrative. Sections: collar, placket, front/back, sleeve,
assembly, finishing.
"""

POLO_SHIRT_OPERATIONS = [
    # ----- Collar / placket prep -----
    {"op_code": "OP01", "sequence": 1,  "description": "Collar runstitch",                    "sam": 0.45, "machine_type": "SNLS",       "skill_level": 3, "section": "collar"},
    {"op_code": "OP02", "sequence": 2,  "description": "Trim & turn collar",                  "sam": 0.30, "machine_type": "MANUAL",     "skill_level": 1, "section": "collar"},
    {"op_code": "OP03", "sequence": 3,  "description": "Topstitch collar edge",               "sam": 0.55, "machine_type": "SNLS",       "skill_level": 3, "section": "collar"},
    {"op_code": "OP04", "sequence": 4,  "description": "Mark placket",                        "sam": 0.20, "machine_type": "MANUAL",     "skill_level": 1, "section": "placket"},
    {"op_code": "OP05", "sequence": 5,  "description": "Attach placket to front",             "sam": 0.85, "machine_type": "SNLS",       "skill_level": 4, "section": "placket"},
    {"op_code": "OP06", "sequence": 6,  "description": "Topstitch placket box",               "sam": 0.70, "machine_type": "SNLS",       "skill_level": 3, "section": "placket"},
    {"op_code": "OP07", "sequence": 7,  "description": "Bartack placket bottom",              "sam": 0.20, "machine_type": "BARTACK",    "skill_level": 2, "section": "placket"},
    {"op_code": "OP08", "sequence": 8,  "description": "Buttonhole placket",                  "sam": 0.50, "machine_type": "BUTTONHOLE", "skill_level": 4, "section": "placket"},
    {"op_code": "OP09", "sequence": 9,  "description": "Mark button position",                "sam": 0.15, "machine_type": "MANUAL",     "skill_level": 1, "section": "placket"},
    {"op_code": "OP10", "sequence": 10, "description": "Attach buttons",                      "sam": 0.45, "machine_type": "BUTTON",     "skill_level": 3, "section": "placket"},

    # ----- Body prep -----
    {"op_code": "OP11", "sequence": 11, "description": "Inspect cut panels",                  "sam": 0.25, "machine_type": "MANUAL",     "skill_level": 1, "section": "front"},
    {"op_code": "OP12", "sequence": 12, "description": "Hem back yoke (if any) or mark",      "sam": 0.30, "machine_type": "OL",         "skill_level": 2, "section": "back"},
    {"op_code": "OP13", "sequence": 13, "description": "Join shoulder seams",                 "sam": 0.60, "machine_type": "OL",         "skill_level": 3, "section": "assembly"},
    {"op_code": "OP14", "sequence": 14, "description": "Topstitch shoulder seam",             "sam": 0.50, "machine_type": "FOA",        "skill_level": 3, "section": "assembly"},

    # ----- Sleeves -----
    {"op_code": "OP15", "sequence": 15, "description": "Hem sleeve cuff (rib attach)",        "sam": 0.55, "machine_type": "OL",         "skill_level": 3, "section": "sleeve"},
    {"op_code": "OP16", "sequence": 16, "description": "Topstitch sleeve cuff",               "sam": 0.45, "machine_type": "FOA",        "skill_level": 3, "section": "sleeve"},
    {"op_code": "OP17", "sequence": 17, "description": "Attach sleeve to body (set-in)",      "sam": 0.85, "machine_type": "OL",         "skill_level": 4, "section": "assembly"},
    {"op_code": "OP18", "sequence": 18, "description": "Topstitch armhole",                   "sam": 0.65, "machine_type": "FOA",        "skill_level": 4, "section": "assembly"},

    # ----- Side / hem -----
    {"op_code": "OP19", "sequence": 19, "description": "Side seam join (sleeve to hem)",      "sam": 0.95, "machine_type": "OL",         "skill_level": 4, "section": "assembly"},
    {"op_code": "OP20", "sequence": 20, "description": "Tack side seam at hem",               "sam": 0.20, "machine_type": "BARTACK",    "skill_level": 2, "section": "assembly"},
    {"op_code": "OP21", "sequence": 21, "description": "Bottom hem",                          "sam": 0.55, "machine_type": "FOA",        "skill_level": 3, "section": "assembly"},

    # ----- Collar attach -----
    {"op_code": "OP22", "sequence": 22, "description": "Attach collar to neckline",           "sam": 0.95, "machine_type": "SNLS",       "skill_level": 4, "section": "collar"},
    {"op_code": "OP23", "sequence": 23, "description": "Close neck tape & topstitch",         "sam": 0.70, "machine_type": "SNLS",       "skill_level": 4, "section": "collar"},
    {"op_code": "OP24", "sequence": 24, "description": "Tack collar joint",                   "sam": 0.20, "machine_type": "BARTACK",    "skill_level": 2, "section": "collar"},

    # ----- Labels / detail -----
    {"op_code": "OP25", "sequence": 25, "description": "Attach main label",                   "sam": 0.30, "machine_type": "SNLS",       "skill_level": 2, "section": "finishing"},
    {"op_code": "OP26", "sequence": 26, "description": "Attach size/care label",              "sam": 0.30, "machine_type": "SNLS",       "skill_level": 2, "section": "finishing"},
    {"op_code": "OP27", "sequence": 27, "description": "Side slit reinforcement",             "sam": 0.40, "machine_type": "SNLS",       "skill_level": 3, "section": "assembly"},

    # ----- Finishing -----
    {"op_code": "OP28", "sequence": 28, "description": "Trim threads",                        "sam": 0.40, "machine_type": "MANUAL",     "skill_level": 1, "section": "finishing"},
    {"op_code": "OP29", "sequence": 29, "description": "Inline inspection",                   "sam": 0.50, "machine_type": "MANUAL",     "skill_level": 2, "section": "finishing"},
    {"op_code": "OP30", "sequence": 30, "description": "Touch-up press collar/placket",       "sam": 0.45, "machine_type": "IRON",       "skill_level": 2, "section": "finishing"},
    {"op_code": "OP31", "sequence": 31, "description": "Final press body",                    "sam": 0.60, "machine_type": "IRON",       "skill_level": 2, "section": "finishing"},
    {"op_code": "OP32", "sequence": 32, "description": "Measurement check",                   "sam": 0.35, "machine_type": "MANUAL",     "skill_level": 2, "section": "finishing"},
    {"op_code": "OP33", "sequence": 33, "description": "Hangtag & price tag",                 "sam": 0.30, "machine_type": "MANUAL",     "skill_level": 1, "section": "finishing"},
    {"op_code": "OP34", "sequence": 34, "description": "Fold & polybag",                      "sam": 0.45, "machine_type": "MANUAL",     "skill_level": 1, "section": "finishing"},
    {"op_code": "OP35", "sequence": 35, "description": "Final QC pass",                       "sam": 0.40, "machine_type": "MANUAL",     "skill_level": 2, "section": "finishing"},
]

POLO_SHIRT_PRECEDENCE = [
    # Collar sub-assembly
    ("OP01", "OP02"), ("OP02", "OP03"),
    # Placket
    ("OP04", "OP05"), ("OP05", "OP06"), ("OP06", "OP07"),
    ("OP06", "OP08"), ("OP08", "OP09"), ("OP09", "OP10"),
    # Body assembly
    ("OP11", "OP13"),
    ("OP12", "OP13"),
    ("OP13", "OP14"),
    # Sleeves
    ("OP15", "OP16"), ("OP16", "OP17"),
    ("OP14", "OP17"),
    ("OP17", "OP18"),
    # Side / hem
    ("OP18", "OP19"), ("OP19", "OP20"), ("OP19", "OP21"),
    # Collar attach (after placket + body assembly)
    ("OP10", "OP22"), ("OP03", "OP22"), ("OP18", "OP22"),
    ("OP22", "OP23"), ("OP23", "OP24"),
    # Labels (after neck closed)
    ("OP23", "OP25"), ("OP25", "OP26"),
    ("OP21", "OP27"),
    # Finishing chain
    ("OP24", "OP28"), ("OP21", "OP28"), ("OP26", "OP28"),
    ("OP28", "OP29"), ("OP29", "OP30"), ("OP30", "OP31"),
    ("OP31", "OP32"), ("OP32", "OP33"), ("OP33", "OP34"),
    ("OP34", "OP35"),
]
