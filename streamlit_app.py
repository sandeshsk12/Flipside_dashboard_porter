import os
import subprocess
import sys
import streamlit as st
import asyncio
import json
import re
import shutil
import builtins
from pathlib import Path
from urllib.parse import urljoin

import nest_asyncio
nest_asyncio.apply()

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


@st.cache_resource
def install_playwright_deps():
    """
    Installs the chromium browser for Playwright and system dependencies.
    The @st.cache_resource decorator ensures this runs only once.
    """
    try:
        # Show installation status
        status = st.status("Installing Playwright dependencies...")
        
        with status:
            st.write("Installing Playwright browser...")
            # Install Chromium browser
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                st.error(f"Failed to install Playwright browser: {result.stderr}")
                
            st.write("Installing system dependencies...")
            
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install-deps"],
                    capture_output=True,
                    text=True
                )
            except Exception as e:
                st.warning(f"Note: Some system dependencies might be missing: {e}")
                st.warning("The app might not work correctly in this environment.")
                
            st.success("Playwright setup completed!")
    except Exception as e:
        st.error(f"Failed to set up Playwright: {str(e)}")
        st.warning("The app might not work correctly. Some features may be limited.")
        st.stop()

# Run the installer at the start of the script
install_playwright_deps()
# ——————————————————————————————————————————————————————

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.strip().lower()).strip('-') or 'untitled'

async def download_resource(session, url, output_path):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.read()
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(content)
                return True
    except Exception:
        pass
    return False

def rewrite_links(soup, current_html_path, site_map, base_output_dir):
    nav_elements = soup.select('a, button, [role="button"]')
    current_dir = Path(current_html_path).parent

    for el in nav_elements:
        text = el.get_text(strip=True)
        if not text:
            continue
        
        slug = slugify(text)
        if slug in site_map:
            target_path = Path(base_output_dir) / site_map[slug]
            relative_path = os.path.relpath(target_path.resolve(), current_dir.resolve())

            if el.name == 'a':
                el['href'] = relative_path
            else:
                anchor = soup.new_tag('a', href=relative_path)
                if el.get('class'):
                    anchor['class'] = el.get('class')
                anchor['style'] = el.get('style', '') + ' text-decoration: none; color: inherit; cursor: pointer;'
                anchor.string = el.get_text()
                el.replace_with(anchor)
    return soup

async def save_page_with_assets(page, session, output_dir, file_slug, site_map, base_output_dir):
    print(f"    -> Processing page: {Path(output_dir).relative_to(base_output_dir)}/{file_slug}")
    print("      Waiting 5 seconds for page to load...")
    await page.wait_for_timeout(5000)
    html = await page.content()
    base_url = page.url
    soup = BeautifulSoup(html, 'html.parser')

    assets_dir_name = f"{file_slug}_files"
    assets_out_dir = Path(output_dir) / assets_dir_name
    assets_out_dir.mkdir(parents=True, exist_ok=True)

    for link_tag in soup.find_all('link', rel='stylesheet'):
        css_url = link_tag.get('href')
        if not css_url:
            continue
        abs_css_url = urljoin(base_url, css_url)
        css_filename = os.path.basename(abs_css_url.split('?')[0]) or "style.css"
        local_css_path = assets_out_dir / css_filename
        if await download_resource(session, abs_css_url, str(local_css_path)):
            link_tag['href'] = f"{assets_dir_name}/{css_filename}"

    target_div = soup.select_one('body > div > div:nth-of-type(3) > main > div > div > div:nth-of-type(1) > div:nth-of-type(2)')

    if target_div:
        new_soup = BeautifulSoup('<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body></body></html>', 'html.parser')
        for link_tag in soup.find_all('link', rel='stylesheet'):
            new_soup.head.append(link_tag)
        
        style_tag = new_soup.new_tag('style')
        style_tag.string = """
            body, html { margin: 0; padding: 0; width: 100%; height: 100%; overflow: auto; }
            body > div { width: 100% !important; max-width: 100% !important; }
        """
        new_soup.head.append(style_tag)
        new_soup.body.append(target_div)
        final_soup = new_soup
    else:
        print(f"      Warning: Target element not found in {file_slug}. Saving an empty page.")
        final_soup = BeautifulSoup('<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Element not found</title></head><body><h1>Content not found</h1><p>The requested element could not be found on the page.</p></body></html>', 'html.parser')

    fpath = Path(output_dir) / f"{file_slug}.html"
    final_soup = rewrite_links(final_soup, str(fpath), site_map, base_output_dir)

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(str(final_soup))
    print(f"      Saved and linked HTML to {fpath}")

async def discover_site_structure(page):
    print("--- Starting Site Discovery Phase ---")
    site_map = {}
    main_tabs_handles = await page.query_selector_all('div[role="tablist"]:first-of-type >> [role="tab"]')

    for i in range(len(main_tabs_handles)):
        main_tabs = await page.query_selector_all('div[role="tablist"]:first-of-type >> [role="tab"]')
        main_tab_element = main_tabs[i]
        main_name = await main_tab_element.inner_text()
        main_slug = slugify(main_name)
        
        await main_tab_element.click()
        await page.wait_for_timeout(2000)

        all_tablists = await page.query_selector_all('[role="tablist"]')
        
        if len(all_tablists) <= 1:
            site_map[main_slug] = str(Path(main_slug) / "index.html")
        else:
            sub_tabs_handles = await all_tablists[1].query_selector_all('[role="tab"]')
            if sub_tabs_handles:
                first_sub_name = await sub_tabs_handles[0].inner_text()
                site_map[main_slug] = str(Path(main_slug) / f"{slugify(first_sub_name)}.html")

                for sub_tab_handle in sub_tabs_handles:
                    sub_name = await sub_tab_handle.inner_text()
                    site_map[slugify(sub_name)] = str(Path(main_slug) / f"{slugify(sub_name)}.html")

    print("--- Site Discovery Complete ---")
    print(json.dumps(site_map, indent=2))
    await page.goto(page.url, wait_until="networkidle")
    return site_map

async def main_scraper(url: str, out_dir_base: str):
    site_map = {} # Define site_map at a higher scope
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")

        if Path(out_dir_base).exists():
            print(f"--- Removing existing output directory: {out_dir_base} ---")
            shutil.rmtree(out_dir_base)
        Path(out_dir_base).mkdir(exist_ok=True)

        main_tabs_handles = await page.query_selector_all(
            'div[role="tablist"]:first-of-type >> [role="tab"]'
        )

        async with aiohttp.ClientSession() as session:
            if not main_tabs_handles:
                print("--- No tabs found. Saving as a single page. ---")
                await save_page_with_assets(page, session, out_dir_base, "index", {}, out_dir_base)
            else:
                site_map = await discover_site_structure(page)
                print("\n--- Starting Download and Rewrite Phase ---")
                for i in range(len(main_tabs_handles)):
                    main_tabs = await page.query_selector_all(
                        'div[role="tablist"]:first-of-type >> [role="tab"]'
                    )
                    name = await main_tabs[i].inner_text()
                    print(f"\nProcessing main tab: {name}")

                    try:
                        await main_tabs[i].click()
                        await page.wait_for_timeout(2000)

                        slug = slugify(name)
                        tab_out_dir = Path(out_dir_base) / slug
                        tab_out_dir.mkdir(parents=True, exist_ok=True)

                        all_tablists = await page.query_selector_all('[role="tablist"]')
                        if len(all_tablists) <= 1:
                            await save_page_with_assets(
                                page, session, str(tab_out_dir), "index", site_map, out_dir_base
                            )
                        else:
                            print(f"  Found sub-tabs for '{name}'")
                            sub_tabs_list = await page.query_selector_all('div[role="tablist"] >> nth=1 >> [role="tab"]')
                            
                            for j in range(len(sub_tabs_list)):
                                all_tablists_again = await page.query_selector_all('[role="tablist"]')
                                sub_tabs_container = all_tablists_again[1]
                                sub_tabs = await sub_tabs_container.query_selector_all('[role="tab"]')

                                sub_name = await sub_tabs[j].inner_text()
                                try:
                                    await sub_tabs[j].click()
                                    await page.wait_for_timeout(1500)
                                    await save_page_with_assets(
                                        page,
                                        session,
                                        str(tab_out_dir),
                                        slugify(sub_name),
                                        site_map,
                                        out_dir_base,
                                    )
                                except Exception as sub_e:
                                    print(f"    -> Error on sub-tab '{sub_name}': {sub_e}")

                    except Exception as e:
                        print(f"  -> Error on main tab '{name}': {e}")
        
        # --- CREATE INDEX.HTML REDIRECT FILE ---
        if site_map:
            first_page_path = next(iter(site_map.values()))
            
            # Always use index.html as the root file name
            root_file_path = Path(out_dir_base) / "index.html"
            
            print(f"\n--- Creating root entry file 'index.html' to redirect to '{first_page_path}' ---")
            
            redirect_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Redirecting...</title>
    <meta charset="utf-8" />
    <meta http-equiv="refresh" content="0; url={first_page_path}" />
</head>
<body>
    <p>If you are not redirected automatically, follow this <a href="{first_page_path}">link to the dashboard</a>.</p>
</body>
</html>
"""
            with open(root_file_path, 'w', encoding='utf-8') as f:
                f.write(redirect_html.strip())
            
            print(f"✅ Root file created successfully.")
        # --- END OF MODIFIED CODE BLOCK ---

        await browser.close()
        print("\n✅ All tabs and assets downloaded and linked.")


#
# ——— Streamlit UI ———
#

st.title("💾 Save your Flipside dashboard")
st.markdown(
    """
    Enter the URL of your dashboard, click **Start Download**,  
    and this tool will grab all tabs (and sub-tabs), download their HTML + CSS assets,  
    rewrite links to work offline, and package them for you.
    """
)

url = st.text_input("🔗 Dashboard URL", placeholder="https://example.com/your-dashboard")
out_dir = st.text_input("📁 Dashboard Name", value="Enter Dashboard Name")

if st.button("🚀 Start Download"):
    if not url.strip():
        st.error("Please enter a valid URL.")
    else:
        # Create a container for logs
        log_container = st.empty()
        logs = []
        original_print = builtins.print

        def _capture_print(*args, **kwargs):
            # Call the original print function
            original_print(*args, **kwargs)
            
            # Add to logs
            log_message = " ".join(str(a) for a in args)
            logs.append(log_message)
            
            # Update the log display in real-time
            with log_container.container():
                st.subheader("📝 Logs (Live)")
                st.code("\n".join(logs), language="text")

        builtins.print = _capture_print
        
        # Show initial log container
        with log_container.container():
            st.subheader("📝 Logs (Live)")
            st.code("Starting download process...", language="text")

        try:
            with st.spinner("Downloading… this may take a few minutes…"):
                asyncio.run(main_scraper(url, out_dir))
            st.success("✅ Download complete!")
        except Exception as e:
            error_msg = f"❌ Error: {e}"
            logs.append(error_msg)
            st.error(error_msg)
        finally:
            builtins.print = original_print
            
        # Final log display
        with log_container.container():
            st.subheader("📝 Logs")
            st.code("\n".join(logs), language="text")

        if Path(out_dir).exists():
            # Create a ZIP file with a clean name based on the dashboard name
            clean_name = out_dir.lower().replace(' ', '_')
            zip_filename = f"{clean_name}_dashboard.zip"
            zip_path = shutil.make_archive(out_dir, 'zip', out_dir)
            
            # Rename the zip file to our clean name
            new_zip_path = Path(zip_path).parent / zip_filename
            Path(zip_path).rename(new_zip_path)
            
            with open(new_zip_path, "rb") as fp:
                st.download_button(
                    label="📥 Download ZIP of snapshots",
                    data=fp,
                    file_name=zip_filename,
                    mime="application/zip"
                )
