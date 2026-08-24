from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import re
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_certificate_text(text: str) -> dict:
    data = {
        "from_date": None,
        "to_date": None,
        "commissioning_date": None,
        "issue_date": None,
        "sourcing_method": None,
        "quantity": None,
        "standard": None,
        "technology_type": None,
        "origin_countries": None,
    }

    # 1. Standard & Sourcing Method
    if re.search(r'\b(International Tracking Standard|I-REC)\b', text, re.IGNORECASE):
        data["standard"] = "I-REC (International)"
        data["sourcing_method"] = "Unbundled procurement of Energy Attribute Certificates (EACs)"
    elif re.search(r'\b(Guarantee of Origin|GO|EECS)\b', text, re.IGNORECASE):
        data["standard"] = "Guarantee of Origin (GO / EECS)"
        data["sourcing_method"] = "Unbundled procurement of Energy Attribute Certificates (EACs)"

    # 2. Quantity (MWh)
    vol_match = re.search(r'([\d\s\.,]+)\s*(?:MWh|I-REC Certificates|Megawatt[ -]hours?)', text, re.IGNORECASE)
    if vol_match:
        try:
            cleaned = vol_match.group(1).replace(' ', '').replace(',', '.')
            if cleaned.count('.') > 1:
                parts = cleaned.split('.')
                cleaned = "".join(parts[:-1]) + "." + parts[-1]
            data["quantity"] = float(cleaned)
        except ValueError:
            pass

    # 3. Technology Type
    tech_patterns = [
        (r'\b(Solar\s*PV|Solar|Fotovoltaica)\b', "Solar PV"),
        (r'\b(Wind|Onshore\s*Wind|Offshore\s*Wind|Eólica)\b', "Wind"),
        (r'\b(Hydro|Hydroelectric|Hidroeléctrica)\b', "Hydroelectric"),
        (r'\b(Biomass)\b', "Biomass"),
        (r'\b(Geothermal)\b', "Geothermal"),
    ]
    for pattern, label in tech_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            data["technology_type"] = label
            break

    # 4. Origin Country
    country_list = ["Israel", "Thailand", "Chile", "Norway", "Uruguay", "Spain", "France", "Germany", "Jordan", "Mexico", "Canada", "USA"]
    for c in country_list:
        if re.search(r'\b' + re.escape(c) + r'\b', text, re.IGNORECASE):
            data["origin_countries"] = c
            break

    # 5. Commissioning Date (Multiple English Synonyms)
    cod_match = re.search(
        r'(?:Commissioning Date|Commercial Operation Date|COD|In-Service Date|Commercial In-Service Date|Installation Date|Date of Initial Operation|Built Date|Plant Vintage)[:\s]*([0-9/\.\-]+)', 
        text, 
        re.IGNORECASE
    )
    if cod_match:
        data["commissioning_date"] = cod_match.group(1).strip()

    # 6. Issue Date / Valid Until
    issue_match = re.search(r'(?:Issue Date|Date of Issue|Effective Date)[:\s]*([0-9/\.\-]+)', text, re.IGNORECASE)
    if issue_match:
        data["issue_date"] = issue_match.group(1).strip()

    # 7. Production Dates (From Date / To Date)
    dates = re.findall(r'\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b', text)
    if len(dates) >= 2:
        data["from_date"] = dates[0]
        data["to_date"] = dates[1]

    return data

@app.post("/api/extract")
async def extract_pdf(file: UploadFile = File(...)):
    contents = await file.read()
    accumulated_text = ""
    
    with pdfplumber.open(io.BytesIO(contents)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            accumulated_text += t + "\n"
            
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    accumulated_text += " " + " ".join([str(c) for c in row if c])

    extracted = parse_certificate_text(accumulated_text)
    return extracted

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
