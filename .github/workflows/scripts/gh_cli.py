"""
Wrapper of GitHub CLI for Pull Request Actions

See:
- https://cli.github.com/manual
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/using-github-cli-in-workflows

Environ:
- PR_NUMBER
- GH_TOKEN or github_api_token

---

This file is part of scripts of MCDReforged Plugin Catalogue.

This is a free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.

This is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
in the `scripts` folder of the project root. If not, see
<https://www.gnu.org/licenses/>.
"""

import os
import subprocess
import json
from typing import Optional, Tuple

from common.log import logger
from utilities import COMMENT_SIGN

EXECUTABLE = 'gh'
PR_NUMBER = os.environ.get('PR_NUMBER')
CATALOGUE_REPO = 'MCDReforged/PluginCatalogue'.split('/')

if 'GH_TOKEN' not in os.environ:
    os.environ['GH_TOKEN'] = os.environ.get('github_api_token', '')

os.environ['NO_COLOR'] = 'true'  # https://cli.github.com/manual/gh_help_environment

logger.info('Initializing gh-cli with PR number: %s', PR_NUMBER)


def pr_comment(body: str, edit_last: bool = False, pr_number: str = PR_NUMBER) -> None:
    """Comment on a PR

    Runs:
        `gh pr comment <pr_number> --body-file <body_file> [--edit-last]`
    """
    try:
        logger.info(f'Commenting on PR: #{pr_number}, edit_last: {edit_last}')

        body_file = 'reply.md'
        with open(body_file, 'w', encoding='utf-8') as f:
            f.write(body)

        cmd = [EXECUTABLE, 'pr', 'comment', pr_number, '--body-file', body_file]
        if edit_last:
            cmd.append('--edit-last')

        result = subprocess.check_output(cmd)
        logger.info(result.decode('utf-8'))
    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to comment: returned {e.returncode}.')
    except Exception as e:
        logger.error(f'Failed to comment: {e}')


def pr_update_or_comment(user: str, body: str, pr_number: str = PR_NUMBER, sign: str = COMMENT_SIGN) -> None:
    """Update last comment of given user if it contains sign, otherwise add a new one

    Checks:
        `gh pr view <pr_number> --json comments --jq <jq_query>`
        `jq_query := .comments | any(.author.login == "<user>" and (.body | contains("<sign>")))`
    """
    cmd = [
        EXECUTABLE, 'pr', 'view', pr_number, '--json', 'comments', '--jq',
        f'.comments | any(.author.login == "{user}" and (.body | contains("{sign}")))'
    ]
    try:
        result = subprocess.check_output(cmd)  # true\n
        if result.decode('utf-8').startswith('true'):
            logger.info(f'Updating last comment of {user} on PR: #{pr_number}')
            pr_comment(pr_number=pr_number, body=body, edit_last=True)
        else:
            pr_comment(pr_number=pr_number, body=body)
    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to check last comment: returned {e.returncode}.')
    except Exception as e:
        logger.error(f'Failed to check last comment: {e}')


def pr_label(add_labels: Optional[list[str]] = None, remove_labels: Optional[list[str]] = None, pr_number: str = PR_NUMBER) -> None:
    """Add or remove labels from a PR

    `remove_labels` will be ignored it `add_labels` is provided

    Runs:
        `gh pr edit <pr_number> [--add-label|--remove-label] <add_labels|remove_labels>`
    """
    logger.info(f'Labeling PR: #{pr_number}, add_labels: {add_labels}, remove_labels: {remove_labels}')
    cmd = [EXECUTABLE, 'pr', 'edit', pr_number]
    if add_labels:
        cmd.extend(['--add-label', ','.join(add_labels)])
    elif remove_labels:
        cmd.extend(['--remove-label', ','.join(remove_labels)])
    else:
        logger.info('No labels to add or remove, skipping')
        return
    try:
        result = subprocess.check_output(cmd)
        logger.info(result.decode('utf-8'))
    except Exception as e:
        logger.error(f'Failed to label: {e}')


def check_contributor(pr_number: str = PR_NUMBER) -> Tuple[Optional[str], bool]:
    """Check if the author of a PR is a first-time contributor.

    Args:
        pr_number (str): The pull request number.

    Returns:
        Tuple[Optional[str], bool]: A tuple containing the author's login and a boolean indicating if they are a first-time contributor.

    Data Structure:
        ```
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "author": {
                            "login": "<author_login>"
                        },
                        "authorAssociation": "FIRST_TIME_CONTRIBUTOR"
                    }
                }
            }
        }
        ```
    """
    logger.info(f'Checking contributor for PR: #{pr_number}')

    query = ' '.join(map(str.strip, f"""
    {{
      repository(owner: "{CATALOGUE_REPO[0]}", name: "{CATALOGUE_REPO[1]}") {{
        pullRequest(number: {pr_number}) {{
          author {{
            login
          }}
          authorAssociation
        }}
      }}
    }}
    """.split('\n')))

    cmd = [
        'gh', 'api', 'graphql', '-F', f'query={query}']

    try:
        result = subprocess.check_output(cmd)   # Alex326 false
        result_json = json.loads(result.decode('utf-8'))

        author_login = result_json['data']['repository']['pullRequest']['author']['login']
        is_first_time = result_json['data']['repository']['pullRequest']['authorAssociation'].upper() == 'FIRST_TIME_CONTRIBUTOR'

        logger.info(f'Contributor: {author_login}, First Time: {is_first_time}')
        return author_login, is_first_time

    except Exception as e:
        logger.error(f'Failed to fetch contributor data: {e}')
        return None, False
