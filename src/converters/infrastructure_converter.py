"""
Infrastructure Inventory Converter
Converts CSV/XLSX infrastructure data to LLM-friendly JSON format
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# ==============================================================
# 🗂️ Path Management
# ==============================================================

def get_infrastructure_path(filename: str, subdir: str = "processed") -> Path:
    """Get path to infrastructure data files."""
    from src.utils.path_utils import get_base_path
    base = get_base_path() / "data" / "infrastructure" / subdir
    base.mkdir(parents=True, exist_ok=True)
    return base / filename

# ==============================================================
# 🏷️ Categorization Logic
# ==============================================================

def categorize_product(row: pd.Series) -> str:
    """
    Automatically categorize products based on their attributes.
    """
    product_type = str(row.get('Product type', '')).lower()
    accessibility = str(row.get('Accessibility', '')).lower()
    context = str(row.get('Context (why and for what we use it)', '')).lower()
    notes = str(row.get('Notes', '')).lower()
    
    # External facing services (highest priority for security)
    if 'external' in accessibility:
        return 'external_facing'
    
    # SaaS services
    if 'saas' in product_type:
        return 'saas_services'
    
    # Server installations (internal infrastructure)
    if 'server' in product_type:
        if any(word in context or word in notes for word in ['monitor', 'observability', 'metrics', 'logging', 'trace', 'prometheus', 'grafana', 'jaeger']):
            return 'monitoring_observability'
        elif any(word in context or word in notes for word in ['database', 'data', 'storage', 'redis', 'sql', 'mariadb', 'postgres']):
            return 'databases'
        elif any(word in context or word in notes for word in ['container', 'orchestration', 'kubernetes', 'docker', 'harbor']):
            return 'container_platform'
        elif any(word in context or word in notes for word in ['proxy', 'load balancer', 'reverse proxy', 'haproxy', 'traefik']):
            return 'networking_proxy'
        elif any(word in context or word in notes for word in ['vault', 'secret', 'authentication', 'ldap', 'kerberos', 'freeipa']):
            return 'security_identity'
        else:
            return 'infrastructure_tools'
    
    # Workstation installations
    if 'workstation' in product_type:
        return 'development_tools'
    
    # Libraries
    if 'library' in product_type:
        return 'libraries_frameworks'
    
    # Default
    return 'other'

# ==============================================================
# 🧹 Data Cleaning
# ==============================================================

def clean_value(value: Any) -> str:
    """Clean and normalize values from CSV/Excel."""
    if pd.isna(value) or value == '' or value == ' ':
        return ''
    return str(value).strip()

def process_row_to_dict(row: pd.Series) -> Optional[Dict[str, Any]]:
    """Convert a CSV/Excel row to a structured dictionary."""
    product = clean_value(row.get('Product', ''))
    if not product:
        return None
    
    return {
        'product': product,
        'vendor': clean_value(row.get('Vendor', '')),
        'type': clean_value(row.get('Product type', '')).lower().replace(' ', '_'),
        'license': clean_value(row.get('License type', '')).lower().replace(' ', '_'),
        'license_name': clean_value(row.get('License', '')),
        'exposure': clean_value(row.get('Accessibility', '')).lower().replace('/', '_'),
        'used_by': clean_value(row.get('Consumer', '')).lower(),
        'use_category': clean_value(row.get('Use  - category', '')).lower(),
        'purpose': clean_value(row.get('Context (why and for what we use it)', '')),
        'notes': clean_value(row.get('Notes', ''))
    }

# ==============================================================
# 📊 CSV to JSON Converter
# ==============================================================

def csv_to_categorized_json(csv_path: str | Path, output_path: Optional[str | Path] = None) -> Dict[str, List[Dict]]:
    """
    Convert CSV to categorized JSON structure.
    
    Args:
        csv_path: Path to CSV file
        output_path: Optional path to save JSON file
    
    Returns:
        Dictionary with categorized products
    """
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Initialize categories
    categorized = {
        'external_facing': [],
        'saas_services': [],
        'security_identity': [],
        'infrastructure_tools': [],
        'monitoring_observability': [],
        'databases': [],
        'container_platform': [],
        'networking_proxy': [],
        'development_tools': [],
        'libraries_frameworks': [],
        'other': []
    }
    
    # Process each row
    for _, row in df.iterrows():
        product_dict = process_row_to_dict(row)
        if product_dict:
            category = categorize_product(row)
            categorized[category].append(product_dict)
    
    # Remove empty categories
    categorized = {k: v for k, v in categorized.items() if v}
    
    # Save to file if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(categorized, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved categorized JSON to: {output_path}")
    
    return categorized

# ==============================================================
# 📊 XLSX to JSON Converter
# ==============================================================

def xlsx_to_categorized_json(xlsx_path: str | Path, output_dir: Optional[str | Path] = None) -> Dict[str, Dict]:
    """
    Convert XLSX with multiple sheets to separate JSON files.
    
    Args:
        xlsx_path: Path to XLSX file
        output_dir: Optional directory to save JSON files
    
    Returns:
        Dictionary with sheet names as keys and categorized data as values
    """
    # Read all sheets
    xlsx_file = pd.ExcelFile(xlsx_path)
    all_sheets = {}
    
    print(f"📊 Processing XLSX file: {xlsx_path}")
    print(f"📄 Found sheets: {xlsx_file.sheet_names}")
    
    for sheet_name in xlsx_file.sheet_names:
        print(f"\n🔄 Processing sheet: {sheet_name}")
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        
        # Initialize categories
        categorized = {
            'external_facing': [],
            'saas_services': [],
            'security_identity': [],
            'infrastructure_tools': [],
            'monitoring_observability': [],
            'databases': [],
            'container_platform': [],
            'networking_proxy': [],
            'development_tools': [],
            'libraries_frameworks': [],
            'other': []
        }
        
        # Process each row
        for _, row in df.iterrows():
            product_dict = process_row_to_dict(row)
            if product_dict:
                category = categorize_product(row)
                categorized[category].append(product_dict)
        
        # Remove empty categories
        categorized = {k: v for k, v in categorized.items() if v}
        all_sheets[sheet_name] = categorized
        
                # Save individual sheet JSON if output directory provided
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            # Fix: Convert sheet_name to string first, then lowercase
            sheet_filename = f"{str(sheet_name).lower().replace(' ', '_')}.json"
            output_path = output_dir / sheet_filename
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(categorized, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {sheet_name} to: {output_path}")
    
    # Save combined JSON
    if output_dir:
        combined_path = Path(output_dir) / "combined_infrastructure.json"
        with open(combined_path, 'w', encoding='utf-8') as f:
            json.dump(all_sheets, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved combined JSON to: {combined_path}")
    
    return all_sheets

# ==============================================================
# 📝 Condensed Text Format
# ==============================================================

def create_condensed_context(categorized_data: Dict[str, List[Dict]], output_path: Optional[str | Path] = None) -> str:
    """
    Create ultra-condensed text format for token efficiency.
    
    Args:
        categorized_data: Categorized product dictionary
        output_path: Optional path to save text file
    
    Returns:
        Condensed text string
    """
    lines = ["# ThreatMark Infrastructure Inventory\n"]
    
    category_titles = {
        'external_facing': '## 🌐 External-Facing Services (HIGH PRIORITY)',
        'saas_services': '## ☁️ SaaS/Cloud Services',
        'security_identity': '## 🔐 Security & Identity Management',
        'infrastructure_tools': '## 🛠️ Infrastructure & Automation Tools',
        'monitoring_observability': '## 📊 Monitoring & Observability',
        'databases': '## 💾 Databases & Data Stores',
        'container_platform': '## 🐳 Container Platform',
        'networking_proxy': '## 🌉 Networking & Load Balancing',
        'development_tools': '## 💻 Development Tools (Workstation)',
        'libraries_frameworks': '## 📚 Libraries & Frameworks',
        'other': '## 🔧 Other Tools'
    }
    
    for category, products in categorized_data.items():
        if not products:
            continue
            
        lines.append(f"\n{category_titles.get(category, f'## {category}')}")
        
        for product in products:
            exposure_note = f", {product['exposure']}" if product['exposure'] else ""
            notes_text = f" — {product['notes']}" if product['notes'] else ""
            lines.append(
                f"- **{product['product']}** ({product['vendor']}): "
                f"{product['purpose']}{exposure_note}{notes_text}"
            )
    
    condensed_text = "\n".join(lines)
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(condensed_text)
        print(f"✅ Saved condensed text to: {output_path}")
    
    return condensed_text

# ==============================================================
# 🔄 Load Infrastructure Context
# ==============================================================

def load_infrastructure_context(format: str = "json") -> Dict | str:
    """
    Load infrastructure context for LLM prompts.
    
    Args:
        format: "json" or "text"
    
    Returns:
        Infrastructure context in requested format
    """
    if format == "json":
        path = get_infrastructure_path("infrastructure_context.json")
        if not path.exists():
            raise FileNotFoundError(
                f"❌ Infrastructure context not found at {path}\n"
                "Run: uv run python scripts/convert_infrastructure.py"
            )
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    elif format == "text":
        path = get_infrastructure_path("infrastructure_condensed.txt")
        if not path.exists():
            raise FileNotFoundError(
                f"❌ Infrastructure context not found at {path}\n"
                "Run: uv run python scripts/convert_infrastructure.py"
            )
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    else:
        raise ValueError(f"Invalid format: {format}. Use 'json' or 'text'")