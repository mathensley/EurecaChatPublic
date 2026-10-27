import csv

def json_to_csv(json_data, csv_path):
    data = json_data if isinstance(json_data, list) else [json_data]
    if type(json_data) is list: pass
    else: return

    if len(data) >= 100: return
    if not data: return

    fieldnames = []
    for item in data:
        for key in item.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    return f"""
    CSV nome do CSV salvo: {csv_path} com ({len(data)}) registros contendo dados como {data[0].keys()}.
    """