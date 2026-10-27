def dicts_to_markdown_table(data: list[dict]):
        # Só converte se for uma lista de dicionários
        if not (
            isinstance(data, list)
            and data
            and all(isinstance(item, dict) for item in data)
        ):
            return data

        headers = list(data[0].keys())

        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]

        for row in data:
            values = [str(row.get(col, "")) for col in headers]
            lines.append("| " + " | ".join(values) + " |")

        return "\n".join(lines)
