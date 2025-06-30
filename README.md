# Tab-Structured Site Snapshotter

A powerful tool to download and save tab-structured websites as offline HTML snapshots. Perfect for archiving dashboards, documentation, or any website with tabbed navigation.

## Features

- 🚀 Scrapes all tabs and sub-tabs from a website
- 💾 Saves complete offline snapshots with all assets (CSS, JS, images)
- 🔗 Rewrites links to work offline
- 📂 Organizes content in a clean directory structure
- ⚡ Built with Python and Playwright for reliable scraping

## Prerequisites

- Python 3.9+
- Node.js (required for Playwright)
- Git (for cloning the repository)

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/tab-snapshotter.git
   cd tab-snapshotter
   ```

2. **Create and activate a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**:
   ```bash
   playwright install
   ```

## Usage

1. **Run the Streamlit app**:
   ```bash
   streamlit run streamlit_app.py
   ```

2. **In the web interface**:
   - Enter the URL of the website you want to scrape
   - Provide a name for the output directory
   - Click "Start Download"

3. **View the output**:
   - The tool will create a new directory with your specified name
   - Open `index.html` in your browser to view the offline snapshot


## Output Structure

The tool creates the following directory structure:

```
output_directory/
├── index.html                  # Main entry point (redirects to first tab)
├── tab1/                       # First tab
│   ├── index.html              # Main content of first tab
│   └── assets/                 # Assets for first tab
│       ├── styles.css
│       └── script.js
├── tab2/                       # Second tab
│   ├── index.html
│   └── assets/
└── ...
```

## Troubleshooting

- **Missing tabs**: Some websites load content dynamically. Try increasing the wait times in the code.
- **Authentication**: The tool doesn't handle login-required pages. Ensure the content is publicly accessible.
- **Rate limiting**: Some websites may block frequent requests. Add delays between requests if needed.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you find this tool useful, consider giving it a ⭐ on GitHub!
