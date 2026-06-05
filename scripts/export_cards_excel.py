import sqlite3
import pandas as pd
import json
import argparse
import os
from datetime import datetime

def export_cards(db_path, output_path, version_label=None, safety_types=None, all_active=False):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    
    # Query to get the latest released version of each card
    query = """
    SELECT 
        cr.card_id,
        cr.key,
        cr.safety_type,
        cr.event,
        cr.phase,
        cr.options_json,
        cr.audio_url,
        cr.version_label,
        cr.released_by,
        datetime(cr.released_at / 1000, 'unixepoch') as released_at_formatted
    FROM cards_released cr
    INNER JOIN (
        SELECT key, MAX(released_at) as max_t 
        FROM cards_released 
        GROUP BY key
    ) latest ON cr.key = latest.key AND cr.released_at = latest.max_t
    WHERE 1=1
    """
    
    params = []
    
    if not all_active:
        if version_label:
            query += " AND cr.version_label = ?"
            params.append(version_label)
        
        if safety_types:
            placeholders = ','.join(['?'] * len(safety_types))
            query += f" AND cr.safety_type IN ({placeholders})"
            params.extend(safety_types)
            
    query += " ORDER BY cr.key ASC"

    try:
        df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            print("No cards found matching the specified criteria.")
            conn.close()
            return False

        # Parse options JSON and flatten to columns
        def parse_options(row):
            try:
                options = json.loads(row['options_json'])
                parsed = {}
                for i, opt in enumerate(options):
                    idx = chr(ord('A') + i) # A, B, C...
                    parsed[f'Option {idx} Text'] = opt.get('text', '')
                    parsed[f'Option {idx} Quality'] = opt.get('quality', '')
                    parsed[f'Option {idx} Score'] = opt.get('score', '')
                return pd.Series(parsed)
            except Exception as e:
                return pd.Series()

        # Apply parsing
        options_df = df.apply(parse_options, axis=1)
        
        # Merge back to original dataframe and drop the raw JSON column
        result_df = pd.concat([df, options_df], axis=1)
        result_df.drop('options_json', axis=1, inplace=True)
        
        # Rename columns for better readability (Chinese headers as requested mostly in Excel)
        rename_map = {
            'card_id': '卡牌 ID (card_id)',
            'key': '唯一键 (key)',
            'safety_type': '安全类型 (safety_type)',
            'event': '事件内容 (event)',
            'phase': '阶段 (phase)',
            'audio_url': '音频链接 (audio_url)',
            'version_label': '版本标签 (version_label)',
            'released_by': '发布人 ID (released_by)',
            'released_at_formatted': '发布时间 (released_at)'
        }
        result_df.rename(columns=rename_map, inplace=True)

        # Write to Excel
        result_df.to_excel(output_path, index=False, engine='openpyxl')
        print(f"Successfully exported {len(result_df)} cards to {output_path}")
        conn.close()
        return True

    except Exception as e:
        print(f"Error during export: {e}")
        conn.close()
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导出 wqt-auth-backend 的激活卡牌数据到 Excel")
    parser.add_argument("--db-path", type=str, default="data/cards.db", help="cards.db 文件的相对或绝对路径")
    parser.add_argument("--output", type=str, default="cards_export.xlsx", help="输出的 Excel 文件路径")
    parser.add_argument("--version-label", type=str, help="指定要导出的版本标签，例如 '沙盒'")
    parser.add_argument("--safety-type", type=str, help="指定要导出的安全类型（逗号分隔），例如 '心理安全,社交安全'")
    parser.add_argument("--all", action="store_true", help="忽略其他过滤条件，导出所有当前激活的卡牌")

    args = parser.parse_args()
    
    # Process safety_types list
    safety_types_list = [s.strip() for s in args.safety_type.split(',')] if args.safety_type else None
    
    export_cards(args.db_path, args.output, args.version_label, safety_types_list, args.all)
