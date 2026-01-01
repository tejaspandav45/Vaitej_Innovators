def validate_common(data):
    required = ["full_name", "email", "password", "phone", "country"]
    return all(data.get(field) for field in required)


def validate_founder(data):
    required = [
        "company_name",
        "founding_year",
        "stage",
        "sector",
        "business_model",
        "actively_raising"
    ]
    return all(data.get(field) for field in required)


def validate_investor(data):
    required = [
        "fund_name",
        "investment_stage",
        "sector_focus",
        "geography_focus",
        "check_size"
    ]
    return all(data.get(field) for field in required)
