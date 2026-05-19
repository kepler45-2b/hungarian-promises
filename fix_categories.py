import json

CATEGORY_RULES = [
    ("Minority Rights", ["Roma Inclusion", "Minority Rights", "Diaspora", "Repatriation", "Citizenship"]),
    ("Democracy & Anti-Corruption", ["Anti-Corruption", "Anti-corruption", "Transparency", "Electoral Rights", "Civil Society", "Media Reform", "Rule of Law", "Accountability", "Asset Recovery", "Historical"]),
    ("Foreign Policy & Defense", ["Foreign Policy", "Foreign Affairs", "Defense", "National Security", "Sovereignty", "Cybersecurity", "International Relations", "Diplomacy"]),
    ("Healthcare", ["Healthcare", "Health", "Medical"]),
    ("Education", ["Education", "Science & Research", "Science and Tech", "Innovation", "Literature", "Music & Ed"]),
    ("Economy", ["Economy", "Fiscal Policy", "Taxation", "Investment", "Industry", "Monetary", "Debt Management", "Public Finance", "SME", "Euro Adoption", "Blockchain", "Crypto", "Tourism", "Employment", "Labor"]),
    ("Housing", ["Housing", "Urban Development", "Construction"]),
    ("Transport", ["Transport", "Rail", "Road Safety"]),
    ("Agriculture", ["Agricult", "Food", "Rural Development", "Organic Farming", "Horticulture", "Animal Welfare", "Animal Husbandry", "Wildlife"]),
    ("Environment", ["Environment", "Nature", "Climate", "Water", "Waste", "Air Quality", "Coastal", "Composting", "Recycling", "Habitat", "Green"]),
    ("Culture & Sport", ["Culture", "Sport", "Film", "Music", "Heritage", "Media", "Arts", "Literature", "Libraries"]),
    ("Energy", ["Energy", "Geothermal", "Clean Energy"]),
    ("Social Policy", ["Social", "Family", "Pension", "Disability", "Women", "Child Protection", "Human Rights", "Quality of Life"]),
    ("Justice & Rule of Law", ["Justice", "Legislation", "Consumer Protection", "Public Safety", "Law Enforcement"]),
    ("Public Administration", ["Public Administration", "Governance", "Local Government", "Public Procurement", "Digitalization", "Public Service", "Public Institution"]),
]

def map_category(cat):
    for standard, keywords in CATEGORY_RULES:
        if any(kw.lower() in cat.lower() for kw in keywords):
            return standard
    return "Public Administration"  # sensible default

def fix_categories():
    with open("data/promises.json", encoding="utf-8") as f:
        promises = json.load(f)

    for p in promises:
        p["category_ai"] = map_category(p["category_ai"])

    with open("data/promises.json", "w", encoding="utf-8") as f:
        json.dump(promises, f, ensure_ascii=False, indent=2)

    cats = sorted(set(p["category_ai"] for p in promises))
    print(f"Done! {len(cats)} categories across {len(promises)} promises:")
    for c in cats:
        count = sum(1 for p in promises if p["category_ai"] == c)
        print(f"  {c}: {count}")

if __name__ == "__main__":
    fix_categories()