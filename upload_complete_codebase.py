#!/usr/bin/env python3
"""
Complete Codebase Upload Script for HTML Reference File
Uploads all app.py code in 500-line chunks to the HTML file
"""

import os
from pathlib import Path

def upload_complete_codebase():
    """Upload all remaining chunks of app.py to HTML file"""
    
    # File paths
    base_dir = Path(__file__).parent
    app_py_path = base_dir / "app.py"
    html_path = base_dir / "app_py_complete_reference.html"
    
    print(f"📂 Reading app.py from: {app_py_path}")
    print(f"📝 Updating HTML file: {html_path}")
    
    # Read the complete app.py file
    with open(app_py_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    total_lines = len(lines)
    chunk_size = 500
    total_chunks = (total_lines + chunk_size - 1) // chunk_size  # Ceiling division
    
    print(f"📊 Total lines: {total_lines}")
    print(f"📊 Chunk size: {chunk_size} lines")
    print(f"📊 Total chunks needed: {total_chunks}")
    
    # Read current HTML content
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Find the insertion point (after chunk 1)
    insertion_marker = '        </div>\n\n        <div class="info-box">'
    
    if insertion_marker not in html_content:
        print("❌ Could not find insertion marker in HTML file")
        return False
    
    # Split HTML content
    before_marker = html_content.split(insertion_marker)[0]
    after_marker = insertion_marker + html_content.split(insertion_marker)[1]
    
    # Generate all chunks (starting from chunk 2, since chunk 1 is already uploaded)
    chunks_html = ""
    
    for chunk_num in range(2, total_chunks + 1):
        start_line = (chunk_num - 1) * chunk_size
        end_line = min(chunk_num * chunk_size, total_lines)
        
        chunk_lines = lines[start_line:end_line]
        chunk_content = ''.join(chunk_lines)
        
        # Generate line numbers
        line_numbers = '\n'.join(str(i + start_line + 1) for i in range(len(chunk_lines)))
        
        # Escape HTML characters in code
        chunk_content_escaped = (chunk_content
                                .replace('&', '&amp;')
                                .replace('<', '&lt;')
                                .replace('>', '&gt;')
                                .replace('"', '&quot;')
                                .replace("'", '&#x27;'))
        
        # Determine chunk description
        if chunk_num == 2:
            description = "Routes & API Endpoints"
        elif chunk_num <= 5:
            description = "Main Routes & Business Logic"
        elif chunk_num <= 10:
            description = "API Endpoints & Data Processing"
        elif chunk_num <= 15:
            description = "Advanced Features & Analytics"
        else:
            description = "Additional Features & Utilities"
        
        chunk_html = f"""
        <!-- COMPLETE APP.PY CODE - CHUNK {chunk_num}: Lines {start_line + 1}-{end_line} -->
        <div class="section" id="app-py-{start_line + 1}-{end_line}">
            <div class="section-header">
                <span class="section-icon">🐍</span>
                Complete app.py - Chunk {chunk_num}: Lines {start_line + 1}-{end_line} ({description})
            </div>
            <div class="code-container">
                <button class="copy-btn" onclick="copyCode(this)">📋 Copy</button>
                <div class="line-numbers">{line_numbers}</div>
                <pre class="code-block"><code class="language-python">{chunk_content_escaped}</code></pre>
            </div>
        </div>
"""
        chunks_html += chunk_html
        print(f"✅ Generated chunk {chunk_num}: Lines {start_line + 1}-{end_line}")
    
    # Combine all content
    new_html_content = before_marker + chunks_html + "\n" + after_marker
    
    # Write updated HTML file
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_html_content)
    
    print(f"🎉 Successfully uploaded complete codebase!")
    print(f"📊 Total chunks uploaded: {total_chunks}")
    print(f"📊 Total lines uploaded: {total_lines}")
    print(f"📝 Updated file: {html_path}")
    
    return True

def update_navigation():
    """Update the quick navigation to include all chunks"""
    html_path = Path(__file__).parent / "app_py_complete_reference.html"
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add navigation links for all chunks
    nav_links = []
    for chunk_num in range(1, 18):  # 17 total chunks
        start_line = (chunk_num - 1) * 500 + 1
        end_line = min(chunk_num * 500, 8213)
        nav_links.append(f'                <a href="#app-py-{start_line}-{end_line}" class="nav-link">🐍 Chunk {chunk_num}: Lines {start_line}-{end_line}</a>')
    
    # Find and replace the navigation section
    nav_start = '<div class="quick-nav">'
    nav_end = '</div>'
    
    if nav_start in content:
        before_nav = content.split(nav_start)[0]
        after_nav_parts = content.split(nav_start)[1].split(nav_end, 1)
        after_nav = nav_end + after_nav_parts[1] if len(after_nav_parts) > 1 else nav_end
        
        new_nav = nav_start + '\n' + '\n'.join(nav_links) + '\n            ' + nav_end
        new_content = before_nav + new_nav + after_nav
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Updated navigation links")

if __name__ == "__main__":
    print("🚀 Starting complete codebase upload...")
    
    if upload_complete_codebase():
        update_navigation()
        print("\n🎉 COMPLETE! Your HTML file now contains the entire app.py codebase!")
        print("📱 Open app_py_complete_reference.html in your browser to use the AI chat assistant!")
    else:
        print("❌ Upload failed. Please check the error messages above.")