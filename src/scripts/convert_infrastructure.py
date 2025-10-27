#!/usr/bin/env python3
"""
Infrastructure CSV/XLSX to JSON Converter CLI

Usage:
    uv run python scripts/convert_infrastructure.py path/to/infrastructure.csv
    uv run python scripts/convert_infrastructure.py path/to/infrastructure.xlsx
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.converters.infrastructure_converter import (
    csv_to_categorized_json,
    xlsx_to_categorized_json,
    create_condensed_context,
    get_infrastructure_path,
)


def convert_file(input_path: str):
    """Auto-detect file type and convert."""
    input_file = Path(input_path)
    
    if not input_file.exists():
        print(f"❌ Error: File not found: {input_path}")
        sys.exit(1)
    
    print(f"🚀 Converting infrastructure inventory: {input_file.name}\n")
    
    # Determine output paths
    json_output = get_infrastructure_path("infrastructure_context.json")
    text_output = get_infrastructure_path("infrastructure_condensed.txt")
    
    # Convert based on file type
    if input_file.suffix.lower() == '.csv':
        print(f"📄 Converting CSV...")
        data = csv_to_categorized_json(input_file, json_output)
        
    elif input_file.suffix.lower() in ['.xlsx', '.xls']:
        print(f"📊 Converting XLSX...")
        output_dir = get_infrastructure_path("", subdir="processed").parent / "processed"
        all_sheets = xlsx_to_categorized_json(input_file, output_dir)
        
        # Use first sheet or combined data
        if len(all_sheets) == 1:
            data = list(all_sheets.values())[0]
        else:
            # Merge all sheets
            data = {}
            for sheet_data in all_sheets.values():
                for category, products in sheet_data.items():
                    if category not in data:
                        data[category] = []
                    data[category].extend(products)
    else:
        print(f"❌ Error: Unsupported file type: {input_file.suffix}")
        print("   Supported formats: .csv, .xlsx, .xls")
        sys.exit(1)
    
    # Create condensed text version
    print(f"\n📝 Creating condensed text format...")
    condensed = create_condensed_context(data, text_output)
    
    # Print statistics
    print("\n" + "=" * 60)
    print("📊 CONVERSION SUMMARY")
    print("=" * 60)
    total_products = sum(len(products) for products in data.values())
    print(f"✅ Total products processed: {total_products}")
    print(f"\n📦 Products per category:")
    for category, products in sorted(data.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   {category:30s}: {len(products):3d} products")
    
    # Token estimate
    token_estimate = len(condensed.split()) * 1.3
    print(f"\n🪙 Estimated tokens (condensed format): ~{int(token_estimate)}")
    
    print(f"\n💾 Output files:")
    print(f"   JSON:  {json_output}")
    print(f"   Text:  {text_output}")
    
    print("\n✅ Conversion complete!")
    print("\n💡 Next steps:")
    print("   • Review the generated JSON/text files")
    print("   • Use load_infrastructure_context() in your analyzers")
    print("   • Update analyzer_manager.py to include this context")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/convert_infrastructure.py <input_file>")
        print("\nExample:")
        print("  uv run python scripts/convert_infrastructure.py data/infrastructure/raw/infrastructure.csv")
        print("  uv run python scripts/convert_infrastructure.py data/infrastructure/raw/infrastructure.xlsx")
        sys.exit(1)
    
    convert_file(sys.argv[1])