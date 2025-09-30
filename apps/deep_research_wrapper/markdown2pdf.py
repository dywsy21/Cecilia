import asyncio
import aiofiles
import aiohttp
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from apps.llm_handler.llm_handler import LLMHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def convert_markdown_to_pdf(input_file_path: str, topic: str, pdfpath: str) -> str:
    """
    Convert markdown content to PDF using a 4-step process:
    1. Clean input file and create valid markdown
    2. Generate cleaner topic using AI
    3. Download all images to /tmp
    4. Use pandoc to convert to PDF
    """
    try:
        # Step 1: Clean the input file and create valid markdown
        clean_md_path = await _clean_input_file(input_file_path)
        logger.info(f"Step 1 complete: Cleaned markdown created at {clean_md_path}")
        
        # Step 2: Use LLM to generate a cleaner topic
        llm_handler = LLMHandler()
        cleaner_topic = await _generate_cleaner_topic(llm_handler, topic, clean_md_path)
        logger.info(f"Step 2 complete: Generated cleaner topic: {cleaner_topic}")
        
        # Step 3: Download all images and update markdown
        final_md_path = await _download_images_and_update_markdown(clean_md_path, cleaner_topic)
        logger.info(f"Step 3 complete: Images downloaded and markdown updated at {final_md_path}")
        
        # Step 4: Use pandoc to convert to PDF
        await _convert_with_pandoc(final_md_path, pdfpath)
        logger.info(f"Step 4 complete: PDF created at {pdfpath}")
        
        return pdfpath
        
    except Exception as e:
        logger.error(f"Error in markdown to PDF conversion: {e}")
        raise

async def _clean_input_file(input_file_path: str) -> str:
    """Step 1: Clean the input file and create a valid markdown file"""
    try:
        # Read the input file
        content = ''
        async with aiofiles.open(input_file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        assert content, 'why the fuck is the input file empty?'
        
        # Parse server-sent events format
        lines = content.split('\n')
        markdown_content = ''
        
        for line in lines:
            # Skip event lines
            if line.startswith('event:'):
                continue
            # Process data lines
            if line.startswith('data:'):
                # Extract JSON from data line
                json_str = line[5:].strip()  # Remove 'data:' prefix
                try:
                    import json
                    data = json.loads(json_str)
                    
                    # Navigate through the nested structure to find the markdown content
                    if 'result' in data and 'content' in data['result']:
                        for content_item in data['result']['content']:
                            if content_item.get('type') == 'text':
                                text_data = content_item.get('text', '')
                                # Parse the inner JSON string
                                inner_data = json.loads(text_data)
                                if 'finalReport' in inner_data:
                                    # Decode escaped characters
                                    markdown_content = inner_data['finalReport']
                                    markdown_content = markdown_content.replace('\\n', '\n')
                                    markdown_content = markdown_content.replace('\\t', '\t')
                                    markdown_content = markdown_content.replace('\\"', '"')
                                    break
                        if markdown_content:
                            break
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Could not parse JSON from line: {line[:100]}... Error: {e}")
                    continue
        
        # If no markdown content found in structured format, try fallback parsing
        if not markdown_content:
            logger.warning("Could not find structured markdown content, trying fallback parsing")
            cleaned_lines = []
            for line in lines:
                # Skip server-sent event headers
                if line.startswith('event:') or line.startswith('data:') or line.startswith('id:'):
                    continue
                # Skip empty lines at the beginning
                if not cleaned_lines and not line.strip():
                    continue
                cleaned_lines.append(line)
            markdown_content = '\n'.join(cleaned_lines)
        
        # Basic markdown cleanup
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)  # Remove excessive newlines
        
        # Ensure headers have blank lines after them
        markdown_content = _fix_header_spacing(markdown_content)
        
        markdown_content = markdown_content.strip()
        
        if not markdown_content:
            raise ValueError("No valid markdown content found in input file")
        
        # Create temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_md_path = f"/tmp/cleaned_markdown_{timestamp}.md"
        
        async with aiofiles.open(clean_md_path, 'w', encoding='utf-8') as f:
            await f.write(markdown_content)
        
        return clean_md_path
        
    except Exception as e:
        logger.error(f"Error cleaning input file: {e}")
        raise

def _fix_header_spacing(content: str) -> str:
    """Ensure all headers have proper blank lines after them"""
    lines = content.split('\n')
    result_lines = []
    
    for i, line in enumerate(lines):
        result_lines.append(line)
        
        # Check if current line is a header
        if line.strip().startswith('#'):
            # Check if next line exists and is not empty
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line:
                    # Add blank line after header if next line is not empty and not another header
                    result_lines.append('')
    
    return '\n'.join(result_lines)

async def _generate_cleaner_topic(llm_handler: LLMHandler, original_topic: str, md_file_path: str) -> str:
    """Step 2: Use LLM to generate a cleaner, more readable topic"""
    try:
        # Read some content from the markdown file for context
        async with aiofiles.open(md_file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        # Get first 2000 characters for context
        content_preview = content[:2000] if len(content) > 2000 else content
        
        prompt = f"""
Based on the original topic and the content preview below, generate a clean, professional, and concise title for this research document. 
The title should be:
- Clear and descriptive
- Professional and academic in tone
- Between 5-10 words, make sure to be <= 10 words!
- Without special characters or timestamps
- In English

Original topic: {original_topic}

Content preview:
{content_preview}

Please respond with ONLY the clean title, nothing else.
"""
        
        logger.info("Calling LLM to generate cleaner topic...")
        clean_topic = await llm_handler.ask_ai(prompt)
        logger.info(f"LLM responded with: {clean_topic}")
        
        # Fallback to cleaned version of original topic if AI fails
        if not clean_topic or len(clean_topic.strip()) == 0:
            logger.warning("LLM returned empty response, using fallback")
            clean_topic = re.sub(r'[^\w\s-]', '', original_topic)
            clean_topic = re.sub(r'_+', ' ', clean_topic)
            clean_topic = ' '.join(clean_topic.split())
        
        return clean_topic.strip()
        
    except Exception as e:
        logger.error(f"Error generating cleaner topic: {e}")
        # Fallback to cleaned original topic
        clean_topic = re.sub(r'[^\w\s-]', '', original_topic)
        clean_topic = re.sub(r'_+', ' ', clean_topic)
        return ' '.join(clean_topic.split())

async def _download_images_and_update_markdown(md_path: str, title: str) -> str:
    """Step 3: Download all images in the markdown file and update references"""
    try:
        async with aiofiles.open(md_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        # Handle References section - split content at "---" if present
        main_content = content
        references_content = ""
        
        if '---' in content:
            parts = content.split('---', 1)
            main_content = parts[0].strip()
            if len(parts) > 1:
                references_content = "\n\n".join(parts[1].strip().replace(":", "").splitlines())
        
        # Find all image URLs in markdown - check both ![]() and []() patterns
        # Pattern 1: Standard markdown images ![]()
        image_pattern1 = r'!\[([^\]]*)\]\(([^)]+)\)'
        # Pattern 2: Reference-style links that might be images []()
        image_pattern2 = r'(?<!\!)\[([^\]]*)\]\(([^)]+\.(jpg|jpeg|png|gif|bmp|svg|webp))\)'
        
        images1 = re.findall(image_pattern1, main_content)
        images2 = re.findall(image_pattern2, main_content, re.IGNORECASE)
        
        # Combine both patterns - convert pattern2 results to same format as pattern1
        images = [(alt, url) for alt, url in images1]
        images.extend([(alt, url) for alt, url, ext in images2])
        
        updated_content = main_content
        
        # Download each image from main content
        if images:
            logger.info(f"Found {len(images)} images to download")
            
            async with aiohttp.ClientSession() as session:
                for alt_text, image_url in images:
                    if image_url.startswith(('http://', 'https://')):
                        try:
                            # Generate local filename
                            parsed_url = urlparse(image_url)
                            extension = os.path.splitext(parsed_url.path)[1]
                            if not extension:
                                # Try to detect extension from URL or default to .png
                                if any(ext in image_url.lower() for ext in ['.jpg', '.jpeg']):
                                    extension = '.jpg'
                                elif '.gif' in image_url.lower():
                                    extension = '.gif'
                                elif '.svg' in image_url.lower():
                                    extension = '.svg'
                                elif '.webp' in image_url.lower():
                                    extension = '.webp'
                                else:
                                    extension = '.png'
                            
                            local_filename = f"image_{abs(hash(image_url)) % 10000}{extension}"
                            local_path = f"/tmp/{local_filename}"
                            
                            # Download image
                            async with session.get(image_url, timeout=30) as response:
                                if response.status == 200:
                                    async with aiofiles.open(local_path, 'wb') as f:
                                        async for chunk in response.content.iter_chunked(8192):
                                            await f.write(chunk)
                                    
                                    # Update markdown content with local path - handle both patterns
                                    updated_content = updated_content.replace(
                                        f'![{alt_text}]({image_url})',
                                        f'![{alt_text}]({local_path})'
                                    )
                                    updated_content = updated_content.replace(
                                        f'[{alt_text}]({image_url})',
                                        f'![{alt_text}]({local_path})'  # Convert []() to ![]() for images
                                    )
                                    logger.info(f"Downloaded image: {image_url} -> {local_path}")
                                else:
                                    logger.warning(f"Failed to download image: {image_url} (status: {response.status})")
                                    
                        except Exception as e:
                            logger.warning(f"Error downloading image {image_url}: {e}")
                            continue
        else:
            logger.info("No images found in markdown content")
        
        # Generate YAML header
        current_date = datetime.now().strftime("%y.%m.%d")
        yaml_header = f"""---
title: {title.replace(':', "——")}
abstract:
author: Cecilia
acknowledgements:
declaration:
text1: Cecilia - Deep Research
text2: {current_date}
text3: 
text4: 
titlepage-logo: /home/ubuntu/Cecilia/pics/avatar.png
link-citations: true
reference-section-title: References
---

"""
        
        # Add YAML header and title to the beginning of the document
        updated_content = yaml_header + updated_content
        
        # Remove any existing H1 title at the start since we have it in YAML
        # Look for the first H1 and remove it if it matches our title
        lines = updated_content.split('\n')
        yaml_end_count = 0
        content_start_idx = 0
        
        for i, line in enumerate(lines):
            if line.strip() == '---':
                yaml_end_count += 1
                if yaml_end_count == 2:  # Found the end of YAML frontmatter
                    content_start_idx = i + 1
                    break
        
        # Check if the first content line after YAML is our title
        if content_start_idx < len(lines):
            first_content_line = lines[content_start_idx].strip()
            if first_content_line.startswith('# ') and title.lower() in first_content_line.lower():
                # Remove the duplicate title line
                lines.pop(content_start_idx)
                # Also remove the next line if it's empty
                if content_start_idx < len(lines) and not lines[content_start_idx].strip():
                    lines.pop(content_start_idx)
        
        updated_content = '\n'.join(lines)
        
        # Add References section with proper LaTeX formatting if it exists
        if references_content:
            # Add page break and centered References title
            updated_content += '\n\n\\newpage\n\n'
            updated_content += '\\begin{center}\n'
            updated_content += '\\textbf{\\Large References}\n'
            updated_content += '\\end{center}\n\n'
            updated_content += references_content
        
        # Create final markdown file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_md_path = f"/tmp/final_markdown_{timestamp}.md"
        
        async with aiofiles.open(final_md_path, 'w', encoding='utf-8') as f:
            await f.write(updated_content)
        
        return final_md_path
        
    except Exception as e:
        logger.error(f"Error downloading images: {e}")
        raise

async def _convert_with_pandoc(md_path: str, output_pdf_path: str) -> None:
    """Step 4: Use pandoc to convert markdown to PDF"""
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_pdf_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Check for pandoc and xelatex executables
        pandoc_paths = [
            "/usr/bin/pandoc",
            "/usr/local/bin/pandoc",
            "pandoc"
        ]
        
        xelatex_paths = [
            "/usr/local/texlive/2025/bin/x86_64-linux/xelatex",
            "/usr/local/texlive/2024/bin/x86_64-linux/xelatex", 
            "/usr/bin/xelatex",
            "/usr/local/bin/xelatex",
            "xelatex"
        ]
        
        # Find working pandoc
        pandoc_cmd = None
        for path in pandoc_paths:
            try:
                process = await asyncio.create_subprocess_exec(
                    path, "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                if process.returncode == 0:
                    pandoc_cmd = path
                    logger.info(f"Found pandoc at: {pandoc_cmd}")
                    break
            except FileNotFoundError:
                continue
        
        if not pandoc_cmd:
            raise RuntimeError("Pandoc not found in any of the expected locations")
        
        # Find working xelatex
        xelatex_cmd = None
        for path in xelatex_paths:
            try:
                process = await asyncio.create_subprocess_exec(
                    path, "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                if process.returncode == 0:
                    xelatex_cmd = path
                    logger.info(f"Found xelatex at: {xelatex_cmd}")
                    break
            except FileNotFoundError:
                continue
        
        if not xelatex_cmd:
            raise RuntimeError("XeLaTeX not found in any of the expected locations")
        
        # Check if dissertation template exists
        template_path = "./dissertation/dissertation.tex"
        
        if os.path.exists(template_path):
            # Use custom template if available
            cmd = [
                pandoc_cmd, md_path,
                "--template", template_path,
                "-o", output_pdf_path,
                "--pdf-engine", xelatex_cmd
            ]
        else:
            # Fallback to default pandoc conversion
            logger.warning(f"Dissertation template not found at {template_path}, using default")
            cmd = [
                pandoc_cmd, md_path,
                "-o", output_pdf_path,
                "--pdf-engine", xelatex_cmd,
                "-V", "geometry:margin=2cm"
            ]
        
        logger.info(f"Running pandoc command: {' '.join(cmd)}")
        
        # Run pandoc
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Pandoc conversion successful: {output_pdf_path}")
        else:
            error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
            logger.error(f"Pandoc conversion failed: {error_msg}")
            if stdout:
                logger.info(f"Pandoc stdout: {stdout.decode('utf-8')}")
            raise RuntimeError(f"Pandoc conversion failed: {error_msg}")
            
    except Exception as e:
        logger.error(f"Error in pandoc conversion: {e}")
        raise


if __name__ == '__main__':
    import asyncio
    async def main():
        topic = 'Recent AI Advancements (2023–2024): Transformative Progress in Large Language Models, Computer Vision, and Reinforcement Learning'
        input_file_path = '/home/ubuntu/Cecilia/data/deep_research/deep_research_response_Recent_advancements_in_AI_technology_20232024_with_20250929_201858.txt'
        pdf_path = 'out.pdf'
        await convert_markdown_to_pdf(input_file_path, topic, pdf_path)
    asyncio.run(main())
