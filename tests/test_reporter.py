import os
import pytest


os.environ.setdefault('API_KEY', 'test-key-for-pytest-only')


def test_weekly_report_generates_valid_html(tmp_path):
    from src.reporter import generate_weekly_report
    output = str(tmp_path / 'report.html')
    result = generate_weekly_report(city='Riyadh', output_path=output)
    assert os.path.exists(result)
    content = open(result, encoding='utf-8').read()
    assert '<!DOCTYPE html>'           in content
    assert 'Riyadh'                    in content
    assert 'Executive Summary'         in content
    assert 'Congestion Trend'          in content
    assert 'Saudi Green Initiative'    in content
    assert 'data:image/png;base64'     in content




def test_pdf_report_generates_valid_file(tmp_path):
    from src.reporter import generate_weekly_report_pdf
    output = str(tmp_path / 'report.pdf')
    result = generate_weekly_report_pdf(city='Riyadh', output_path=output)
    assert os.path.exists(result)
    with open(result, 'rb') as f:
        assert f.read(4) == b'%PDF'

# tests/test_reporter.py (add at the end)

def test_api_doc_package_generates_valid_html_file(tmp_path):
    """Test that the generated HTML contains all 8 section headers."""
    from src.reporter import generate_api_doc_package
    # Create dummy markdown files in a temporary directory
    base = tmp_path / "docs"
    base.mkdir()
    files = [
        "ENDPOINT_SENSITIVITY.md",
        "SECURITY_POLICY.md",
        "SLA_TERMS.md",
        "PDPL_COMPLIANCE_NOTE.md",
        "MODEL_CHANGELOG.md",
        "INTEGRATION.md",
    ]
    for fname in files:
        (base / fname).write_text(f"# Dummy content for {fname}\n\nSome text.")
    
    # Create a minimal app.py to supply version
    (base / "app.py").write_text('__version__ = "5.0.0"')
    
    output_dir = tmp_path / "output"
    output_file = generate_api_doc_package(str(output_dir), base_path=str(base))
    
    assert os.path.exists(output_file)
    
    with open(output_file, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Check all 8 section headers (numbered)
    sections = [
        "1. Executive Summary",
        "2. Endpoint Reference",
        "3. Authentication and Access Control",
        "4. SLA Terms",
        "5. Data Privacy",
        "6. Model Version History",
        "7. Integration Guide",
        "8. Limitations and Scope",
    ]
    for sec in sections:
        assert f"<h2>{sec}</h2>" in html, f"Section '{sec}' not found"


def test_api_doc_package_includes_limitations_section(tmp_path):
    """Specifically assert the Limitations section mentions synthetic data."""
    from src.reporter import generate_api_doc_package
    base = tmp_path / "docs"
    base.mkdir()
    # Create minimal dummy files (only need to trigger generation)
    files = [
        "ENDPOINT_SENSITIVITY.md",
        "SECURITY_POLICY.md",
        "SLA_TERMS.md",
        "PDPL_COMPLIANCE_NOTE.md",
        "MODEL_CHANGELOG.md",
        "INTEGRATION.md",
    ]
    for fname in files:
        (base / fname).write_text("# Dummy\n\nContent.")
    (base / "app.py").write_text('__version__ = "5.0.0"')
    
    output_dir = tmp_path / "output"
    output_file = generate_api_doc_package(str(output_dir), base_path=str(base))
    
    with open(output_file, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Look for the Limitations section and check for "synthetic" (case-insensitive)
    import re
    # Extract the section between <h2>Limitations and Scope</h2> and next <h2> or end
    pattern = r'<h2>8\. Limitations and Scope</h2>(.*?)(?=<h2>|</body>)'
    match = re.search(pattern, html, re.DOTALL)
    assert match is not None, "Limitations section not found"
    limitations_text = match.group(1)
    assert re.search(r'synthetic', limitations_text, re.IGNORECASE), "Limitations section does not mention 'synthetic'"