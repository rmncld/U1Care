"""Exercise upstream HACS 2.0.5 polling/release logic without a download.

CI checks out upstream code. Only the relevant methods are compiled unchanged,
avoiding HACS setup, credentials and any changes to real HA configuration.
GitHub's response and scheduling are test doubles; selection and polling are HACS.
"""
import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.update import UpdateEntity

ROOT = Path(__file__).parents[1]
UPSTREAM = ROOT / 'work/hacs-reference/custom_components/hacs'
pytestmark = pytest.mark.skipif(not UPSTREAM.exists(), reason='Upstream HACS checkout is installed by CI')


def upstream_methods(path, class_name, names):
    tree = ast.parse((UPSTREAM / path).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    namespace = {}
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0),
        *[node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(UPSTREAM / path), 'exec'), namespace)
    return {name: namespace[name] for name in names}


@pytest.mark.asyncio
@pytest.mark.parametrize('installed', ['v0.3.6', 'v0.4.0', 'v0.4.1'])
async def test_upstream_periodic_poll_signals_new_release_without_download(installed):
    from awesomeversion import AwesomeVersion
    version = json.loads((ROOT / 'custom_components/u1_companion/manifest.json').read_text())['version']
    latest = 'v' + version
    repository_methods = upstream_methods('repositories/base.py', 'HacsRepository', [
        'get_releases', 'common_update_data', 'version_to_download',
        'display_available_version', 'display_installed_version', 'display_version_or_commit', 'pending_update'])
    # Supply the same version comparison to the isolated pending_update property.
    repository_methods['common_update_data'].__globals__.update({
        'HacsException': RuntimeError, 'AIOGitHubAPIException': RuntimeError,
        'HacsNotModifiedException': LookupError, 'HacsRepositoryExistException': KeyError,
        'HacsRepositoryArchivedException': ValueError})
    repository_methods['pending_update'].fget.__globals__['version_left_higher_then_right'] = lambda a, b: AwesomeVersion(a) > AwesomeVersion(b)
    Repo = type('UpstreamRepositoryProbe', (), repository_methods)
    repo = Repo()
    repo.data = NS(full_name='rmncld/U1Care', archived=False, installed=True,
        installed_version=installed, installed_commit=None, etag_repository=None,
        selected_tag=None, default_branch='main', show_beta=False, prerelease=None,
        last_version=installed, last_commit=None, category='integration', id=1420718056,
        update_data=MagicMock(), releases=True)
    repo.releases = NS(objects=[])
    repo.force_branch = False
    repo.string = 'rmncld/U1Care'
    repo.logger = MagicMock()
    repo.validate = NS(errors=[])
    release = NS(tag_name=latest, draft=False, prerelease=False, assets=[])
    github = AsyncMock(return_value=NS(data=[release]))
    coordinator = NS(async_update_listeners=MagicMock())
    tasks, queued = [], []
    def background(coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        tasks.append(task)
        return task
    hacs = NS(system=NS(disabled=False, generator=False, action=False),
        common=NS(categories=['integration'], renamed_repositories={}),
        repositories=NS(list_downloaded=[repo], is_default=lambda _: False, is_removed=lambda _: False),
        queue=NS(add=queued.append), configuration=NS(config_entry=None),
        hass=NS(async_create_background_task=background),
        coordinators={'integration': coordinator}, log=MagicMock(),
        githubapi=NS(repos=NS(releases=NS(list=object()))), async_github_api_method=github)
    repo.hacs = hacs
    repo.async_get_legacy_repository_object = AsyncMock(return_value=(NS(full_name='rmncld/U1Care', attributes={}), 'etag'))
    repo.get_tree = AsyncMock(return_value=[NS(full_path='custom_components/u1_companion/manifest.json')])
    repo.update_repository = AsyncMock()
    # AsyncMock's side_effect is explicitly async so its coroutine is awaited.
    async def refresh(**kwargs):
        await repo.common_update_data()
    repo.update_repository.side_effect = refresh
    repo.async_download_repository = AsyncMock()
    poll = upstream_methods('base.py', 'HacsBase', ['async_update_downloaded_custom_repositories'])['async_update_downloaded_custom_repositories']
    poll.__globals__['asyncio'] = asyncio
    await poll(hacs)
    await asyncio.gather(*queued)
    await asyncio.gather(*tasks)
    assert repo.display_available_version == latest
    assert repo.display_installed_version == installed
    assert repo.pending_update is True
    coordinator.async_update_listeners.assert_called_once()
    repo.async_download_repository.assert_not_called()
    Entity = type('UpstreamUpdateProbe', (UpdateEntity,), upstream_methods('update.py', 'HacsRepositoryUpdateEntity', ['installed_version', 'latest_version']))
    entity = Entity()
    entity.repository = repo
    assert entity.state == 'on'
