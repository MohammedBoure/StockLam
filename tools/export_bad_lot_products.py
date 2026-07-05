from __future__ import annotations

import argparse
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
EXCEL_EPOCH = datetime(1899, 12, 30)
DATE_COLUMNS = {
    "Expiry_Date",
    "Created_At",
    "Deleted_At",
    "Order_Date",
    "Expected_Delivery_Date",
    "Reception_Date",
    "Updated_At",
    "Date_of_Purchase",
}


def column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref or "A")
    letters = match.group(1) if match else "A"
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def column_letter(index: int) -> str:
    index += 1
    letters = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def excel_date(value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value or ""
    parsed = EXCEL_EPOCH + timedelta(days=number)
    if abs(number - int(number)) < 0.000001:
        return parsed.strftime("%Y-%m-%d")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("x:si", NS):
                shared_strings.append("".join(t.text or "" for t in item.findall(".//x:t", NS)))

        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row in root.findall(".//x:sheetData/x:row", NS):
            values: dict[int, str] = {}
            max_index = -1
            for cell in row.findall("x:c", NS):
                idx = column_index(cell.get("r", "A1"))
                max_index = max(max_index, idx)
                cell_type = cell.get("t")
                if cell_type == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//x:t", NS))
                else:
                    node = cell.find("x:v", NS)
                    value = "" if node is None else node.text or ""
                    if cell_type == "s" and value:
                        value = shared_strings[int(value)]
                values[idx] = value
            rows.append([values.get(i, "") for i in range(max_index + 1)])

    if not rows:
        return []

    headers = rows[0]
    records: list[dict[str, str]] = []
    for raw_row in rows[1:]:
        record = {header: raw_row[i] if i < len(raw_row) else "" for i, header in enumerate(headers)}
        for key in DATE_COLUMNS.intersection(record):
            if record[key]:
                record[key] = excel_date(record[key])
        records.append(record)
    return records


def key(value: object) -> str:
    return str(value or "").strip()


def index_by(rows: Iterable[dict[str, str]], field: str) -> dict[str, dict[str, str]]:
    return {key(row.get(field)): row for row in rows if key(row.get(field))}


def lot_problem(value: str) -> str | None:
    stripped = key(value)
    if not stripped:
        return "EMPTY"
    if stripped.upper() == "NON_DEFINI":
        return "NON_DEFINI"
    if stripped.upper() == "N/A":
        return "N/A"
    if re.fullmatch(r"\.+", stripped):
        return "DOTS"
    return None


def build_report_rows(source_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    batches = read_xlsx_rows(source_dir / "inventory_batches.xlsx")
    products = index_by(read_xlsx_rows(source_dir / "products_master.xlsx"), "Product_ID")
    families = index_by(read_xlsx_rows(source_dir / "product_families.xlsx"), "Family_ID")
    manufacturers = index_by(read_xlsx_rows(source_dir / "manufacturers.xlsx"), "Manuf_ID")
    automates = index_by(read_xlsx_rows(source_dir / "automates.xlsx"), "Automate_ID")
    locations = index_by(read_xlsx_rows(source_dir / "locations.xlsx"), "Location_ID")
    receptions = index_by(read_xlsx_rows(source_dir / "reception_log.xlsx"), "BR_ID")
    purchase_orders = index_by(read_xlsx_rows(source_dir / "purchase_orders.xlsx"), "PO_ID")
    suppliers = index_by(read_xlsx_rows(source_dir / "suppliers.xlsx"), "Supplier_ID")

    detailed_rows: list[dict[str, str]] = []
    product_summary: dict[str, dict[str, str]] = {}
    batch_counts: defaultdict[str, int] = defaultdict(int)
    qty_current_totals: defaultdict[str, float] = defaultdict(float)

    for batch in batches:
        problem = lot_problem(batch.get("Lot_Number", ""))
        if not problem:
            continue

        product_id = key(batch.get("Product_ID"))
        product = products.get(product_id, {})
        family = families.get(key(product.get("Family_ID")), {})
        manufacturer = manufacturers.get(key(product.get("Manuf_ID")), {})
        automate = automates.get(key(product.get("Preferred_Automate_ID")), {})
        location = locations.get(key(batch.get("Location_ID")), {})
        reception = receptions.get(key(batch.get("BR_ID")), {})
        purchase_order = purchase_orders.get(key(batch.get("PO_ID")), {})
        supplier_id = key(reception.get("Supplier_ID")) or key(purchase_order.get("Supplier_ID"))
        supplier = suppliers.get(supplier_id, {})

        row = {
            "Problem_Type": problem,
            "Batch_ID": batch.get("Batch_ID", ""),
            "Internal_Barcode": batch.get("Internal_Barcode", ""),
            "Lot_Number": batch.get("Lot_Number", ""),
            "Product_ID": product_id,
            "Product_Name": product.get("Product_Name", ""),
            "Family_Name": family.get("Family_Name", ""),
            "Manuf_Name": manufacturer.get("Manuf_Name", ""),
            "Automate_Name": automate.get("Automate_Name", ""),
            "Barcode": product.get("Barcode", ""),
            "Manuf_Cat_No": product.get("Manuf_Cat_No", ""),
            "Ordering_Unit": product.get("Ordering_Unit", ""),
            "Stock_Unit": product.get("Stock_Unit", ""),
            "Stock_Qty_Per_Order_Unit": product.get("Stock_Qty_Per_Order_Unit", ""),
            "Usage_Unit": product.get("Usage_Unit", ""),
            "Usage_Qty_Per_Stock_Unit": product.get("Usage_Qty_Per_Stock_Unit", ""),
            "Minimum_Stock_Level": product.get("Minimum_Stock_Level", ""),
            "Alert_Before_Expiry_Days": product.get("Alert_Before_Expiry_Days", ""),
            "Open_Vial_Stability_Days": product.get("Open_Vial_Stability_Days", ""),
            "Storage_Temp_Req": product.get("Storage_Temp_Req", ""),
            "Is_Billable": product.get("Is_Billable", ""),
            "Product_Deleted_At": product.get("Deleted_At", ""),
            "Location_ID": batch.get("Location_ID", ""),
            "Location_Name": location.get("Location_Name", ""),
            "Expiry_Date": batch.get("Expiry_Date", ""),
            "Quantity_Initial": batch.get("Quantity_Initial", ""),
            "Quantity_Current": batch.get("Quantity_Current", ""),
            "Unit_Price_Received": batch.get("Unit_Price_Received", ""),
            "Tax_Rate_Percent": batch.get("Tax_Rate_Percent", ""),
            "Discount_Percent": batch.get("Discount_Percent", ""),
            "Batch_Status": batch.get("Status", ""),
            "Reception_Note": batch.get("Reception_Note", ""),
            "Batch_Created_At": batch.get("Created_At", ""),
            "PO_ID": batch.get("PO_ID", ""),
            "BR_ID": batch.get("BR_ID", ""),
            "Supplier_Name": supplier.get("Supplier_Name", ""),
            "Supplier_Invoice_Ref": reception.get("Supplier_Invoice_Ref") or purchase_order.get("Supplier_Invoice_Ref", ""),
            "Supplier_BL_Ref": reception.get("Supplier_BL_Ref", ""),
            "Reception_Date": reception.get("Reception_Date") or purchase_order.get("Reception_Date", ""),
            "PO_Order_Date": purchase_order.get("Order_Date", ""),
            "PO_Status": purchase_order.get("Status", ""),
        }
        detailed_rows.append(row)

        batch_counts[product_id] += 1
        try:
            qty_current_totals[product_id] += float(batch.get("Quantity_Current") or 0)
        except ValueError:
            pass
        product_summary.setdefault(
            product_id,
            {
                "Product_ID": product_id,
                "Product_Name": product.get("Product_Name", ""),
                "Family_Name": family.get("Family_Name", ""),
                "Manuf_Name": manufacturer.get("Manuf_Name", ""),
                "Automate_Name": automate.get("Automate_Name", ""),
                "Barcode": product.get("Barcode", ""),
                "Manuf_Cat_No": product.get("Manuf_Cat_No", ""),
                "Stock_Unit": product.get("Stock_Unit", ""),
                "Minimum_Stock_Level": product.get("Minimum_Stock_Level", ""),
            },
        )

    summary_rows = []
    for product_id, row in sorted(product_summary.items(), key=lambda item: item[1].get("Product_Name", "")):
        summary = dict(row)
        summary["Problem_Batch_Count"] = str(batch_counts[product_id])
        summary["Problem_Current_Qty_Total"] = f"{qty_current_totals[product_id]:g}"
        summary_rows.append(summary)

    detailed_rows.sort(key=lambda row: (row.get("Product_Name", ""), row.get("Batch_ID", "")))
    return detailed_rows, summary_rows


def xml_cell(row_index: int, col_index: int, value: object, style: str | None = None) -> str:
    ref = f"{column_letter(col_index)}{row_index}"
    text = escape("" if value is None else str(value))
    style_attr = f' s="{style}"' if style else ""
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{text}</t></is></c>'


def worksheet_xml(headers: list[str], rows: list[dict[str, str]], sheet_name: str) -> str:
    all_rows = [headers] + [[row.get(header, "") for header in headers] for row in rows]
    xml_rows = []
    for row_index, values in enumerate(all_rows, start=1):
        cells = [
            xml_cell(row_index, col_index, value, "1" if row_index == 1 else None)
            for col_index, value in enumerate(values)
        ]
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    last_col = column_letter(max(len(headers) - 1, 0))
    last_row = max(len(all_rows), 1)
    columns = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{min(max(len(header) + 2, 12), 34)}" customWidth="1"/>'
        for i, header in enumerate(headers)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<dimension ref="A1:{last_col}{last_row}"/>
<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols>{columns}</cols>
<sheetData>{"".join(xml_rows)}</sheetData>
<autoFilter ref="A1:{last_col}{last_row}"/>
<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>"""


def write_xlsx(path: Path, sheets: list[tuple[str, list[str], list[dict[str, str]]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
"""
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
"""
            + "".join(
                f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
"""
            + "".join(
                f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                for i, (name, _headers, _rows) in enumerate(sheets, start=1)
            )
            + "</sheets></workbook>",
        )
        archive.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>""",
        )
        created = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        archive.writestr(
            "docProps/core.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:creator>StockLam export</dc:creator><cp:lastModifiedBy>StockLam export</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>""",
        )
        archive.writestr(
            "docProps/app.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>StockLam export</Application></Properties>""",
        )
        for i, (name, headers, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", worksheet_xml(headers, rows, name))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export products with undefined or dotted lot numbers.")
    parser.add_argument("--source-dir", default="sauvegarde_excel_20260704_144952")
    parser.add_argument("--output", default="reports/produits_lot_non_defini_avec_na_20260705.xlsx")
    args = parser.parse_args()

    details, summary = build_report_rows(Path(args.source_dir))
    detail_headers = list(details[0]) if details else ["Problem_Type"]
    summary_headers = list(summary[0]) if summary else ["Product_ID", "Product_Name"]
    metadata = [
        {"Metric": "Source_Directory", "Value": args.source_dir},
        {"Metric": "Problem_Batch_Count", "Value": str(len(details))},
        {"Metric": "Problem_Product_Count", "Value": str(len(summary))},
        {"Metric": "Generated_At", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "Lot_Filter", "Value": "NON_DEFINI, N/A, empty, or dots only"},
    ]

    write_xlsx(
        Path(args.output),
        [
            ("Produits_A_Suivre", detail_headers, details),
            ("Produits_Uniques", summary_headers, summary),
            ("Resume", ["Metric", "Value"], metadata),
        ],
    )
    print(f"Wrote {args.output}")
    print(f"Problem batches: {len(details)}")
    print(f"Problem products: {len(summary)}")


if __name__ == "__main__":
    main()
