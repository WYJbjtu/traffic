"""Offline regression checks for published exact bytes and README integration."""
from pathlib import Path
import hashlib
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]
METRICS = 'experiments/unified96/runs/p1-f0-f4-v1/metrics.csv'
EXPECTED = 'a263659e54dedefde9a3ce801dbff09d09c0e181b62ad5546d63b1cfa887dcbf'


def test_readme_has_no_merge_markers():
    assert not re.search(r'^(?:<{7}|={7}|>{7})(?: |$)', (ROOT/'README.md').read_text(encoding='utf-8'), re.M)


def test_frozen_checkout_with_autocrlf(tmp_path):
    """Real Git index checkout, outside project; not a claim about Windows CI."""
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('config', 'core.autocrlf', 'false')
    (tmp_path/'.gitattributes').write_bytes((ROOT/'.gitattributes').read_bytes())
    target = tmp_path/METRICS
    target.parent.mkdir(parents=True)
    scoped = 'experiments/unified96/.gitattributes'
    (tmp_path/scoped).write_bytes((ROOT/scoped).read_bytes())
    target.write_bytes((ROOT/METRICS).read_bytes())
    git('add', '.gitattributes', scoped, METRICS)
    target.unlink()
    git('-c', 'core.autocrlf=true', 'checkout-index', '-a', '-f')
    assert hashlib.sha256(target.read_bytes()).hexdigest() == EXPECTED
