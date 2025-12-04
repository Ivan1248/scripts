from datetime import datetime, timedelta

def generate_events(compact_text: str):
    """
    Parse compact event schedule format and generate event entries.

    This function converts a compact multi-block text format into individual event entries.
    Each block represents a location and its associated events over a date range.

    Args:
        compact_text (str): Multi-block schedule in compact format. Each block contains:
            - Header: "location|start_date|duration_hours"
            - Event lines: "day_offset|start_hour*count"
            
            Blocks are separated by blank lines.
            Event lines specify when events occur relative to start_date.

    Returns:
        list[str]: Event entries in format "YYYY-MM-DD|HH:00|HH:00|location",
                   with blank lines separating different dates and locations.

    Example:
        >>> text = '''
        ... A109|2025-12-15|2
        ... 0|13*2
        ... 1|9*1
        ...
        ... A110|2025-12-15|2
        ... 0|11*1
        ... '''
        >>> events = generate_events(text)
        >>> for event in events:
        ...     print(event)
        2025-12-15|13:00|15:00|A109
        2025-12-15|15:00|17:00|A109
        
        2025-12-16|09:00|11:00|A109
        
        2025-12-15|11:00|13:00|A110

    The format explanation:
        - Location: Room/location identifier (e.g., "A109")
        - Start date: Base date for calculations (YYYY-MM-DD)
        - Duration: Hours per event
        - Day offset: Number of days relative to start_date (0 = start_date itself)
        - Start hour: Hour when first event starts (24-hour format)
        - Count: Number of consecutive events at that hour
    """
    events = []

    blocks = [b.strip() for b in compact_text.strip().split("\n\n")]

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        header = lines[0]

        location, start_date_str, duration_str = header.split("|")
        base_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        duration = int(duration_str)

        last_date = None

        for line in lines[1:]:
            day_offset_part, time_part = line.split("|")
            start_hour_str, count_part = time_part.split("*")

            day_offset = int(day_offset_part.strip())
            start_hour = int(start_hour_str.strip())
            count = int(count_part.strip())

            event_date = base_date + timedelta(days=day_offset)

            # Insert empty line when day changes (but not at very beginning)
            if last_date is not None and event_date != last_date:
                events.append("")

            last_date = event_date

            for i in range(count):
                start_hour_i = start_hour + i * duration
                end_hour_i = start_hour_i + duration

                start_time = f"{start_hour_i:02d}:00"
                end_time = f"{end_hour_i:02d}:00"

                events.append(
                    f"{event_date}|{start_time}|{end_time}|{location}"
                )

        # Separate different locations with an empty line
        events.append("\n")

    # Remove trailing empty lines
    while events and events[-1] == "":
        events.pop()

    return events


# -----------------------------
# Example Usage
# -----------------------------

if __name__ == "__main__":
    compact_input = """
A109|2025-12-15|2
0|13 *3
1|9  *6
2|10 *5
3|11 *4
4|11 *3

A110|2025-12-15|2
0|11 *4
1|9  *6
2|10 *5
3|11 *4
4|11 *3
"""

    generated = generate_events(compact_input)

    for line in generated:
        print(line)
