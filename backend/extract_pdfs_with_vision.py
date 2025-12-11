"""
PDF Extraction using OpenAI Vision API

This script converts PDF pages to images and uses OpenAI's Vision API
to extract text content. Much more reliable than PyPDF2 for complex PDFs.
"""
import base64
import io
import logging
from pathlib import Path
from typing import List
import sys

from pdf2image import convert_from_path
from PIL import Image
from openai import OpenAI

from config import OPENAI_API_KEY, RAW_DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VisionPDFExtractor:
    """Extract text from PDFs using OpenAI Vision API"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Supports vision and is cost-effective

    def pdf_page_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        # Resize if too large (max 2048px on longest side for efficiency)
        max_size = 2048
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()

    def extract_text_from_image(self, image_base64: str, page_num: int) -> str:
        """Use OpenAI Vision API to extract text from image"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Extract ALL text content from this image.

Instructions:
- Extract all visible text exactly as it appears
- Preserve formatting, bullet points, and structure
- Include headers, subheaders, and body text
- For tables, format them clearly with columns
- If there are diagrams with labels, include the labels
- Do NOT add any commentary or descriptions
- Just output the raw text content

Begin extraction:"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.0  # Deterministic extraction
            )

            extracted_text = response.choices[0].message.content
            logger.info(f"✓ Extracted text from page {page_num} ({len(extracted_text)} chars)")
            return extracted_text

        except Exception as e:
            logger.error(f"Error extracting text from page {page_num}: {e}")
            return f"[Error extracting page {page_num}]"

    def extract_pdf(self, pdf_path: Path) -> str:
        """Extract all text from a PDF file"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Extracting: {pdf_path.name}")
        logger.info(f"{'='*60}")

        try:
            # Convert PDF to images
            logger.info("Converting PDF pages to images...")
            poppler_path = r"C:\Users\joshual\poppler\poppler-24.08.0\Library\bin"
            images = convert_from_path(str(pdf_path), dpi=150, poppler_path=poppler_path)
            logger.info(f"Found {len(images)} pages")

            # Extract text from each page
            all_text = []
            for i, image in enumerate(images, 1):
                logger.info(f"Processing page {i}/{len(images)}...")
                image_base64 = self.pdf_page_to_base64(image)
                text = self.extract_text_from_image(image_base64, i)
                all_text.append(f"\n\n--- Page {i} ---\n\n{text}")

            combined_text = "\n".join(all_text)
            logger.info(f"\n✅ Successfully extracted {len(combined_text)} characters from {pdf_path.name}")
            return combined_text

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path.name}: {e}")
            return ""

    def save_extracted_text(self, pdf_path: Path, text: str) -> Path:
        """Save extracted text to a file"""
        # Create output filename
        output_dir = RAW_DATA_DIR / "extracted"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"{pdf_path.stem}.txt"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Extracted from: {pdf_path.name}\n\n")
            f.write(text)

        logger.info(f"💾 Saved to: {output_file}")
        return output_file


def main():
    """Main extraction process"""
    logger.info("="*60)
    logger.info("PDF Extraction with OpenAI Vision API")
    logger.info("="*60)

    # Find all PDFs
    pdf_files = list(RAW_DATA_DIR.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDF files found in {RAW_DATA_DIR}")
        logger.info("Please add PDF files to the data/raw directory")
        sys.exit(1)

    logger.info(f"\nFound {len(pdf_files)} PDF file(s):")
    for pdf in pdf_files:
        logger.info(f"  - {pdf.name}")

    # Initialize extractor
    extractor = VisionPDFExtractor()

    # Process each PDF
    extracted_files = []
    for pdf_path in pdf_files:
        text = extractor.extract_pdf(pdf_path)
        if text:
            output_file = extractor.save_extracted_text(pdf_path, text)
            extracted_files.append(output_file)

    # Summary
    logger.info("\n" + "="*60)
    logger.info("EXTRACTION COMPLETE")
    logger.info("="*60)
    logger.info(f"✅ Extracted {len(extracted_files)} PDF(s)")
    logger.info(f"📁 Text files saved to: {RAW_DATA_DIR / 'extracted'}")
    logger.info("\nNext steps:")
    logger.info("1. Review the extracted text files")
    logger.info("2. Move them to data/raw/ if they look good")
    logger.info("3. Run: python ingest_docs.py")
    logger.info("\nNote: Original PDFs are untouched")


if __name__ == "__main__":
    main()
