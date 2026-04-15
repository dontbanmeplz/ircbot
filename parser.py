"""
Parser for SearchBot results
Extracts and structures search results from IRC SearchBot zip files
"""

import os
import re
import zipfile
from typing import Dict, List, Optional
import config


def parse_search_results(zip_filepath: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Extract and parse search results from SearchBot zip file
    
    Args:
        zip_filepath: Path to the downloaded SearchBot .zip file
        
    Returns:
        dict: Grouped results by bot name
        {
            "Bsk": [
                {
                    "command": "!Bsk EG 01 - Enders Game...",
                    "title": "Enders Game - Card Orson Scott",
                    "size": "381.6KB",
                    "format": "epub",
                    "full_line": "original line from file"
                },
                ...
            ],
            "Dumbledore": [...],
            ...
        }
    """
    results = {}
    
    try:
        # Extract zip file
        txt_content = extract_zip(zip_filepath)
        if not txt_content:
            return results
        
        # Parse each line
        lines = txt_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line starts with ! (IRC command)
            if not line.startswith('!'):
                continue
            
            # Check if line contains any allowed formats
            if not any(fmt in line.lower() for fmt in config.ALLOWED_FORMATS):
                continue
            
            # Parse the line
            parsed = parse_line(line)
            if parsed:
                bot_name = parsed['bot_name']
                if bot_name not in results:
                    results[bot_name] = []
                results[bot_name].append(parsed)
        
        # Limit results per bot
        for bot_name in results:
            if len(results[bot_name]) > config.MAX_RESULTS_PER_BOT:
                results[bot_name] = results[bot_name][:config.MAX_RESULTS_PER_BOT]
        
        return results
        
    except Exception as e:
        print(f"Error parsing search results: {e}")
        import traceback
        traceback.print_exc()
        return results


def extract_zip(zip_filepath: str) -> Optional[str]:
    """
    Extract zip file and return contents of .txt file
    
    Args:
        zip_filepath: Path to zip file
        
    Returns:
        str: Contents of text file, or None if error
    """
    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            # Find .txt file in zip
            txt_files = [f for f in zip_ref.namelist() if f.endswith('.txt')]
            if not txt_files:
                print(f"No .txt file found in {zip_filepath}")
                return None
            
            # Read first .txt file
            txt_filename = txt_files[0]
            with zip_ref.open(txt_filename) as txt_file:
                # Try different encodings
                try:
                    content = txt_file.read().decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        content = txt_file.read().decode('latin-1')
                    except:
                        content = txt_file.read().decode('utf-8', errors='replace')
                
                return content
                
    except Exception as e:
        print(f"Error extracting zip {zip_filepath}: {e}")
        return None


def parse_line(line: str) -> Optional[Dict[str, str]]:
    """
    Parse a single line from search results
    
    Args:
        line: Line from search results file
        
    Returns:
        dict: Parsed data or None if line doesn't match pattern
    """
    try:
        # Extract bot name (first word after !)
        # Pattern: !BotName <rest>
        bot_match = re.match(r'^!(\S+)\s+(.+)$', line)
        if not bot_match:
            return None
        
        bot_name = bot_match.group(1)
        rest = bot_match.group(2)
        
        # Extract file format
        format_match = re.search(r'\.(epub|mobi|pdf)', line, re.IGNORECASE)
        file_format = format_match.group(1).lower() if format_match else "unknown"
        
        # Extract file size if present
        # Patterns: ::INFO:: 381.6KB or just 381.6KB
        size_match = re.search(r'([\d.]+\s*[KMG]B)', line, re.IGNORECASE)
        file_size = size_match.group(1) if size_match else "Unknown"
        
        # Extract title (everything between bot name and ::INFO:: or size)
        title = rest
        
        # Remove ::INFO:: section
        if '::INFO::' in title:
            title = title.split('::INFO::')[0].strip()
        
        # Remove hash section if present
        if '::HASH::' in title:
            title = title.split('::HASH::')[0].strip()
        
        # Remove file extension from title display
        for fmt in ['.epub', '.mobi', '.pdf', '.rar']:
            if title.lower().endswith(fmt):
                title = title[:-len(fmt)]
                break
        
        # Clean up title
        title = title.strip()
        
        # Build command (everything up to ::INFO:: or ::HASH::)
        command = line
        if '::INFO::' in command:
            command = command.split('::INFO::')[0].strip()
        if '::HASH::' in command:
            command = command.split('::HASH::')[0].strip()
        
        return {
            'bot_name': bot_name,
            'command': command,
            'title': title,
            'size': file_size,
            'format': file_format,
            'full_line': line
        }
        
    except Exception as e:
        print(f"Error parsing line '{line}': {e}")
        return None


def extract_metadata_from_filename(filename: str) -> Dict[str, str]:
    """
    Extract title and author from filename
    
    Common patterns:
    - "Author Name - Book Title.epub"
    - "Book Title - Author Name.epub"
    - "[Series 01] - Book Title - Author Name.epub"
    
    Args:
        filename: Book filename
        
    Returns:
        dict: {'title': '...', 'author': '...'}
    """
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # Try to extract author and title
    author = None
    title = name
    
    # Pattern: "Author - Title" or "Title - Author"
    if ' - ' in name:
        parts = name.split(' - ')
        if len(parts) >= 2:
            # Common pattern: last part before extension is author
            # But could also be: Author - Title
            # Let's use a simple heuristic: if first part has comma, it's likely author
            if ',' in parts[0] or len(parts[0].split()) <= 3:
                author = parts[0].strip()
                title = ' - '.join(parts[1:]).strip()
            else:
                title = parts[0].strip()
                if len(parts) > 1:
                    author = parts[-1].strip()
    
    # Clean up series numbers, file numbers, etc.
    # Remove patterns like "[Series 01]", "(v5.0)", "(retail)", etc.
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'v\d+\.\d+', '', title)
    title = title.strip()
    
    if author:
        author = re.sub(r'\[.*?\]', '', author)
        author = re.sub(r'\(.*?\)', '', author)
        author = author.strip()
    
    return {
        'title': title if title else filename,
        'author': author
    }
