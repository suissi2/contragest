# Import Public Holidays SOP

This SOP outlines the workflow for importing public holidays into the Contragest attendance system database.

## 1. Directive Goal
Automatically fetch public/national holidays from the web (using Nager.Date API via `execution/fetch_public_holidays.py`) and bulk upsert them into the database so they can be used for JF/JFB STAT computation.

## 2. Input Parameters
- **Year**: The four-digit year for which to retrieve holidays (e.g., 2026).
- **Country Code**: The two-letter ISO country code (e.g., TN for Tunisia, FR for France).

## 3. Tool Execution
Run the deterministic script to fetch the holiday list in JSON format:
```bash
python execution/fetch_public_holidays.py <year> <country_code>
```

## 4. Processing & Persistence
- For each holiday returned, verify if a record with the same date already exists in the `public_holidays` database table.
- If it exists, update its name and description.
- If it does not exist, insert it.
- Finally, refresh the UI calendar grid.
