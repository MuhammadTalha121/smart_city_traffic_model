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

