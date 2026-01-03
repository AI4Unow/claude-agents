#!/usr/bin/env python3
"""
Scaffold a new masterplan from templates.

Usage:
  python scaffold-masterplan.py --id forestry --name "Lâm nghiệp" --decision QD-999 --entity forests --color emerald
"""

import argparse
import os
import re
from pathlib import Path

# Template placeholders
PLACEHOLDERS = {
    'MASTERPLAN_ID': '',           # forestry
    'MASTERPLAN_ID_PASCAL': '',    # Forestry
    'MASTERPLAN_ID_UPPER': '',     # FORESTRY
    'MASTERPLAN_NAME_VI': '',      # Lâm nghiệp
    'DECISION_ID': '',             # QD-999
    'DECISION_NUMBER': '',         # 999
    'PRIMARY_ENTITY': '',          # forests
    'PRIMARY_ENTITY_PASCAL': '',   # Forest
    'PRIMARY_ENTITY_UPPER': '',    # FORESTS
    'ACCENT_COLOR': '',            # emerald
    'ACCENT_HEX': '',              # 10b981
}

ACCENT_COLORS = {
    'emerald': '10b981',
    'amber': 'f59e0b',
    'blue': '3b82f6',
    'rose': 'f43f5e',
    'purple': 'a855f7',
    'cyan': '06b6d4',
    'orange': 'f97316',
}

def to_pascal_case(s: str) -> str:
    """Convert to PascalCase: forestry -> Forestry, power_plants -> PowerPlants"""
    return ''.join(word.capitalize() for word in re.split(r'[_\s-]', s))

def to_upper_case(s: str) -> str:
    """Convert to UPPER_CASE: forestry -> FORESTRY"""
    return s.upper().replace('-', '_')

def replace_placeholders(content: str, values: dict) -> str:
    """Replace all {{PLACEHOLDER}} in content with values."""
    for key, value in values.items():
        content = content.replace('{{' + key + '}}', value)
    return content

def scaffold_file(template_path: Path, output_path: Path, values: dict):
    """Read template, replace placeholders, write to output."""
    content = template_path.read_text()
    content = replace_placeholders(content, values)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    print(f"  ✓ {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Scaffold a new masterplan')
    parser.add_argument('--id', required=True, help='Masterplan ID (e.g., forestry)')
    parser.add_argument('--name', required=True, help='Vietnamese name (e.g., Lâm nghiệp)')
    parser.add_argument('--decision', required=True, help='Decision ID (e.g., QD-999)')
    parser.add_argument('--entity', required=True, help='Primary entity (e.g., forests)')
    parser.add_argument('--color', default='emerald', help='Accent color (emerald, amber, blue, etc.)')
    parser.add_argument('--project-root', default='.', help='Project root directory')

    args = parser.parse_args()

    # Extract decision number
    decision_number = re.search(r'\d+', args.decision)
    if not decision_number:
        print(f"Error: Could not extract number from decision ID: {args.decision}")
        return
    decision_number = decision_number.group()

    # Build placeholder values
    values = {
        'MASTERPLAN_ID': args.id,
        'MASTERPLAN_ID_PASCAL': to_pascal_case(args.id),
        'MASTERPLAN_ID_UPPER': to_upper_case(args.id),
        'MASTERPLAN_NAME_VI': args.name,
        'DECISION_ID': args.decision,
        'DECISION_NUMBER': decision_number,
        'PRIMARY_ENTITY': args.entity,
        'PRIMARY_ENTITY_PASCAL': to_pascal_case(args.entity.rstrip('s')),  # forests -> Forest
        'PRIMARY_ENTITY_UPPER': to_upper_case(args.entity),
        'ACCENT_COLOR': args.color,
        'ACCENT_HEX': ACCENT_COLORS.get(args.color, '10b981'),
    }

    print(f"\nScaffolding masterplan: {args.id}")
    print(f"  Name: {args.name}")
    print(f"  Decision: {args.decision}")
    print(f"  Entity: {args.entity}")
    print(f"  Color: {args.color}")
    print()

    # Get paths
    script_dir = Path(__file__).parent
    templates_dir = script_dir.parent / 'references' / 'templates'
    project_root = Path(args.project_root)

    # Template -> Output mapping
    files = [
        ('types.template.ts', f'src/types/{args.id}.ts'),
        ('firebase-queries.template.ts', f'src/lib/firebase/{args.id}.ts'),
        ('ai-tools.template.ts', f'src/lib/ai/{args.id}-tools.ts'),
        ('map-page.template.tsx', f'src/app/{args.id}/page.tsx'),
        ('overview-page.template.tsx', f'src/app/{args.id}/overview/page.tsx'),
        ('stats-overlay.template.tsx', f'src/components/{args.id}/{args.id}-stats-overlay.tsx'),
        ('stats-cards.template.tsx', f'src/components/{args.id}/{args.id}-stats-cards.tsx'),
        ('filter-panel.template.tsx', f'src/components/{args.id}/{args.id}-filter-panel.tsx'),
        ('popup.template.tsx', f'src/components/{args.id}/{args.id}-popup.tsx'),
    ]

    print("Generating files:")
    for template_name, output_rel in files:
        template_path = templates_dir / template_name
        output_path = project_root / output_rel

        if template_path.exists():
            scaffold_file(template_path, output_path, values)
        else:
            print(f"  ⚠ Template not found: {template_name}")

    print()
    print("Next steps:")
    print(f"  1. Add collection constants to src/lib/firebase/constants.ts")
    print(f"  2. Add config to src/lib/masterplan/registry.ts")
    print(f"  3. Add tools to src/lib/ai/toolset-registry.ts")
    print(f"  4. Customize generated files for domain-specific logic")
    print(f"  5. Run: npm run dev")
    print(f"  6. Test: http://localhost:3000/{args.id}")

if __name__ == '__main__':
    main()
