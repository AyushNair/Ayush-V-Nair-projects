"""Run one synthetic BiLSTM training epoch without the protected dataset.

The repository is copied to a temporary directory, and all generated sample
data and checkpoints stay there. Install the packages in requirements.txt and
PyTorch before running this script from the repository root.
"""

import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def prepare_synthetic_inputs(repo_dir, torch):
    dataset_name = 'SyntheticDemo'
    labels = ['real', 'fake', 'real', 'fake']
    token_ids = [[1, 2, 3], [4, 5], [6, 7, 8], [9, 10]]

    posts_dir = repo_dir / 'dataset' / dataset_name / 'post'
    tokens_dir = repo_dir / 'preprocess' / 'WordEmbeddings' / 'data' / dataset_name
    posts_dir.mkdir(parents=True, exist_ok=True)
    tokens_dir.mkdir(parents=True, exist_ok=True)

    examples = [
        {'label': label, 'content': 'synthetic example {}'.format(index)}
        for index, label in enumerate(labels)
    ]
    for split in ('train', 'val', 'test'):
        with open(posts_dir / '{}.json'.format(split), 'w', encoding='utf-8') as output:
            json.dump(examples, output)
        with open(tokens_dir / '{}.pkl'.format(split), 'wb') as output:
            pickle.dump(token_ids, output)

    torch.manual_seed(7)
    embeddings = torch.randn(11, 300)
    embeddings[0].zero_()
    torch.save(embeddings, tokens_dir / 'embedding_weight.pt')


def main():
    try:
        import torch
    except ImportError as exc:
        raise SystemExit(
            'PyTorch is required. Install the matching build from pytorch.org first.'
        ) from exc

    source_repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='news-env-demo-') as temporary_dir:
        copied_repo = Path(temporary_dir) / 'repository'
        shutil.copytree(
            source_repo,
            copied_repo,
            ignore=shutil.ignore_patterns('.git', '.venv', '__pycache__', '*.pyc'),
        )
        prepare_synthetic_inputs(copied_repo, torch)

        command = [
            sys.executable, 'main.py',
            '--dataset', 'SyntheticDemo',
            '--model', 'BiLSTM',
            '--use_news_env', 'false',
            '--epochs', '1',
            '--batch_size', '2',
            '--num_workers', '0',
            '--fp16', 'false',
            '--save', './ckpts/SyntheticDemo/demo',
        ]
        print('Running a one-epoch BiLSTM demo on generated synthetic examples.')
        subprocess.run(command, cwd=copied_repo / 'model', check=True)
        print('Synthetic demo completed successfully.')


if __name__ == '__main__':
    main()
