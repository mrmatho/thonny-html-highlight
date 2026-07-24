# thonny-html-highlight

Syntax highlighting for HTML, CSS, and JavaScript files in the [Thonny](https://thonny.org) IDE.

By default Thonny treats `.html`, `.htm`, `.css`, and `.js` files as plain text. This plugin adds colour highlighting for:

- Tag names (`div`, `span`, `a`, …)
- Attribute names (`class`, `href`, `data-value`, …)
- Attribute values (`"foo"`, `'bar'`, …)
- HTML comments (`<!-- … -->`)
- DOCTYPE declarations (`<!DOCTYPE html>`)
- Entity references (`&amp;`, `&#169;`, `&#xA9;`, …)
- Angle-bracket punctuation
- CSS selectors, properties, values, and comments
- JavaScript keywords, builtins, strings, numbers, and comments

## Requirements

- Thonny 5.0 or later
- Python 3.13 or later (bundled with Thonny 5)

## Installation

### Via Thonny's built-in package manager (recommended)

1. Open Thonny.
2. Go to **Tools → Manage packages…**
3. Search for `thonny-html-highlight`.
4. Click **Install**.
5. Restart Thonny.

### Via pip / uv (command line)

```bash
# Using pip
pip install thonny-html-highlight

# Using uv
uv pip install thonny-html-highlight
```

Then restart Thonny.

### From source (development)

```bash
git clone https://github.com/mrmatho/thonny-html-highlight.git
cd thonny-html-highlight
uv pip install -e .
```

Restart Thonny after installing.

## Usage

Open any `.html`, `.htm`, `.css`, or `.js` file in Thonny — highlighting is applied automatically. HTML files also highlight CSS inside `<style>` tags and JavaScript inside `<script>` tags.

## Known limitations

- Colours follow Thonny's default light theme. Integration with custom syntax themes is planned for a future release.

## Development

```bash
# Run tests
uv run --group test pytest

# Run tests with verbose output
uv run --group test pytest -v
```

## Licence

MIT
