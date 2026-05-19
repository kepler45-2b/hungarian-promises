import json

MAIN_CHAPTER_MAP = [
    (7, 14, "Rendszerváltás békésen, felelősséggel"),
    (14, 16, "Alapvető értékeink"),
    (16, 28, "Magyarország nem működik"),
    (28, 34, "Magyarország jövőképe"),
    (34, 36, "Problémák és vállalásaink"),
    (36, 91, "Rich & Successful Country"),
    (91, 137, "Peaceful & Ordered Country"),
    (137, 204, "Free & Happy Country"),
    (204, 243, "Clean & Progressive Country"),
]

CHAPTER_MAP = [
    (36, 54, "Ganz Ábrahám Economic Development"),
    (54, 57, "Tax Reduction"),
    (57, 67, "Stable Budget"),
    (67, 72, "Utility Cost Reduction"),
    (72, 86, "Infrastructure Development"),
    (86, 91, "Wekerle Sándor Housing Program"),
    (91, 96, "Border Security"),
    (96, 101, "Public Order & Safety"),
    (101, 104, "Zero Tolerance Immigration"),
    (104, 109, "National Sovereignty"),
    (109, 114, "Demographic Recovery & Diaspora"),
    (114, 118, "Fair Hungary"),
    (118, 125, "Bibó István Rule of Law"),
    (125, 132, "Functioning State & Local Government"),
    (132, 137, "Strong Communities"),
    (137, 148, "Hugonnai Vilma Healthcare"),
    (148, 151, "Pension Increase"),
    (151, 158, "Brunszvik Teréz Child Protection"),
    (158, 164, "100% Family Program"),
    (164, 180, "Smart Nation & Education"),
    (180, 184, "Accessible Hungary"),
    (184, 189, "Equal Opportunities for Women"),
    (189, 194, "Roma Equal Opportunity"),
    (194, 197, "Hajós Alfréd Sports"),
    (197, 204, "Free Culture & Arts"),
    (204, 218, "Green Hungary"),
    (218, 223, "Agriculture & Food Industry"),
    (223, 228, "Xantus János Animal Protection"),
    (228, 233, "Szent István Rural Development"),
    (233, 243, "Preparing for the Future"),
]

def get_main_chapter(page):
    if not page:
        return "Unknown"
    try:
        page = int(page)
    except (ValueError, TypeError):
        return "Unknown"
    for start, end, name in MAIN_CHAPTER_MAP:
        if start <= page < end:
            return name
    return "Unknown"

def get_chapter(page):
    if not page:
        return "Unknown"
    try:
        page = int(page)
    except (ValueError, TypeError):
        return "Unknown"
    for start, end, name in CHAPTER_MAP:
        if start <= page < end:
            return name
    return "Unknown"

def add_chapters():
    with open("data/promises.json", encoding="utf-8") as f:
        promises = json.load(f)
    
    for p in promises:
        p["category_main"] = get_main_chapter(p.get("page_hint"))
        p["category_chapter"] = get_chapter(p.get("page_hint"))
        try:
            p["category_ai"] = p.pop("category")
        except KeyError:
            pass
    
    with open("data/promises.json", "w", encoding="utf-8") as f:
        json.dump(promises, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Added chapter categories to {len(promises)} promises")
    print("\nSample:")
    print(json.dumps(promises[0], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    add_chapters()