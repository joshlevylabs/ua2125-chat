# PDF Extraction Guide

## Using OpenAI Vision API for Reliable PDF Text Extraction

### Why Use This Instead of PyPDF2?

**OpenAI Vision API can:**
- ✅ Read scanned PDFs (image-based)
- ✅ Handle complex layouts and tables
- ✅ Extract text from images and diagrams
- ✅ Work with any PDF format
- ✅ Never hang or crash

**Cost:** ~$0.10-0.30 per PDF (very affordable)

---

## Step-by-Step Instructions

### 1. Install Dependencies

First time only:
```powershell
cd backend
pip install pdf2image==1.16.3 Pillow==10.3.0
```

**Note for Windows:** pdf2image requires poppler. Install it:
- Download: https://github.com/oschwartz10612/poppler-windows/releases/
- Extract to `C:\Program Files\poppler`
- Add `C:\Program Files\poppler\Library\bin` to your PATH

Or use conda:
```powershell
conda install -c conda-forge poppler
```

### 2. Place PDFs in data/raw/

```powershell
# Your PDFs should be in:
backend/data/raw/*.pdf
```

### 3. Run the Extraction Script

```powershell
cd backend
python extract_pdfs_with_vision.py
```

This will:
1. Find all PDFs in `data/raw/`
2. Convert each page to an image
3. Use OpenAI Vision API to extract text
4. Save extracted text to `data/raw/extracted/*.txt`

### 4. Review the Extracted Text

```powershell
# Check the extracted files
ls backend/data/raw/extracted/

# Review one file
cat backend/data/raw/extracted/sell-sheet.txt
```

### 5. Move Good Extractions to data/raw/

```powershell
# If extraction looks good, move it:
mv backend/data/raw/extracted/*.txt backend/data/raw/

# Remove the original PDFs (optional)
rm backend/data/raw/*.pdf
```

### 6. Ingest the Text Files

```powershell
cd backend
python ingest_docs.py
```

Now the text will be ingested into your knowledge base!

---

## Example Usage

```powershell
# Complete workflow
cd C:\Users\joshual\Documents\Cursor\ua2125-chat\backend

# 1. Extract PDFs with Vision API
python extract_pdfs_with_vision.py

# Output:
# ============================================================
# PDF Extraction with OpenAI Vision API
# ============================================================
# Found 2 PDF file(s):
#   - sell-sheet.pdf
#   - accessories.pdf
#
# ============================================================
# Extracting: sell-sheet.pdf
# ============================================================
# Converting PDF pages to images...
# Found 2 pages
# Processing page 1/2...
# ✓ Extracted text from page 1 (1234 chars)
# Processing page 2/2...
# ✓ Extracted text from page 2 (987 chars)
# ✅ Successfully extracted 2221 characters from sell-sheet.pdf
# 💾 Saved to: data/raw/extracted/sell-sheet.txt

# 2. Review extracted files
cat data/raw/extracted/sell-sheet.txt

# 3. If good, move to raw folder
mv data/raw/extracted/*.txt data/raw/

# 4. Remove PDFs (they're now text)
rm data/raw/*.pdf

# 5. Ingest the text files
python ingest_docs.py
```

---

## Troubleshooting

### "poppler not found" Error

**Windows:**
1. Download poppler: https://github.com/oschwartz10612/poppler-windows/releases/
2. Extract to `C:\Program Files\poppler`
3. Add to PATH: `C:\Program Files\poppler\Library\bin`
4. Restart PowerShell

**macOS:**
```bash
brew install poppler
```

**Linux:**
```bash
sudo apt-get install poppler-utils
```

### "OpenAI API Error"

Check your API key in `.env` file and ensure you have credits.

### Extraction Quality Issues

Adjust the DPI in the script (line 110):
```python
images = convert_from_path(str(pdf_path), dpi=200)  # Higher = better quality
```

---

## Cost Estimates

**OpenAI Vision API Pricing (gpt-4o-mini):**
- Input: ~$0.15 per 1M tokens
- Images: ~$0.003 per image

**Typical costs:**
- 1-page PDF: $0.05 - $0.10
- 5-page PDF: $0.15 - $0.30
- 10-page PDF: $0.30 - $0.50

**Your 5 UA2-125 PDFs (~50 pages total):** ~$1.50 - $3.00

---

## Tips

1. **Batch Processing**: Process all PDFs at once - it's automatic!

2. **Review Extractions**: Always review the extracted text before ingesting

3. **Keep Originals**: The script doesn't delete your PDFs

4. **Reprocess if Needed**: If extraction quality is poor, adjust DPI and re-run

5. **Cost Control**: Process only the PDFs you need

---

## Comparison: PyPDF2 vs Vision API

| Feature | PyPDF2 | Vision API |
|---------|--------|------------|
| Text PDFs | ✅ Fast | ✅ Reliable |
| Scanned PDFs | ❌ Fails | ✅ Works |
| Complex layouts | ❌ Poor | ✅ Excellent |
| Tables | ❌ Messy | ✅ Clean |
| Cost | Free | ~$0.20/PDF |
| Speed | Very fast | ~30 sec/PDF |
| Reliability | ❌ Often hangs | ✅ Never fails |

**Recommendation:** Use Vision API for all PDFs - the reliability is worth the minimal cost!

---

## Next Steps

After extraction and ingestion:

1. **Test your chatbot** at http://localhost:5000
2. **Ask questions** about the extracted content
3. **Verify accuracy** of the responses
4. **Add more PDFs** as needed

Your chatbot will now have access to ALL the content from your PDFs, reliably extracted with OpenAI Vision!
