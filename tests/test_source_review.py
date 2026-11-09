import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


def release_module():
    path = Path(__file__).resolve().parents[1] / 'scripts/create_draft_release.py'
    spec = importlib.util.spec_from_file_location('test_release_review', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bundle(path, mutation=None):
    text = b'upstream license text'
    review = {'commit': 'a' * 40, 'distribution_inventory_sha256': 'b' * 64,
              'public_distribution_approved': True,
              'components': [{'id': 'qt', 'status': 'reviewed', 'rationale': 'Fixture rationale only',
                 'license_materials': [{'path': 'notices/LICENSE', 'sha256': hashlib.sha256(text).hexdigest()}]}]}
    if mutation:
        mutation(review)
    with zipfile.ZipFile(path, 'w') as output:
        output.writestr('distribution-review.json', json.dumps(review))
        output.writestr('notices/LICENSE', text)
    return path


def test_matching_source_review_and_material_hashes(tmp_path):
    module = release_module()
    module.validate_source_review(bundle(tmp_path / 'source.zip'), 'a' * 40, 'b' * 64, {'qt'})


@pytest.mark.parametrize('mutate', [
    lambda r: r.update(public_distribution_approved=False),
    lambda r: r.update(commit='c' * 40),
    lambda r: r.update(distribution_inventory_sha256='d' * 64),
    lambda r: r.update(components=[]),
    lambda r: r['components'][0].update(status='needs-review'),
    lambda r: r['components'][0].update(rationale=''),
    lambda r: r['components'][0]['license_materials'][0].update(sha256='e' * 64),
])
def test_incomplete_or_mismatched_review_blocks_release(tmp_path, mutate):
    with pytest.raises(ValueError):
        release_module().validate_source_review(bundle(tmp_path / 'source.zip', mutate), 'a' * 40, 'b' * 64, {'qt'})
